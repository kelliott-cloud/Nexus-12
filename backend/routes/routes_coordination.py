from nexus_utils import now_iso
"""Agent Coordination Protocol — TPM-directed work queue and shared workspace memory.

Prevents duplicate work by:
1. TPM assigns work items to specific agents — others PAUSE until assigned
2. Shared memory store agents read/write for visibility
3. Dedup checks before project/task creation
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)



def register_coordination_routes(api_router, db, get_current_user):

    # ============ Work Queue (TPM Assigns, Agents Execute) ============

    @api_router.get("/workspaces/{ws_id}/work-queue")
    async def get_work_queue(ws_id: str, request: Request, agent_key: str = None, status: str = None):
        user = await get_current_user(request)
        query = {"workspace_id": ws_id}
        if agent_key:
            query["assigned_to"] = agent_key
        if status:
            query["status"] = status
        items = await db.work_queue.find(query, {"_id": 0}).sort("priority", 1).to_list(100)
        return items

    @api_router.post("/workspaces/{ws_id}/work-queue")
    async def create_work_item(ws_id: str, request: Request):
        """TPM creates a work item and assigns it to a specific agent."""
        user = await get_current_user(request)
        body = await request.json()
        
        item_id = f"wq_{uuid.uuid4().hex[:12]}"
        item = {
            "item_id": item_id,
            "workspace_id": ws_id,
            "title": body.get("title", ""),
            "description": body.get("description", ""),
            "assigned_to": body.get("assigned_to", ""),
            "project_id": body.get("project_id", ""),
            "priority": body.get("priority", 5),
            "status": "pending",
            "created_by": body.get("created_by", user["user_id"]),
            "claimed_at": None,
            "completed_at": None,
            "result_summary": None,
            "created_at": now_iso(),
        }
        await db.work_queue.insert_one(item)
        item.pop("_id", None)
        return item

    @api_router.put("/work-queue/{item_id}/claim")
    async def claim_work_item(item_id: str, request: Request):
        """Agent claims a work item assigned to them."""
        user = await get_current_user(request)
        body = await request.json()
        agent_key = body.get("agent_key", "")
        
        item = await db.work_queue.find_one({"item_id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Work item not found")
        if item["status"] != "pending":
            raise HTTPException(400, f"Work item already {item['status']}")
        if item["assigned_to"] and item["assigned_to"] != agent_key:
            raise HTTPException(403, f"Work item assigned to {item['assigned_to']}, not {agent_key}")
        
        await db.work_queue.update_one(
            {"item_id": item_id},
            {"$set": {"status": "in_progress", "claimed_at": now_iso(), "assigned_to": agent_key}}
        )
        return {"message": "Claimed", "item_id": item_id}

    @api_router.put("/work-queue/{item_id}/complete")
    async def complete_work_item(item_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        await db.work_queue.update_one(
            {"item_id": item_id},
            {"$set": {
                "status": "completed",
                "completed_at": now_iso(),
                "result_summary": body.get("result_summary", "")[:500],
            }}
        )
        return {"message": "Completed", "item_id": item_id}

    # ============ Shared Workspace Memory ============

    @api_router.get("/workspaces/{ws_id}/memory")
    async def get_workspace_memory(ws_id: str, request: Request, namespace: str = None):
        user = await get_current_user(request)
        query = {"workspace_id": ws_id}
        if namespace:
            query["namespace"] = namespace
        entries = await db.workspace_memory.find(query, {"_id": 0}).sort("updated_at", -1).to_list(200)
        return entries

    @api_router.post("/workspaces/{ws_id}/memory")
    async def set_workspace_memory(ws_id: str, request: Request):
        """Agents write their current state to shared memory."""
        user = await get_current_user(request)
        body = await request.json()
        key = body.get("key", "")
        if not key:
            raise HTTPException(400, "Key is required")
        
        await db.workspace_memory.update_one(
            {"workspace_id": ws_id, "key": key},
            {"$set": {
                "workspace_id": ws_id,
                "key": key,
                "value": body.get("value", ""),
                "namespace": body.get("namespace", "agent_state"),
                "agent_key": body.get("agent_key", ""),
                "updated_by": body.get("updated_by", "system"),
                "updated_at": now_iso(),
            }},
            upsert=True,
        )
        return {"message": "Saved", "key": key}

    @api_router.delete("/workspaces/{ws_id}/memory/{key}")
    async def delete_workspace_memory(ws_id: str, key: str, request: Request):
        user = await get_current_user(request)
        await db.workspace_memory.delete_one({"workspace_id": ws_id, "key": key})
        return {"message": "Deleted"}

    # ============ Project Dedup Check ============

    @api_router.post("/workspaces/{ws_id}/check-duplicate")
    async def check_duplicate(ws_id: str, request: Request):
        """Check if a project or task name is too similar to an existing one."""
        user = await get_current_user(request)
        body = await request.json()
        name = body.get("name", "").strip().lower()
        entity_type = body.get("type", "project")
        
        if not name:
            return {"is_duplicate": False}
        
        if entity_type == "project":
            existing = await db.projects.find(
                {"workspace_id": ws_id}, {"_id": 0, "name": 1, "project_id": 1, "status": 1}
            ).to_list(50)
        else:
            existing = await db.project_tasks.find(
                {"workspace_id": ws_id}, {"_id": 0, "title": 1, "task_id": 1, "status": 1}
            ).to_list(200)
        
        matches = []
        for item in existing:
            existing_name = (item.get("name") or item.get("title", "")).strip().lower()
            similarity = SequenceMatcher(None, name, existing_name).ratio()
            if similarity > 0.7:
                matches.append({
                    "id": item.get("project_id") or item.get("task_id"),
                    "name": item.get("name") or item.get("title"),
                    "status": item.get("status", ""),
                    "similarity": round(similarity, 2),
                })
        
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return {
            "is_duplicate": len(matches) > 0,
            "matches": matches[:5],
            "suggestion": f"Use existing '{matches[0]['name']}' (ID: {matches[0]['id']})" if matches else "",
        }

    # ============ Agent Coordination Status ============

    @api_router.get("/workspaces/{ws_id}/coordination-status")
    async def get_coordination_status(ws_id: str, request: Request):
        """Full coordination overview: who's working on what, pending assignments, memory state."""
        user = await get_current_user(request)
        
        # Active work items
        queue = await db.work_queue.find(
            {"workspace_id": ws_id, "status": {"$in": ["pending", "in_progress"]}},
            {"_id": 0}
        ).sort("priority", 1).to_list(50)
        
        # Agent states from memory
        agent_states = await db.workspace_memory.find(
            {"workspace_id": ws_id, "namespace": "agent_state"},
            {"_id": 0}
        ).to_list(20)
        
        # Project summary
        projects = await db.projects.find(
            {"workspace_id": ws_id}, {"_id": 0, "project_id": 1, "name": 1, "status": 1}
        ).to_list(50)
        
        # Recent completions
        completed = await db.work_queue.find(
            {"workspace_id": ws_id, "status": "completed"},
            {"_id": 0}
        ).sort("completed_at", -1).limit(10).to_list(10)
        
        return {
            "pending_assignments": [q for q in queue if q["status"] == "pending"],
            "in_progress": [q for q in queue if q["status"] == "in_progress"],
            "agent_states": {s["key"]: s for s in agent_states},
            "projects": projects,
            "recent_completions": completed,
        }


    # ============ TPM Queue ============

    @api_router.get("/workspaces/{ws_id}/tpm-queue")
    async def get_tpm_queue(ws_id: str, request: Request, agent_key: str = None, status: str = "active"):
        """Get TPM directives. Agents reference this before responding."""
        user = await get_current_user(request)
        query = {"workspace_id": ws_id, "status": status}
        if agent_key:
            query["$or"] = [{"target_agent": agent_key}, {"target_agent": "all"}]
        directives = await db.tpm_queue.find(query, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"directives": directives}

    @api_router.post("/workspaces/{ws_id}/tpm-queue")
    async def post_tpm_directive(ws_id: str, request: Request):
        """TPM posts a directive for agents to follow."""
        user = await get_current_user(request)
        body = await request.json()
        directive = body.get("directive", "").strip()
        if not directive:
            raise HTTPException(400, "Directive text required")
        target = body.get("target_agent", "all")
        priority = body.get("priority", "normal")
        if priority not in ["critical", "high", "normal", "low"]:
            priority = "normal"
        
        doc = {
            "directive_id": f"tpmd_{uuid.uuid4().hex[:12]}",
            "workspace_id": ws_id,
            "directive": directive[:1000],
            "context": body.get("context", "")[:500],
            "target_agent": target,
            "priority": priority,
            "status": "active",
            "posted_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.tpm_queue.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @api_router.put("/workspaces/{ws_id}/tpm-queue/{directive_id}/complete")
    async def complete_tpm_directive(ws_id: str, directive_id: str, request: Request):
        """Mark a TPM directive as completed."""
        user = await get_current_user(request)
        await db.tpm_queue.update_one(
            {"directive_id": directive_id, "workspace_id": ws_id},
            {"$set": {"status": "completed", "completed_at": now_iso()}}
        )
        return {"message": "Directive completed"}

    # ============ Ask TPM ============

    @api_router.post("/workspaces/{ws_id}/ask-tpm")
    async def ask_tpm(ws_id: str, request: Request):
        """Agent requests direction from the TPM. Creates a work item for the TPM to address."""
        user = await get_current_user(request)
        body = await request.json()
        question = body.get("question", "").strip()
        from_agent = body.get("from_agent", "unknown")
        if not question:
            raise HTTPException(400, "Question required")
        
        # Create a work item assigned to TPM
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "tpm_agent_id": 1})
        tpm_id = (ws or {}).get("tpm_agent_id")
        if not tpm_id:
            return {"message": "No TPM designated in this workspace", "queued": False}
        
        tpm_agent = await db.nexus_agents.find_one({"agent_id": tpm_id}, {"_id": 0, "base_model": 1, "name": 1})
        tpm_key = (tpm_agent or {}).get("base_model", "")
        
        item = {
            "item_id": f"wq_{uuid.uuid4().hex[:12]}",
            "workspace_id": ws_id,
            "title": f"Direction requested by {from_agent}: {question[:100]}",
            "description": question,
            "assigned_to": tpm_key,
            "priority": 1,
            "status": "pending",
            "item_type": "tpm_question",
            "from_agent": from_agent,
            "created_at": now_iso(),
        }
        await db.work_queue.insert_one(item)
        item.pop("_id", None)
        return {"message": f"Question queued for TPM ({(tpm_agent or {}).get('name', 'TPM')})", "queued": True, "item": item}

