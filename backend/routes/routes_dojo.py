"""Dojo Routes — REST API for Agent Dojo sessions, scenarios, extraction.

Follows the Nexus route registration pattern:
  register_dojo_routes(api_router, db, get_current_user)

All endpoints enforce workspace access via require_workspace_access.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from nexus_utils import now_iso

logger = logging.getLogger("routes_dojo")


# ─── Request Models ─────────────────────────────────────

class DojoAgentDef(BaseModel):
    agent_id: str
    role: str = "Assistant"
    role_prompt: str = ""
    domain: str = ""
    methodology: str = ""
    base_model: str = "claude"
    is_driver: bool = False


class DojoTaskDef(BaseModel):
    description: str = Field(..., min_length=10)
    success_criteria: str = ""
    domain: str = "general"
    max_turns: int = 50


class CreateDojoSession(BaseModel):
    scenario_id: Optional[str] = None
    agents: List[DojoAgentDef] = Field(..., min_length=2, max_length=4)
    task: DojoTaskDef
    config: Dict = {}
    auto_start: bool = False
    specify_task: bool = False


class CreateDojoScenario(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    category: str = "engineering"
    roles: List[Dict] = []
    default_task: Dict = {}
    config_defaults: Dict = {}
    skill_alignment: List[str] = []


# ─── Route Registration ────────────────────────────────

def register_dojo_routes(api_router, db, get_current_user):

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    # ════════ SESSION CRUD ═════════════════════════════

    @api_router.post("/workspaces/{ws_id}/dojo/sessions")
    async def create_session(ws_id: str, data: CreateDojoSession,
                              request: Request, bg: BackgroundTasks):
        user = await _authed(request, ws_id)
        session_id = f"dojo_ses_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # Optional: AI-powered task specification (CAMEL pattern)
        task_dict = data.task.dict()
        if data.specify_task:
            from dojo_prompts import specify_task
            roles = [a.role for a in data.agents]
            task_dict["description"] = await specify_task(
                db, task_dict["description"],
                roles[0], roles[1] if len(roles) > 1 else roles[0], ws_id,
            )

        agents = [a.dict() for a in data.agents]
        config = {
            "max_turns": data.task.max_turns,
            "cost_cap_usd": data.config.get("cost_cap_usd", 2.0),
            "turn_timeout_sec": data.config.get("turn_timeout_sec", 120),
            "session_timeout_sec": data.config.get("session_timeout_sec", 600),
            "temperature": data.config.get("temperature", 0.7),
            **data.config,
        }

        session = {
            "session_id": session_id, "workspace_id": ws_id,
            "scenario_id": data.scenario_id or "",
            "status": "draft",
            "agents": agents, "task": task_dict, "config": config,
            "turns": [], "turn_count": 0,
            "termination": None, "synthetic_data": None,
            "cost_tracking": {"total_cost_usd": 0, "per_agent": {}},
            "created_by": user["user_id"],
            "created_at": now, "updated_at": now,
        }
        await db.dojo_sessions.insert_one(session)
        session.pop("_id", None)

        if data.auto_start:
            from dojo_engine import DojoEngine
            engine = DojoEngine(db)
            bg.add_task(engine.run_session, session_id)
            session["status"] = "running"
            await db.dojo_sessions.update_one(
                {"session_id": session_id}, {"$set": {"status": "running"}}
            )

        return session

    @api_router.get("/workspaces/{ws_id}/dojo/sessions")
    async def list_sessions(ws_id: str, request: Request,
                             status: str = None, limit: int = 20):
        await _authed(request, ws_id)
        query = {"workspace_id": ws_id}
        if status:
            query["status"] = status
        sessions = await db.dojo_sessions.find(
            query, {"_id": 0, "turns": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"sessions": sessions}

    @api_router.get("/dojo/sessions/{session_id}")
    async def get_session(session_id: str, request: Request):
        await get_current_user(request)
        s = await db.dojo_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        return s

    @api_router.post("/dojo/sessions/{session_id}/start")
    async def start_session(session_id: str, request: Request, bg: BackgroundTasks):
        user = await get_current_user(request)
        s = await db.dojo_sessions.find_one(
            {"session_id": session_id}, {"status": 1, "workspace_id": 1}
        )
        if not s:
            raise HTTPException(404, "Session not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, s["workspace_id"])
        if s.get("status") != "draft":
            raise HTTPException(400, "Session is not in draft status")
        from dojo_engine import DojoEngine
        engine = DojoEngine(db)
        bg.add_task(engine.run_session, session_id)
        await db.dojo_sessions.update_one(
            {"session_id": session_id}, {"$set": {"status": "running"}}
        )
        return {"session_id": session_id, "status": "running"}

    @api_router.post("/dojo/sessions/{session_id}/pause")
    async def pause_session(session_id: str, request: Request):
        user = await get_current_user(request)
        s = await db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "workspace_id": 1})
        if not s:
            raise HTTPException(404, "Session not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, s["workspace_id"])
        await db.dojo_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "paused", "updated_at": now_iso()}}
        )
        return {"session_id": session_id, "status": "paused"}

    @api_router.post("/dojo/sessions/{session_id}/resume")
    async def resume_session(session_id: str, request: Request, bg: BackgroundTasks):
        user = await get_current_user(request)
        s = await db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "workspace_id": 1})
        if not s:
            raise HTTPException(404, "Session not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, s["workspace_id"])
        from dojo_engine import DojoEngine
        engine = DojoEngine(db)
        await db.dojo_sessions.update_one(
            {"session_id": session_id}, {"$set": {"status": "running"}}
        )
        bg.add_task(engine.run_session, session_id)
        return {"session_id": session_id, "status": "running"}

    @api_router.post("/dojo/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str, request: Request):
        user = await get_current_user(request)
        s = await db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0, "workspace_id": 1})
        if not s:
            raise HTTPException(404, "Session not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, s["workspace_id"])
        await db.dojo_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "cancelled", "updated_at": now_iso()}}
        )
        return {"session_id": session_id, "status": "cancelled"}

    @api_router.delete("/dojo/sessions/{session_id}")
    async def delete_session(session_id: str, request: Request):
        user = await get_current_user(request)
        s = await db.dojo_sessions.find_one({"session_id": session_id}, {"_id": 0, "workspace_id": 1})
        if not s:
            raise HTTPException(404)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, s.get("workspace_id", ""))
        from recycle_bin import soft_delete
        await soft_delete(
            db, "dojo_sessions", {"session_id": session_id},
            user["user_id"], s.get("workspace_id", ""),
        )
        return {"deleted": session_id}

    @api_router.post("/dojo/sessions/{session_id}/fork")
    async def fork_session(session_id: str, request: Request):
        """Fork a session from a specific turn to create a branch."""
        user = await get_current_user(request)
        original = await db.dojo_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not original:
            raise HTTPException(404, "Session not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, original["workspace_id"])
        body = await request.json()
        fork_at_turn = body.get("fork_at_turn", None)
        new_id = f"dojo_ses_{uuid.uuid4().hex[:12]}"
        turns = original.get("turns") or []
        if fork_at_turn is not None:
            turns = [t for t in turns if t.get("turn_number", 0) <= fork_at_turn]
        forked = {
            **original,
            "session_id": new_id,
            "status": "draft",
            "turns": turns,
            "turn_count": len(turns),
            "termination": None,
            "synthetic_data": None,
            "cost_tracking": {"total_cost_usd": 0, "per_agent": {}},
            "forked_from": {"session_id": session_id, "at_turn": fork_at_turn},
            "created_by": user["user_id"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await db.dojo_sessions.insert_one(forked)
        forked.pop("_id", None)
        return forked

    # ════════ SCENARIO ENDPOINTS ═══════════════════════

    @api_router.get("/dojo/scenarios")
    async def list_scenarios(request: Request, ws_id: str = None):
        await get_current_user(request)
        from dojo_scenarios import get_all_scenarios
        builtin = get_all_scenarios()
        custom = []
        if ws_id:
            custom = await db.dojo_scenarios.find(
                {"workspace_id": ws_id}, {"_id": 0}
            ).to_list(50)
        return {"scenarios": builtin + custom}

    @api_router.post("/workspaces/{ws_id}/dojo/scenarios")
    async def create_scenario(ws_id: str, data: CreateDojoScenario, request: Request):
        user = await _authed(request, ws_id)
        sc_id = f"dojo_sc_{uuid.uuid4().hex[:12]}"
        scenario = {
            "scenario_id": sc_id, "workspace_id": ws_id,
            "name": data.name, "description": data.description,
            "category": data.category, "roles": data.roles,
            "default_task": data.default_task,
            "config_defaults": data.config_defaults,
            "skill_alignment": data.skill_alignment,
            "is_builtin": False,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.dojo_scenarios.insert_one(scenario)
        scenario.pop("_id", None)
        return scenario

    @api_router.post("/dojo/scenarios/{scenario_id}/clone")
    async def clone_scenario(scenario_id: str, request: Request):
        """Clone a built-in scenario for workspace customization."""
        user = await get_current_user(request)
        body = await request.json()
        ws_id = body.get("workspace_id", "")
        if not ws_id:
            raise HTTPException(400, "workspace_id required")

        from dojo_scenarios import get_scenario
        original = get_scenario(scenario_id)
        if not original:
            src = await db.dojo_scenarios.find_one(
                {"scenario_id": scenario_id}, {"_id": 0}
            )
            if not src:
                raise HTTPException(404, "Scenario not found")
            original = src

        new_id = f"dojo_sc_{uuid.uuid4().hex[:12]}"
        clone = {
            **original,
            "scenario_id": new_id,
            "workspace_id": ws_id,
            "name": f"{original['name']} (Custom)",
            "is_builtin": False,
            "cloned_from": scenario_id,
            "created_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.dojo_scenarios.insert_one(clone)
        clone.pop("_id", None)
        return clone

    # ════════ DATA EXTRACTION ENDPOINTS ════════════════

    @api_router.post("/dojo/sessions/{session_id}/extract")
    async def extract_data(session_id: str, request: Request):
        await get_current_user(request)
        from dojo_data_extractor import extract_training_data
        ext_id = await extract_training_data(db, session_id)
        if not ext_id:
            raise HTTPException(400, "No data extracted (session incomplete or too short)")
        return {"extraction_id": ext_id}

    @api_router.get("/dojo/sessions/{session_id}/extracted-data")
    async def get_extracted(session_id: str, request: Request):
        await get_current_user(request)
        ext = await db.dojo_extracted_data.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not ext:
            raise HTTPException(404, "No extraction found")
        return ext

    @api_router.post("/dojo/extracted/{extraction_id}/approve")
    async def approve_extracted(extraction_id: str, request: Request):
        await get_current_user(request)
        await db.dojo_extracted_data.update_one(
            {"extraction_id": extraction_id}, {"$set": {"status": "approved"}}
        )
        return {"status": "approved"}

    @api_router.post("/dojo/extracted/{extraction_id}/reject")
    async def reject_extracted(extraction_id: str, request: Request):
        await get_current_user(request)
        await db.dojo_extracted_data.update_one(
            {"extraction_id": extraction_id}, {"$set": {"status": "rejected"}}
        )
        return {"status": "rejected"}

    @api_router.post("/dojo/extracted/{extraction_id}/ingest")
    async def ingest_extracted(extraction_id: str, request: Request):
        await get_current_user(request)
        from dojo_data_extractor import ingest_extracted_data
        chunk_ids = await ingest_extracted_data(db, extraction_id)
        return {"ingested": len(chunk_ids) if chunk_ids else 0, "chunk_ids": chunk_ids or []}

    # ════════ ANALYTICS ════════════════════════════════

    @api_router.get("/workspaces/{ws_id}/dojo/analytics")
    async def dojo_analytics(ws_id: str, request: Request):
        await _authed(request, ws_id)
        total = await db.dojo_sessions.count_documents({"workspace_id": ws_id})
        completed = await db.dojo_sessions.count_documents(
            {"workspace_id": ws_id, "status": "completed"}
        )
        pipeline = [
            {"$match": {"workspace_id": ws_id}},
            {"$group": {
                "_id": None,
                "total_cost": {"$sum": "$cost_tracking.total_cost_usd"},
                "total_pairs": {"$sum": "$synthetic_data.pairs_extracted"},
                "avg_quality": {"$avg": "$synthetic_data.quality_avg"},
            }},
        ]
        agg = await db.dojo_sessions.aggregate(pipeline).to_list(1)
        stats = agg[0] if agg else {}
        return {
            "total_sessions": total,
            "completed_sessions": completed,
            "completion_rate": round(completed / total, 2) if total else 0,
            "total_cost_usd": round(stats.get("total_cost", 0), 4),
            "total_pairs_extracted": stats.get("total_pairs", 0),
            "avg_quality": round(stats.get("avg_quality", 0), 3),
        }
