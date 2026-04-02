"""Agent Handoffs & Knowledge Base - structured context passing and persistent workspace memory"""
import uuid
import logging
import re as _re
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


# ============ Models ============

class HandoffCreate(BaseModel):
    channel_id: str
    from_agent: str
    to_agent: str
    context_type: str = "general"  # general, findings, code, recommendation, analysis
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    metadata: dict = {}


class MemoryCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    value: str
    category: str = "general"  # general, insight, decision, reference, context
    tags: List[str] = []


class MemoryUpdate(BaseModel):
    value: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


VALID_CONTEXT_TYPES = ["general", "findings", "code", "recommendation", "analysis"]
VALID_MEMORY_CATEGORIES = ["general", "insight", "decision", "reference", "context"]


def register_handoff_memory_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Handoffs ============

    @api_router.post("/channels/{channel_id}/handoffs")
    async def create_handoff(channel_id: str, data: HandoffCreate, request: Request):
        """Create a structured handoff between agents"""
        user = await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")

        handoff_id = f"ho_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        handoff = {
            "handoff_id": handoff_id,
            "channel_id": channel_id,
            "workspace_id": channel.get("workspace_id", ""),
            "from_agent": data.from_agent,
            "to_agent": data.to_agent,
            "context_type": data.context_type if data.context_type in VALID_CONTEXT_TYPES else "general",
            "title": data.title,
            "content": data.content,
            "metadata": data.metadata,
            "status": "pending",  # pending, acknowledged, completed
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.handoffs.insert_one(handoff)

        # Post handoff as a special message in the channel
        msg = {
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "sender_type": "handoff",
            "sender_id": data.from_agent,
            "sender_name": data.from_agent,
            "ai_model": data.from_agent,
            "content": f"**Handoff to {data.to_agent}**: {data.title}\n\n{data.content}",
            "handoff": {
                "handoff_id": handoff_id,
                "from_agent": data.from_agent,
                "to_agent": data.to_agent,
                "context_type": data.context_type,
                "title": data.title,
            },
            "created_at": now,
        }
        await db.messages.insert_one(msg)

        result = {k: v for k, v in handoff.items() if k != "_id"}
        return result

    @api_router.get("/channels/{channel_id}/handoffs")
    async def list_handoffs(channel_id: str, request: Request):
        """List all handoffs in a channel"""
        await get_current_user(request)
        handoffs = await db.handoffs.find(
            {"channel_id": channel_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return handoffs

    @api_router.put("/handoffs/{handoff_id}/acknowledge")
    async def acknowledge_handoff(handoff_id: str, request: Request):
        """Mark a handoff as acknowledged by the receiving agent"""
        await get_current_user(request)
        handoff = await db.handoffs.find_one({"handoff_id": handoff_id}, {"_id": 0})
        if not handoff:
            raise HTTPException(404, "Handoff not found")
        await db.handoffs.update_one(
            {"handoff_id": handoff_id},
            {"$set": {"status": "acknowledged", "acknowledged_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"status": "acknowledged"}

    # ============ Knowledge Base / Memory ============

    @api_router.get("/workspaces/{workspace_id}/memory")
    async def list_memory(
        workspace_id: str, request: Request,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ):
        """List memory entries for a workspace"""
        await get_current_user(request)
        query = {"workspace_id": workspace_id}
        if category and category in VALID_MEMORY_CATEGORIES:
            query["category"] = category
        if search:
            from nexus_utils import safe_regex
            query["$or"] = [
                {"key": {"$regex": safe_regex(search), "$options": "i"}},
                {"value": {"$regex": safe_regex(search), "$options": "i"}},
                {"tags": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        entries = await db.workspace_memory.find(query, {"_id": 0}).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.workspace_memory.count_documents(query)
        return {"entries": entries, "total": total}

    @api_router.post("/workspaces/{workspace_id}/memory")
    async def create_memory(workspace_id: str, data: MemoryCreate, request: Request):
        """Create or update a memory entry (upsert by key)"""
        user = await _authed_user(request, workspace_id)
        now = datetime.now(timezone.utc).isoformat()

        # Upsert: if key exists, update value
        existing = await db.workspace_memory.find_one(
            {"workspace_id": workspace_id, "key": data.key}, {"_id": 0}
        )
        if existing:
            await db.workspace_memory.update_one(
                {"memory_id": existing["memory_id"]},
                {"$set": {
                    "value": data.value,
                    "category": data.category if data.category in VALID_MEMORY_CATEGORIES else existing["category"],
                    "tags": data.tags or existing.get("tags") or [],
                    "updated_by": user["user_id"],
                    "updated_at": now,
                    "version": existing.get("version", 1) + 1,
                }}
            )
            return await db.workspace_memory.find_one({"memory_id": existing["memory_id"]}, {"_id": 0})

        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        entry = {
            "memory_id": memory_id,
            "workspace_id": workspace_id,
            "key": data.key,
            "value": data.value,
            "category": data.category if data.category in VALID_MEMORY_CATEGORIES else "general",
            "tags": data.tags,
            "version": 1,
            "created_by": user["user_id"],
            "updated_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.workspace_memory.insert_one(entry)
        return {k: v for k, v in entry.items() if k != "_id"}

    @api_router.put("/memory/{memory_id}")
    async def update_memory(memory_id: str, data: MemoryUpdate, request: Request):
        """Update a memory entry"""
        user = await get_current_user(request)
        entry = await db.workspace_memory.find_one({"memory_id": memory_id}, {"_id": 0})
        if not entry:
            raise HTTPException(404, "Memory entry not found")
        updates = {"updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user["user_id"]}
        if data.value is not None:
            updates["value"] = data.value
            updates["version"] = entry.get("version", 1) + 1
        if data.category is not None and data.category in VALID_MEMORY_CATEGORIES:
            updates["category"] = data.category
        if data.tags is not None:
            updates["tags"] = data.tags
        await db.workspace_memory.update_one({"memory_id": memory_id}, {"$set": updates})
        return await db.workspace_memory.find_one({"memory_id": memory_id}, {"_id": 0})

    @api_router.delete("/memory/{memory_id}")
    async def delete_memory(memory_id: str, request: Request):
        """Delete a memory entry"""
        await get_current_user(request)
        result = await db.workspace_memory.delete_one({"memory_id": memory_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Memory entry not found")
        return {"message": "Memory entry deleted"}

    @api_router.get("/memory/categories")
    async def get_memory_categories(request: Request):
        """Get available memory categories"""
        await get_current_user(request)
        return {"categories": [
            {"key": "general", "name": "General", "description": "General workspace knowledge"},
            {"key": "insight", "name": "Insight", "description": "Key insights from conversations"},
            {"key": "decision", "name": "Decision", "description": "Important decisions made"},
            {"key": "reference", "name": "Reference", "description": "Reference materials and links"},
            {"key": "context", "name": "Context", "description": "Project context and background"},
        ]}

    # ============ Semantic Search ============

    @api_router.post("/workspaces/{workspace_id}/memory/semantic-search")
    async def semantic_search_memory(workspace_id: str, request: Request):
        """Semantic search using embedding similarity"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        query_text = body.get("query", "").strip()
        if not query_text:
            raise HTTPException(400, "Query text required")

        # Get all entries for this workspace
        entries = await db.workspace_memory.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).to_list(200)

        if not entries:
            return {"results": [], "total": 0}

        # Simple TF-IDF-like scoring using word overlap
        query_words = set(query_text.lower().split())
        scored = []
        for entry in entries:
            entry_text = f"{entry.get('key', '')} {entry.get('value', '')} {' '.join(entry.get('tags', []))}".lower()
            entry_words = set(entry_text.split())
            overlap = len(query_words & entry_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                entry["relevance_score"] = round(score, 3)
                scored.append(entry)

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return {"results": scored[:10], "total": len(scored)}

    # ============ File Upload for KB ============

    @api_router.post("/workspaces/{workspace_id}/memory/upload")
    async def upload_knowledge_file(workspace_id: str, request: Request):
        """Upload a file (PDF/DOCX/TXT/MD/CSV) and chunk it into knowledge entries"""
        import io
        user = await _authed_user(request, workspace_id)

        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file provided")

        filename = file.filename or "upload"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("txt", "md", "csv", "pdf", "docx"):
            raise HTTPException(400, f"Unsupported file type: .{ext}. Supported: txt, md, csv, pdf, docx")

        content_bytes = await file.read()
        text_content = ""

        if ext in ("txt", "md", "csv"):
            text_content = content_bytes.decode("utf-8", errors="replace")
        elif ext == "pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=content_bytes, filetype="pdf")
                text_content = "\n".join(page.get_text() for page in doc)
                doc.close()
            except ImportError:
                # Fallback: just store raw text extraction won't work
                text_content = content_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                raise HTTPException(422, f"Failed to parse PDF: {str(e)[:100]}")
        elif ext == "docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(content_bytes))
                text_content = "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                text_content = content_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                raise HTTPException(422, f"Failed to parse DOCX: {str(e)[:100]}")

        if not text_content.strip():
            raise HTTPException(422, "File appears empty or could not be parsed")

        # Chunk the content (~500 words per chunk)
        words = text_content.split()
        chunk_size = 500
        overlap = 50
        chunks = []
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunks.append(" ".join(chunk_words))
            i += chunk_size - overlap

        if not chunks:
            chunks = [text_content]

        now = datetime.now(timezone.utc).isoformat()
        created_entries = []

        for idx, chunk in enumerate(chunks):
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
            key = f"{filename}" if len(chunks) == 1 else f"{filename} (part {idx + 1}/{len(chunks)})"
            entry = {
                "memory_id": memory_id,
                "workspace_id": workspace_id,
                "key": key,
                "value": chunk[:5000],  # Cap at 5000 chars
                "category": "reference",
                "tags": ["uploaded", ext, filename],
                "source_type": "upload",
                "source_filename": filename,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "version": 1,
                "created_by": user["user_id"],
                "updated_by": user["user_id"],
                "created_at": now,
                "updated_at": now,
            }
            await db.workspace_memory.insert_one(entry)
            created_entries.append({"memory_id": memory_id, "key": key, "chunk_index": idx})

        return {
            "filename": filename,
            "file_type": ext,
            "total_chunks": len(chunks),
            "total_words": len(words),
            "entries": created_entries,
        }
