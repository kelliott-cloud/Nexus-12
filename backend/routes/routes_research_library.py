"""Research Library Routes — CRUD, ingestion, chat, compare, lit-review, search, annotations, connectors."""
import uuid
import logging
from fastapi import HTTPException, Request, BackgroundTasks, UploadFile, File
from nexus_utils import now_iso, gen_id, require_workspace_access

logger = logging.getLogger(__name__)


def register_research_library_routes(api_router, db, get_current_user, ws_manager=None):

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        return user

    # ============ Libraries ============

    @api_router.post("/workspaces/{ws_id}/research-libraries")
    async def create_library(ws_id: str, request: Request):
        user = await _authed(request, ws_id)
        body = await request.json()
        lib_id = gen_id("rlib")
        lib = {
            "library_id": lib_id, "workspace_id": ws_id,
            "name": body.get("name", "Untitled Library"), "description": body.get("description", ""),
            "doc_count": 0, "tags": body.get("tags", []),
            "connectors": {"zotero": None, "mendeley": None},
            "created_by": user["user_id"], "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.research_libraries.insert_one(lib)
        lib.pop("_id", None)
        return lib

    @api_router.get("/workspaces/{ws_id}/research-libraries")
    async def list_libraries(ws_id: str, request: Request):
        await _authed(request, ws_id)
        libs = await db.research_libraries.find({"workspace_id": ws_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
        return {"libraries": libs}

    @api_router.get("/research-libraries/{lib_id}")
    async def get_library(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0})
        if not lib:
            raise HTTPException(404, "Library not found")
        await require_workspace_access(db, user, lib["workspace_id"])
        return lib

    @api_router.delete("/research-libraries/{lib_id}")
    async def delete_library(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        await require_workspace_access(db, user, lib["workspace_id"])
        doc_ids = [d["doc_id"] async for d in db.research_documents.find({"library_id": lib_id}, {"_id": 0, "doc_id": 1})]
        if doc_ids:
            await db.research_chunks.delete_many({"doc_id": {"$in": doc_ids}})
            await db.research_annotations.delete_many({"doc_id": {"$in": doc_ids}})
        await db.research_documents.delete_many({"library_id": lib_id})
        await db.research_libraries.delete_one({"library_id": lib_id})
        return {"status": "deleted"}

    # ============ Documents ============

    @api_router.post("/research-libraries/{lib_id}/documents")
    async def upload_document(lib_id: str, request: Request, bg: BackgroundTasks):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404, "Library not found")
        ws_id = lib["workspace_id"]
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        filename = body.get("filename", "document.pdf")
        content_b64 = body.get("content", "")
        if not content_b64:
            raise HTTPException(400, "content (base64) required")
        import base64
        file_bytes = base64.b64decode(content_b64)
        from research_ingestion import ingest_document
        bg.add_task(_ingest_bg, db, file_bytes, filename, lib_id, ws_id, user["user_id"])
        return {"status": "ingesting", "library_id": lib_id}

    @api_router.get("/research-libraries/{lib_id}/documents")
    async def list_documents(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        await require_workspace_access(db, user, lib["workspace_id"])
        docs = await db.research_documents.find({"library_id": lib_id}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        return {"documents": docs}

    @api_router.get("/research-documents/{doc_id}")
    async def get_document(doc_id: str, request: Request):
        user = await get_current_user(request)
        doc = await db.research_documents.find_one({"doc_id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404)
        await require_workspace_access(db, user, doc["workspace_id"])
        return doc

    @api_router.get("/research-documents/{doc_id}/chunks")
    async def get_document_chunks(doc_id: str, request: Request, limit: int = 100, offset: int = 0):
        user = await get_current_user(request)
        doc = await db.research_documents.find_one({"doc_id": doc_id}, {"_id": 0, "workspace_id": 1})
        if not doc:
            raise HTTPException(404)
        await require_workspace_access(db, user, doc["workspace_id"])
        chunks = await db.research_chunks.find({"doc_id": doc_id}, {"_id": 0}).sort("para_index", 1).skip(offset).limit(limit).to_list(limit)
        total = await db.research_chunks.count_documents({"doc_id": doc_id})
        return {"chunks": chunks, "total": total}

    @api_router.delete("/research-documents/{doc_id}")
    async def delete_document(doc_id: str, request: Request):
        user = await get_current_user(request)
        doc = await db.research_documents.find_one({"doc_id": doc_id}, {"_id": 0, "workspace_id": 1, "library_id": 1})
        if not doc:
            raise HTTPException(404)
        await require_workspace_access(db, user, doc["workspace_id"])
        await db.research_chunks.delete_many({"doc_id": doc_id})
        await db.research_annotations.delete_many({"doc_id": doc_id})
        await db.research_documents.delete_one({"doc_id": doc_id})
        await db.research_libraries.update_one({"library_id": doc["library_id"]}, {"$inc": {"doc_count": -1}})
        return {"status": "deleted"}

    # ============ Citation-Linked Chat ============

    @api_router.post("/research-libraries/{lib_id}/chat")
    async def library_chat(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        await require_workspace_access(db, user, lib["workspace_id"])
        body = await request.json()
        query = body.get("query", "").strip()
        if not query:
            raise HTTPException(400, "query required")
        from research_chat import research_chat
        return await research_chat(db, query, lib_id, lib["workspace_id"], model=body.get("model", "claude"))

    # ============ Search ============

    @api_router.post("/research-libraries/{lib_id}/search")
    async def search_library(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        await require_workspace_access(db, user, lib["workspace_id"])
        body = await request.json()
        query = body.get("query", "").strip()
        from research_chat import _retrieve_relevant_chunks
        chunks = await _retrieve_relevant_chunks(db, query, lib_id, lib["workspace_id"], max_chunks=body.get("limit", 25))
        for c in chunks:
            doc = await db.research_documents.find_one({"doc_id": c["doc_id"]}, {"_id": 0, "title": 1})
            c["doc_title"] = (doc or {}).get("title", "")
        return {"results": chunks, "total": len(chunks)}

    # ============ Compare ============

    @api_router.post("/research-libraries/{lib_id}/compare")
    async def compare_documents(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        ws_id = lib["workspace_id"]
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        doc_ids = body.get("doc_ids", [])
        question = body.get("question", "Compare these documents")
        if len(doc_ids) < 2:
            raise HTTPException(400, "At least 2 doc_ids required")
        context_parts = []
        for did in doc_ids[:10]:
            doc = await db.research_documents.find_one({"doc_id": did}, {"_id": 0, "title": 1, "abstract": 1})
            top_chunks = await db.research_chunks.find({"doc_id": did}, {"_id": 0, "content": 1, "section_title": 1}).limit(5).to_list(5)
            text = f"PAPER: {(doc or {}).get('title','?')}\nAbstract: {(doc or {}).get('abstract','')[:300]}\n"
            for c in top_chunks:
                text += f"[{c.get('section_title','')}] {c['content'][:200]}\n"
            context_parts.append(text)
        from collaboration_core import get_ai_key_for_agent
        from ai_providers import call_ai_direct
        for agent in ["claude", "chatgpt", "gemini"]:
            api_key, _ = await get_ai_key_for_agent("system", ws_id, agent)
            if api_key:
                answer = await call_ai_direct(agent, api_key,
                    "Compare the following research papers. Identify agreements, disagreements, and gaps.",
                    f"{'---'.join(context_parts)}\n\nQUESTION: {question}",
                    workspace_id=ws_id, db=db)
                return {"comparison": answer, "docs_compared": len(doc_ids)}
        return {"comparison": "No AI key available", "docs_compared": 0}

    # ============ Literature Review ============

    @api_router.post("/research-libraries/{lib_id}/lit-review")
    async def start_lit_review(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        ws_id = lib["workspace_id"]
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        question = body.get("question", "")
        docs = await db.research_documents.find(
            {"library_id": lib_id, "ingestion_status": "completed"},
            {"_id": 0, "doc_id": 1, "title": 1, "abstract": 1, "authors": 1}
        ).limit(100).to_list(100)
        doc_context = "\n".join([f"- {d['title']} by {(d.get('authors') or ['Unknown'])[0]}: {d.get('abstract','')[:200]}" for d in docs])
        goal = f"Conduct a comprehensive literature review on: {question}\n\nAvailable papers ({len(docs)} documents):\n{doc_context}\n\nProduce: key themes, methodology comparison, findings synthesis, research gaps, recommendations."
        from agent_team_engine import AgentTeamEngine
        engine = AgentTeamEngine(db, ws_manager)
        session_id = await engine.start_session(goal=goal, workspace_id=ws_id,
            channel_id=body.get("channel_id", ""), user_id=user["user_id"],
            settings={"max_cost_usd": 2.0, "confidence_threshold": 0.65})
        return {"session_id": session_id, "status": "decomposing", "docs_included": len(docs)}

    # ============ Cross-Doc Graph ============

    @api_router.get("/research-libraries/{lib_id}/graph")
    async def get_cross_doc_graph(lib_id: str, request: Request):
        user = await get_current_user(request)
        lib = await db.research_libraries.find_one({"library_id": lib_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404)
        await require_workspace_access(db, user, lib["workspace_id"])
        docs = await db.research_documents.find({"library_id": lib_id, "ingestion_status": "completed"},
            {"_id": 0, "doc_id": 1, "title": 1, "references": 1, "tags": 1}).limit(100).to_list(100)
        nodes = [{"id": d["doc_id"], "title": d["title"], "tags": d.get("tags", [])} for d in docs]
        edges = []
        for i, d1 in enumerate(docs):
            for j, d2 in enumerate(docs):
                if i >= j:
                    continue
                shared_tags = set(d1.get("tags", [])) & set(d2.get("tags", []))
                if shared_tags:
                    edges.append({"source": d1["doc_id"], "target": d2["doc_id"], "type": "shared_tags", "tags": list(shared_tags)})
        return {"nodes": nodes, "edges": edges}

    # ============ Annotations ============

    @api_router.post("/research-documents/{doc_id}/annotations")
    async def create_annotation(doc_id: str, request: Request):
        user = await get_current_user(request)
        doc = await db.research_documents.find_one({"doc_id": doc_id}, {"_id": 0, "workspace_id": 1})
        if not doc:
            raise HTTPException(404)
        await require_workspace_access(db, user, doc["workspace_id"])
        body = await request.json()
        ann = {
            "annotation_id": gen_id("rann"), "doc_id": doc_id, "workspace_id": doc["workspace_id"],
            "chunk_id": body.get("chunk_id", ""), "page_num": body.get("page_num", 0),
            "highlight_text": body.get("highlight_text", ""), "note": body.get("note", ""),
            "color": body.get("color", "yellow"), "tags": body.get("tags", []),
            "ai_suggested": False, "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.research_annotations.insert_one(ann)
        ann.pop("_id", None)
        return ann

    @api_router.get("/research-documents/{doc_id}/annotations")
    async def list_annotations(doc_id: str, request: Request):
        user = await get_current_user(request)
        doc = await db.research_documents.find_one({"doc_id": doc_id}, {"_id": 0, "workspace_id": 1})
        if not doc:
            raise HTTPException(404)
        await require_workspace_access(db, user, doc["workspace_id"])
        anns = await db.research_annotations.find({"doc_id": doc_id}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        return {"annotations": anns}

    @api_router.delete("/annotations/{ann_id}")
    async def delete_annotation(ann_id: str, request: Request):
        user = await get_current_user(request)
        ann = await db.research_annotations.find_one({"annotation_id": ann_id}, {"_id": 0, "workspace_id": 1})
        if not ann:
            raise HTTPException(404)
        await require_workspace_access(db, user, ann["workspace_id"])
        await db.research_annotations.delete_one({"annotation_id": ann_id})
        return {"status": "deleted"}

    # ============ Zotero Connector ============

    @api_router.post("/connectors/zotero/sync")
    async def sync_zotero(request: Request, bg: BackgroundTasks):
        user = await get_current_user(request)
        body = await request.json()
        library_id = body.get("library_id", "")
        if not library_id:
            raise HTTPException(400, "library_id required")
        lib = await db.research_libraries.find_one({"library_id": library_id}, {"_id": 0, "workspace_id": 1})
        if not lib:
            raise HTTPException(404, "Library not found")
        ws_id = lib["workspace_id"]
        await require_workspace_access(db, user, ws_id)
        # Resolve Zotero credentials from key_resolver (not request body)
        from key_resolver import get_integration_key
        zotero_api_key = await get_integration_key(db, "ZOTERO_API_KEY")
        zotero_user_id = body.get("zotero_user_id", "")
        collection_id = body.get("collection_id", "")
        if not zotero_api_key:
            raise HTTPException(400, "Zotero API key not configured. Add ZOTERO_API_KEY in Settings > Integrations.")
        if not zotero_user_id:
            raise HTTPException(400, "zotero_user_id required")
        bg.add_task(_sync_zotero_bg, db, library_id, ws_id, zotero_user_id, zotero_api_key, collection_id, user["user_id"])
        return {"status": "syncing", "library_id": library_id}


async def _ingest_bg(db, file_bytes, filename, library_id, workspace_id, user_id):
    try:
        from research_ingestion import ingest_document
        await ingest_document(db, file_bytes, filename, library_id, workspace_id, user_id)
        await db.research_libraries.update_one({"library_id": library_id}, {"$inc": {"doc_count": 1}})
    except Exception as e:
        logger.error(f"Background ingestion failed: {e}")


async def _sync_zotero_bg(db, library_id, workspace_id, zotero_user_id, zotero_api_key, collection_id, user_id):
    try:
        import httpx
        url = f"https://api.zotero.org/users/{zotero_user_id}"
        if collection_id:
            url += f"/collections/{collection_id}/items"
        else:
            url += "/items"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Zotero-API-Key": zotero_api_key, "Zotero-API-Version": "3"})
            if resp.status_code != 200:
                logger.error(f"Zotero sync failed: {resp.status_code}")
                return
            items = resp.json()
            for item in items[:50]:
                data = item.get("data", {})
                existing = await db.research_documents.find_one({"zotero_key": item.get("key"), "library_id": library_id})
                if existing:
                    continue
                doc_id = gen_id("rdoc")
                await db.research_documents.insert_one({
                    "doc_id": doc_id, "workspace_id": workspace_id, "library_id": library_id,
                    "title": data.get("title", ""), "authors": [c.get("lastName", "") for c in data.get("creators", [])],
                    "abstract": data.get("abstractNote", ""), "doi": data.get("DOI"),
                    "publication_date": data.get("date"), "journal": data.get("publicationTitle"),
                    "ingestion_status": "metadata_only", "imported_from": "zotero",
                    "zotero_key": item.get("key"), "uploaded_by": user_id,
                    "chunk_count": 0, "tags": [t.get("tag", "") for t in data.get("tags", [])],
                    "created_at": now_iso(), "updated_at": now_iso(),
                })
                await db.research_libraries.update_one({"library_id": library_id}, {"$inc": {"doc_count": 1}})
        logger.info(f"Zotero sync complete for library {library_id}")
    except Exception as e:
        logger.error(f"Zotero sync failed: {e}")
