"""Nexus Operator Routes — Session management, execution, templates, analytics."""
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



class OperatorSessionCreate(BaseModel):
    goal: str = Field(..., min_length=5, max_length=5000)
    goal_type: str = "custom"
    channel_id: str = ""
    budget: dict = {}
    auto_approve: bool = False


class PlanModification(BaseModel):
    tasks_to_remove: List[str] = []
    tasks_to_add: List[dict] = []
    budget_override: Optional[dict] = None


class SessionInject(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)
    target_task_id: Optional[str] = None


DEFAULT_BUDGETS = {
    "research": {"max_total_cost_usd": 3.0, "max_per_task_cost_usd": 0.5, "max_browser_tabs": 5, "max_parallel_agents": 5, "max_total_duration_sec": 600, "allow_code_execution": False, "allow_file_writes": True, "auto_validate": True},
    "coding": {"max_total_cost_usd": 5.0, "max_per_task_cost_usd": 1.0, "max_browser_tabs": 2, "max_parallel_agents": 3, "max_total_duration_sec": 900, "allow_code_execution": True, "allow_file_writes": True, "auto_validate": True},
    "analysis": {"max_total_cost_usd": 4.0, "max_per_task_cost_usd": 0.8, "max_browser_tabs": 3, "max_parallel_agents": 4, "max_total_duration_sec": 600, "allow_code_execution": False, "allow_file_writes": True, "auto_validate": True},
    "content": {"max_total_cost_usd": 3.0, "max_per_task_cost_usd": 0.5, "max_browser_tabs": 2, "max_parallel_agents": 3, "max_total_duration_sec": 600, "allow_code_execution": False, "allow_file_writes": True, "auto_validate": False},
    "monitoring": {"max_total_cost_usd": 1.0, "max_per_task_cost_usd": 0.2, "max_browser_tabs": 3, "max_parallel_agents": 3, "max_total_duration_sec": 300, "allow_code_execution": False, "allow_file_writes": False, "auto_validate": False},
    "custom": {"max_total_cost_usd": 5.0, "max_per_task_cost_usd": 1.0, "max_browser_tabs": 5, "max_parallel_agents": 5, "max_total_duration_sec": 600, "allow_code_execution": True, "allow_file_writes": True, "auto_validate": True},
}


def register_operator_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    async def _plan_session(db, session_id, goal, ws_id, auto_approve, budget):
        """Background task: generate task plan."""
        try:
            from operator_engine import OperatorEngine
            engine = OperatorEngine(db)
            plan = await engine.plan_tasks(session_id, goal, ws_id)

            # Validate plan against budget
            pg = plan.get("parallel_groups") or {}
            for gname, gconfig in pg.items():
                if gconfig.get("max_concurrent", 5) > budget.get("max_browser_tabs", 5):
                    pg[gname]["max_concurrent"] = budget["max_browser_tabs"]

            if auto_approve:
                assignments = await engine.dispatch_agents(session_id, plan)
                await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {
                    "status": "executing", "task_plan": plan, "agent_assignments": assignments,
                }})
                await engine.run_session(session_id)
            else:
                assignments = await engine.dispatch_agents(session_id, plan)
                await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {
                    "status": "planned", "task_plan": plan, "agent_assignments": assignments,
                }})
        except Exception as e:
            logger.error(f"Planning failed for {session_id}: {e}")
            await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {
                "status": "failed", "error": f"Planning failed: {str(e)[:300]}", "completed_at": now_iso(),
            }})

    @api_router.post("/workspaces/{ws_id}/operator/sessions")
    async def create_session(ws_id: str, data: OperatorSessionCreate, request: Request, background_tasks: BackgroundTasks):
        user = await _authed_user(request, ws_id)

        # Check concurrent session limit
        active = await db.operator_sessions.count_documents({"workspace_id": ws_id, "status": {"$in": ["planning", "executing"]}})
        if active >= 3:
            raise HTTPException(429, "Maximum 3 concurrent operator sessions per workspace")

        # Merge budget with defaults
        defaults = DEFAULT_BUDGETS.get(data.goal_type, DEFAULT_BUDGETS["custom"])
        budget = {**defaults, **data.budget}

        # Get default channel
        channel_id = data.channel_id
        if not channel_id:
            ch = await db.channels.find_one({"workspace_id": ws_id}, {"_id": 0, "channel_id": 1})
            channel_id = ch["channel_id"] if ch else ""

        session_id = f"ops_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        session = {
            "session_id": session_id, "workspace_id": ws_id,
            "channel_id": channel_id, "status": "planning",
            "goal": data.goal, "goal_type": data.goal_type,
            "task_plan": {}, "agent_assignments": {},
            "budget": budget, "observations": [], "injected_instructions": [],
            "results": None, "error": None,
            "metrics": {"total_cost_usd": 0, "total_tokens_in": 0, "total_tokens_out": 0,
                        "total_duration_ms": 0, "tasks_completed": 0, "tasks_failed": 0,
                        "browser_pages_visited": 0, "tools_used": 0, "parallel_peak": 0},
            "created_by": user["user_id"], "created_at": now, "completed_at": None,
        }
        await db.operator_sessions.insert_one(session)
        session.pop("_id", None)

        # Start planning in background
        background_tasks.add_task(_plan_session, db, session_id, data.goal, ws_id, data.auto_approve, budget)
        return session

    @api_router.get("/workspaces/{ws_id}/operator/sessions")
    async def list_sessions(ws_id: str, request: Request, limit: int = 20):
        await _authed_user(request, ws_id)
        sessions = await db.operator_sessions.find(
            {"workspace_id": ws_id}, {"_id": 0, "session_id": 1, "goal": 1, "goal_type": 1,
             "status": 1, "metrics": 1, "created_at": 1, "completed_at": 1, "task_plan": {"tasks": {"$slice": 0}}}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        # Add task count
        for s in sessions:
            plan = s.pop("task_plan", {})
            s["task_count"] = len(plan.get("tasks") or [])
        return {"sessions": sessions}

    async def _verify_session_access(user, session_id):
        """Verify user has access to the operator session's workspace."""
        s = await db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0, "workspace_id": 1, "user_id": 1})
        if not s:
            raise HTTPException(404, "Session not found")
        ws_id = s.get("workspace_id", "")
        if ws_id:
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, ws_id)
        return s

    @api_router.get("/operator/sessions/{session_id}")
    async def get_session(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        s = await db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        return s

    @api_router.post("/operator/sessions/{session_id}/approve-plan")
    async def approve_plan(session_id: str, request: Request, background_tasks: BackgroundTasks):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        session = await db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Session not found")
        if session.get("status") not in ("planning", "planned"):
            raise HTTPException(400, "Session not in planning/planned state")

        # Parse optional modifications
        body = {}
        try:
            body = await request.json()
        except Exception as e:
            logger.debug(f"Non-JSON body: {e}")

        plan = session.get("task_plan") or {}
        tasks = plan.get("tasks") or []

        # Apply modifications
        if body.get("tasks_to_remove"):
            removed = set(body["tasks_to_remove"])
            tasks = [t for t in tasks if t.get("task_id") not in removed]
            for t in tasks:
                t["depends_on"] = [d for d in t.get("depends_on") or [] if d not in removed]
        if body.get("tasks_to_add"):
            for new_task in body["tasks_to_add"]:
                if not new_task.get("task_id"):
                    new_task["task_id"] = f"task_{len(tasks):03d}"
                tasks.append(new_task)
        plan["tasks"] = tasks
        if body.get("budget_override"):
            SAFE_BUDGET = {"max_tokens", "max_cost_usd", "max_time_seconds", "max_steps", "max_retries"}
            override = {k: v for k, v in body["budget_override"].items() if k in SAFE_BUDGET and not str(k).startswith("$")}
            session["budget"] = {**(session.get("budget") or {}), **override}

        from operator_engine import OperatorEngine
        engine = OperatorEngine(db)
        assignments = await engine.dispatch_agents(session_id, plan)

        await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {
            "status": "executing", "task_plan": plan, "agent_assignments": assignments, "budget": session["budget"],
        }})

        background_tasks.add_task(engine.run_session, session_id)
        return {"status": "executing", "session_id": session_id, "task_count": len(tasks)}

    @api_router.post("/operator/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {"status": "cancelled", "completed_at": now_iso()}})
        return {"status": "cancelled"}

    @api_router.post("/operator/sessions/{session_id}/pause")
    async def pause_session(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {"status": "paused"}})
        return {"status": "paused"}

    @api_router.post("/operator/sessions/{session_id}/resume")
    async def resume_session(session_id: str, request: Request, background_tasks: BackgroundTasks):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        await db.operator_sessions.update_one({"session_id": session_id}, {"$set": {"status": "executing"}})
        from operator_engine import OperatorEngine
        engine = OperatorEngine(db)
        background_tasks.add_task(engine.run_session, session_id)
        return {"status": "executing"}

    @api_router.get("/operator/sessions/{session_id}/tasks")
    async def get_session_tasks(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        tasks = await db.operator_task_executions.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("started_at", 1).to_list(50)
        return {"tasks": tasks}

    @api_router.get("/operator/sessions/{session_id}/tasks/{task_id}")
    async def get_task_detail(session_id: str, task_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        task = await db.operator_task_executions.find_one(
            {"session_id": session_id, "task_id": task_id}, {"_id": 0}
        )
        if not task:
            raise HTTPException(404, "Task not found")
        return task

    @api_router.get("/operator/sessions/{session_id}/observations")
    async def get_observations(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        session = await db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0, "observations": 1})
        return {"observations": session.get("observations") or [] if session else []}

    @api_router.post("/operator/sessions/{session_id}/inject")
    async def inject_instruction(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        session = await db.operator_sessions.find_one({"session_id": session_id}, {"_id": 0, "status": 1})
        if not session or session.get("status") not in ("executing", "paused"):
            raise HTTPException(400, "Session must be executing or paused")
        body = await request.json()
        instruction = body.get("instruction", "")
        target = body.get("target_task_id")
        if not instruction:
            raise HTTPException(400, "instruction required")

        injection = {"instruction": instruction, "target_task_id": target, "timestamp": now_iso()}
        observation = {"type": "human_injection", "key": f"User instruction{' for ' + target if target else ''}", "value": instruction, "confidence": 1.0, "source_task": "human", "timestamp": now_iso()}

        await db.operator_sessions.update_one({"session_id": session_id}, {
            "$push": {"injected_instructions": injection, "observations": observation}
        })
        return {"injected": True, "target": target}

    @api_router.post("/workspaces/{ws_id}/operator/quick")
    async def quick_session(ws_id: str, request: Request, background_tasks: BackgroundTasks):
        """One-shot: create session + auto-approve + execute immediately."""
        await _authed_user(request, ws_id)
        body = await request.json()
        goal = body.get("goal", "")
        if not goal:
            raise HTTPException(400, "goal required")
        data = OperatorSessionCreate(goal=goal, goal_type=body.get("goal_type", "custom"), auto_approve=True, budget=body.get("budget") or {}, channel_id=body.get("channel_id", ""))
        return await create_session(ws_id, data, request, background_tasks)

    # ============ Screenshots ============

    @api_router.get("/operator/sessions/{session_id}/screenshots")
    async def get_screenshots(session_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_session_access(user, session_id)
        tasks = await db.operator_task_executions.find(
            {"session_id": session_id, "screenshots": {"$exists": True, "$ne": []}},
            {"_id": 0, "task_id": 1, "goal": 1, "screenshots": 1}
        ).to_list(50)
        return {"screenshots": tasks}

    # ============ SSE Live Stream ============

    @api_router.get("/operator/sessions/{session_id}/live")
    async def live_stream(session_id: str, request: Request):
        from fastapi.responses import StreamingResponse
        import asyncio as _asyncio

        async def event_generator():
            last_obs_count = 0
            last_status = ""
            for _ in range(600):  # 10 min max
                session = await db.operator_sessions.find_one(
                    {"session_id": session_id},
                    {"_id": 0, "status": 1, "metrics": 1, "observations": 1}
                )
                if not session:
                    yield f"data: {json.dumps({'event': 'error', 'message': 'Session not found'})}\n\n"
                    break

                status = session.get("status", "")
                obs = session.get("observations") or []

                # Emit new observations
                if len(obs) > last_obs_count:
                    for o in obs[last_obs_count:]:
                        yield f"data: {json.dumps({'event': 'observation', **o})}\n\n"
                    last_obs_count = len(obs)

                # Emit metrics on status change
                if status != last_status:
                    yield f"data: {json.dumps({'event': 'status', 'status': status, 'metrics': session.get('metrics', {})})}\n\n"
                    last_status = status

                if status in ("completed", "failed", "cancelled"):
                    yield f"data: {json.dumps({'event': 'session:done', 'status': status})}\n\n"
                    break

                await _asyncio.sleep(1)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # ============ Templates ============

    @api_router.get("/workspaces/{ws_id}/operator/templates")
    async def get_templates(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        return {"templates": _builtin_templates()}

    # ============ Analytics ============

    @api_router.get("/workspaces/{ws_id}/operator/analytics")
    async def operator_analytics(ws_id: str, request: Request):
        await _authed_user(request, ws_id)
        total = await db.operator_sessions.count_documents({"workspace_id": ws_id})
        completed = await db.operator_sessions.count_documents({"workspace_id": ws_id, "status": "completed"})
        failed = await db.operator_sessions.count_documents({"workspace_id": ws_id, "status": "failed"})

        agg = await db.operator_sessions.aggregate([
            {"$match": {"workspace_id": ws_id}},
            {"$group": {"_id": None, "total_cost": {"$sum": "$metrics.total_cost_usd"}, "avg_duration": {"$avg": "$metrics.total_duration_ms"}, "total_tasks": {"$sum": "$metrics.tasks_completed"}}}
        ]).to_list(1)
        stats = agg[0] if agg else {}
        stats.pop("_id", None)

        return {
            "total_sessions": total, "completed": completed, "failed": failed,
            "success_rate": round(completed / max(total, 1) * 100, 1),
            "total_cost_usd": round(stats.get("total_cost", 0), 4),
            "avg_duration_ms": int(stats.get("avg_duration", 0) or 0),
            "total_tasks_executed": stats.get("total_tasks", 0),
        }


def _builtin_templates():
    return [
        {"template_id": "competitive_analysis", "name": "Competitive Analysis", "category": "research",
         "description": "Research 5 competitors in parallel — pricing, features, reviews. Synthesize into comparison doc.",
         "goal": "Analyze top 5 competitors to {company}. Compare pricing, features, and customer reviews. Create a comprehensive comparison document.",
         "estimated_cost": 1.50, "estimated_time": "3-5 min"},
        {"template_id": "code_review", "name": "Code Review & Test", "category": "development",
         "description": "Review code for security, quality, and performance. Write tests. Update docs.",
         "goal": "Review this code for security vulnerabilities, code quality issues, and performance problems. Write unit tests and update documentation.",
         "estimated_cost": 0.80, "estimated_time": "2-4 min"},
        {"template_id": "market_research", "name": "Market Research Report", "category": "research",
         "description": "Research market size, trends, key players, and growth projections.",
         "goal": "Research the {industry} market. Find market size, growth rate, key trends, major players, and 3-year projections. Create a research report.",
         "estimated_cost": 2.00, "estimated_time": "5-8 min"},
        {"template_id": "content_creation", "name": "Blog Post Pipeline", "category": "content",
         "description": "Research topic, write draft, edit, optimize for SEO, create social posts.",
         "goal": "Write a comprehensive blog post about {topic}. Research current data, write a 1500-word article, optimize for SEO, and create 3 social media promotional posts.",
         "estimated_cost": 1.00, "estimated_time": "3-5 min"},
        {"template_id": "bug_investigation", "name": "Bug Investigation", "category": "development",
         "description": "Investigate a bug across code, logs, and documentation. Find root cause and propose fix.",
         "goal": "Investigate this bug: {description}. Search the codebase for related code, check recent changes, analyze the error pattern, and propose a fix with code.",
         "estimated_cost": 0.60, "estimated_time": "2-3 min"},
        {"template_id": "onboarding_setup", "name": "New Project Setup", "category": "productivity",
         "description": "Set up a new project workspace with channels, tasks, wiki pages, and initial documentation.",
         "goal": "Set up a new project for {project_name}. Create relevant channels, initial project tasks, a wiki landing page with project overview, and a getting-started guide.",
         "estimated_cost": 0.40, "estimated_time": "1-2 min"},
    ]
