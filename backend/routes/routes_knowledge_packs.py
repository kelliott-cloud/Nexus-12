from nexus_utils import now_iso
"""Export/Import Agent Knowledge Packs — Download and upload agent knowledge as JSON."""
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import Request, UploadFile, File
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)



def register_knowledge_pack_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/knowledge/export")
    async def export_knowledge(ws_id: str, agent_id: str, request: Request):
        """Export agent knowledge as a downloadable JSON pack."""
        user = await get_current_user(request)

        agent = await db.nexus_agents.find_one(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "name": 1, "agent_id": 1, "skills": 1}
        )

        chunks = await db.agent_knowledge.find(
            {"agent_id": agent_id, "workspace_id": ws_id, "flagged": {"$ne": True}},
            {"_id": 0, "bm25_vector": 0}
        ).to_list(500)

        sessions = await db.agent_training_sessions.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(50)

        pack = {
            "format": "nexus_knowledge_pack_v1",
            "exported_at": now_iso(),
            "exported_by": user["user_id"],
            "agent": agent or {"agent_id": agent_id},
            "chunks": chunks,
            "sessions": sessions,
            "stats": {
                "total_chunks": len(chunks),
                "total_sessions": len(sessions),
                "topics": list(set(c.get("topic", "") for c in chunks if c.get("topic"))),
            },
        }

        from nexus_utils import sanitize_filename as _sfn
        return JSONResponse(content=pack, headers={
            "Content-Disposition": f"attachment; filename=knowledge_{_sfn(agent_id)}.json"
        })

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/knowledge/import")
    async def import_knowledge(ws_id: str, agent_id: str, request: Request, file: UploadFile = File(...)):
        """Import a knowledge pack into an agent."""
        user = await get_current_user(request)

        content = await file.read()
        try:
            pack = json.loads(content)
        except json.JSONDecodeError:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON file"})

        if pack.get("format") != "nexus_knowledge_pack_v1":
            return JSONResponse(status_code=400, content={"error": "Unsupported format. Expected nexus_knowledge_pack_v1"})

        chunks = pack.get("chunks") or []
        if not chunks:
            return JSONResponse(status_code=400, content={"error": "No chunks in pack"})

        imported = 0
        skipped = 0
        session_id = f"import_{uuid.uuid4().hex[:12]}"

        for chunk in chunks:
            # Check for duplicate by content hash
            existing = await db.agent_knowledge.find_one({
                "agent_id": agent_id, "workspace_id": ws_id,
                "content": chunk.get("content", "")
            })
            if existing:
                skipped += 1
                continue

            new_chunk = {
                "chunk_id": f"kc_{uuid.uuid4().hex[:12]}",
                "agent_id": agent_id,
                "workspace_id": ws_id,
                "session_id": session_id,
                "content": chunk.get("content", ""),
                "summary": chunk.get("summary", chunk.get("content", "")[:200]),
                "topic": chunk.get("topic", "imported"),
                "category": chunk.get("category", "general"),
                "tags": chunk.get("tags") or [],
                "source": {"type": "import", "original": chunk.get("source") or {}},
                "tokens": chunk.get("tokens") or [],
                "token_count": chunk.get("token_count", 0),
                "quality_score": chunk.get("quality_score", 0.5),
                "flagged": False,
                "times_retrieved": 0,
                "created_at": now_iso(),
                "imported_from": (pack.get("agent") or {}).get("agent_id", "unknown"),
            }
            await db.agent_knowledge.insert_one(new_chunk)
            imported += 1

        # Log the import session
        await db.agent_training_sessions.insert_one({
            "session_id": session_id,
            "agent_id": agent_id,
            "workspace_id": ws_id,
            "status": "completed",
            "source_type": "import",
            "title": f"Imported from {pack.get('agent', {}).get('name', 'unknown')}",
            "total_chunks": imported,
            "created_by": user["user_id"],
            "created_at": now_iso(),
            "completed_at": now_iso(),
        })

        # Trigger embedding recomputation
        try:
            from ai_embeddings import compute_and_store_embeddings
            await compute_and_store_embeddings(db, agent_id, ws_id)
        except Exception as e:
            logger.warning(f"Non-critical error at line 128: {e}")

        return {
            "session_id": session_id,
            "imported": imported,
            "skipped_duplicates": skipped,
            "total_in_pack": len(chunks),
        }
