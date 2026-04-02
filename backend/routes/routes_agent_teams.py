"""Agent Teams API — Start, monitor, and govern autonomous agent team sessions."""
from nexus_utils import now_iso, gen_id, require_workspace_access
from fastapi import HTTPException, Request


def register_agent_team_routes(api_router, db, get_current_user, ws_manager=None):

    @api_router.post("/workspaces/{ws_id}/agent-teams/start")
    async def start_agent_team(ws_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        goal = body.get("goal", "").strip()
        if not goal or len(goal) < 10:
            raise HTTPException(400, "Goal must be at least 10 characters")
        from agent_team_engine import AgentTeamEngine
        engine = AgentTeamEngine(db, ws_manager)
        session_id = await engine.start_session(
            goal=goal, workspace_id=ws_id,
            channel_id=body.get("channel_id", ""),
            user_id=user["user_id"], settings=body.get("settings"))
        return {"session_id": session_id, "status": "decomposing"}

    @api_router.get("/workspaces/{ws_id}/agent-teams/{session_id}")
    async def get_agent_team_session(ws_id: str, session_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        session = await db.agent_team_sessions.find_one(
            {"session_id": session_id, "workspace_id": ws_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Session not found")
        return session

    @api_router.post("/workspaces/{ws_id}/agent-teams/{session_id}/approve")
    async def approve_escalated_session(ws_id: str, session_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        action = body.get("action", "approve")
        from agent_team_engine import AgentTeamEngine
        engine = AgentTeamEngine(db, ws_manager)
        if action == "approve":
            await engine._assemble_and_deliver(session_id)
        elif action == "retry":
            await engine._retry_with_feedback(session_id, body.get("feedback", ""))
        elif action == "cancel":
            await engine._fail(session_id, "Cancelled by user")
        return {"status": "action_taken", "action": action}

    @api_router.get("/workspaces/{ws_id}/agent-teams")
    async def list_agent_team_sessions(ws_id: str, request: Request, status: str = None, limit: int = 20):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        query = {"workspace_id": ws_id}
        if status:
            query["status"] = status
        sessions = await db.agent_team_sessions.find(query, {"_id": 0, "subtasks.output": 0}
        ).sort("created_at", -1).limit(min(limit, 100)).to_list(min(limit, 100))
        return {"sessions": sessions}

    @api_router.get("/workspaces/{ws_id}/agent-team-templates")
    async def list_team_templates(ws_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        templates = await db.agent_team_templates.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("times_used", -1).limit(50).to_list(50)
        return {"templates": templates}

    @api_router.post("/workspaces/{ws_id}/agent-team-templates")
    async def create_team_template(ws_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        name = body.get("name", "").strip()
        if not name:
            raise HTTPException(400, "Template name required")
        template = {
            "template_id": gen_id("att"), "workspace_id": ws_id,
            "name": name, "description": body.get("description", ""),
            "default_models": body.get("default_models", {}),
            "default_settings": body.get("default_settings", {"max_cost_usd": 0.50, "confidence_threshold": 0.75}),
            "created_by": user["user_id"], "times_used": 0, "avg_satisfaction": 0,
            "created_at": now_iso(),
        }
        await db.agent_team_templates.insert_one(template)
        template.pop("_id", None)
        return template

    @api_router.delete("/workspaces/{ws_id}/agent-team-templates/{template_id}")
    async def delete_team_template(ws_id: str, template_id: str, request: Request):
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        result = await db.agent_team_templates.delete_one(
            {"template_id": template_id, "workspace_id": ws_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Template not found")
        return {"status": "deleted"}

    @api_router.post("/workspaces/{ws_id}/agent-teams/start-from-template")
    async def start_from_template(ws_id: str, request: Request):
        """Start an agent team session from a saved template."""
        user = await get_current_user(request)
        await require_workspace_access(db, user, ws_id)
        body = await request.json()
        template_id = body.get("template_id", "")
        goal = body.get("goal", "").strip()
        if not goal or len(goal) < 10:
            raise HTTPException(400, "Goal must be at least 10 characters")
        template = await db.agent_team_templates.find_one(
            {"template_id": template_id, "workspace_id": ws_id}, {"_id": 0})
        if not template:
            raise HTTPException(404, "Template not found")
        settings = {**template.get("default_settings", {}), **(body.get("settings") or {})}
        from agent_team_engine import AgentTeamEngine
        engine = AgentTeamEngine(db, ws_manager)
        session_id = await engine.start_session(
            goal=goal, workspace_id=ws_id,
            channel_id=body.get("channel_id", ""),
            user_id=user["user_id"], settings=settings)
        await db.agent_team_templates.update_one(
            {"template_id": template_id}, {"$inc": {"times_used": 1}})
        return {"session_id": session_id, "status": "decomposing", "template_used": template_id}
