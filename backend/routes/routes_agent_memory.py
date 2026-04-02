"""Agent Memory — Persistent context memory scoped to workspace, project, and org levels.

Three memory tiers:
1. Channel Memory — conversation context within a channel
2. Project Memory — domain knowledge across all project channels
3. Organization Memory — company-wide facts, style guides, terminology
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



from nexus_utils import now_iso, safe_regex

def register_agent_memory_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/agent-memory")
    async def get_agent_memories(ws_id: str, request: Request, scope: str = None, agent_key: str = None, limit: int = 50):
        user = await get_current_user(request)
        query = {"workspace_id": ws_id}
        if scope:
            query["scope"] = scope
        if agent_key:
            query["agent_key"] = agent_key
        
        memories = await db.agent_memory.find(query, {"_id": 0}).sort("updated_at", -1).limit(limit).to_list(limit)
        return {"memories": memories, "total": len(memories)}

    @api_router.post("/workspaces/{ws_id}/agent-memory")
    async def save_memory(ws_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        
        memory = {
            "memory_id": mem_id,
            "workspace_id": ws_id,
            "scope": body.get("scope", "channel"),
            "scope_id": body.get("scope_id", ""),
            "agent_key": body.get("agent_key", ""),
            "category": body.get("category", "fact"),
            "content": body.get("content", ""),
            "source_message_id": body.get("source_message_id", ""),
            "confidence": body.get("confidence", 1.0),
            "tags": body.get("tags") or [],
            "created_by": body.get("created_by", user["user_id"]),
            "created_at": now,
            "updated_at": now,
        }
        await db.agent_memory.insert_one(memory)
        memory.pop("_id", None)
        return memory

    @api_router.put("/agent-memory/{mem_id}")
    async def update_memory(mem_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        update = {"updated_at": now_iso()}
        for f in ["content", "category", "tags", "confidence"]:
            if f in body:
                update[f] = body[f]
        await db.agent_memory.update_one({"memory_id": mem_id}, {"$set": update})
        return {"updated": mem_id}

    @api_router.delete("/agent-memory/{mem_id}")
    async def delete_memory(mem_id: str, request: Request):
        user = await get_current_user(request)
        await db.agent_memory.delete_one({"memory_id": mem_id})
        return {"deleted": mem_id}

    @api_router.get("/workspaces/{ws_id}/agent-memory/search")
    async def search_memory(ws_id: str, request: Request, q: str = "", scope: str = None):
        """Search agent memories by content."""
        user = await get_current_user(request)
        query = {"workspace_id": ws_id, "content": {"$regex": safe_regex(q), "$options": "i"}}
        if scope:
            query["scope"] = scope
        memories = await db.agent_memory.find(query, {"_id": 0}).limit(20).to_list(20)
        return {"results": memories, "query": q}

    @api_router.get("/workspaces/{ws_id}/agent-memory/context")
    async def get_memory_context(ws_id: str, request: Request, channel_id: str = "", project_id: str = ""):
        """Build full memory context for an agent — combines all three tiers."""
        user = await get_current_user(request)
        
        context_parts = []
        
        # Tier 1: Channel memory
        if channel_id:
            ch_mems = await db.agent_memory.find(
                {"workspace_id": ws_id, "scope": "channel", "scope_id": channel_id},
                {"_id": 0, "content": 1, "category": 1}
            ).limit(20).to_list(20)
            if ch_mems:
                context_parts.append("CHANNEL MEMORY:")
                for m in ch_mems:
                    context_parts.append(f"  [{m.get('category', 'fact')}] {m['content']}")
        
        # Tier 2: Project memory
        if project_id:
            proj_mems = await db.agent_memory.find(
                {"workspace_id": ws_id, "scope": "project", "scope_id": project_id},
                {"_id": 0, "content": 1, "category": 1}
            ).limit(15).to_list(15)
            if proj_mems:
                context_parts.append("PROJECT MEMORY:")
                for m in proj_mems:
                    context_parts.append(f"  [{m.get('category', 'fact')}] {m['content']}")
        
        # Tier 3: Organization/workspace memory
        org_mems = await db.agent_memory.find(
            {"workspace_id": ws_id, "scope": "organization"},
            {"_id": 0, "content": 1, "category": 1}
        ).limit(10).to_list(10)
        if org_mems:
            context_parts.append("ORGANIZATION MEMORY:")
            for m in org_mems:
                context_parts.append(f"  [{m.get('category', 'fact')}] {m['content']}")
        
        return {
            "context": "\n".join(context_parts),
            "channel_memories": len([m for m in context_parts if "CHANNEL" in m]),
            "project_memories": len([m for m in context_parts if "PROJECT" in m]),
            "org_memories": len([m for m in context_parts if "ORG" in m]),
        }
