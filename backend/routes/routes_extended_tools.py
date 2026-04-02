"""Extended Tool API Routes — Expose manifesto tools as REST endpoints."""
import logging
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def register_extended_tool_routes(api_router, db, get_current_user):

    @api_router.post("/tools/web-search")
    async def api_web_search(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_web_search
        return await tool_web_search(db, body.get("workspace_id", ""), body)

    @api_router.post("/tools/ask-human")
    async def api_ask_human(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_ask_human
        return await tool_ask_human(db, body.get("channel_id", ""), body.get("agent_key", "system"), body)

    @api_router.post("/tools/read-file")
    async def api_read_file(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_read_file
        return await tool_read_file(db, body.get("workspace_id", ""), body)

    @api_router.post("/workspaces/{ws_id}/decisions")
    async def api_log_decision(ws_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_log_decision
        return await tool_log_decision(db, ws_id, body.get("channel_id", ""), body)

    @api_router.get("/workspaces/{ws_id}/decisions")
    async def api_query_decisions(ws_id: str, request: Request, q: str = ""):
        user = await get_current_user(request)
        from agent_tools_extended import tool_query_decisions
        return await tool_query_decisions(db, ws_id, {"query": q})

    @api_router.post("/tools/search-channels")
    async def api_search_channels(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_search_channels
        return await tool_search_channels(db, body.get("workspace_id", ""), body)

    @api_router.post("/tools/send-alert")
    async def api_send_alert(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_send_alert
        return await tool_send_alert(db, body.get("workspace_id", ""), body.get("channel_id", ""), body)

    @api_router.post("/channels/{ch_id}/branch")
    async def api_branch_conversation(ch_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        from agent_tools_extended import tool_branch_conversation
        return await tool_branch_conversation(db, ch_id, body.get("from_message_id", ""), body)

    @api_router.get("/workspaces/{ws_id}/agent-skills/{agent_key}")
    async def api_get_skills(ws_id: str, agent_key: str, request: Request):
        user = await get_current_user(request)
        from agent_tools_extended import get_agent_skills
        return {"skills": await get_agent_skills(db, ws_id, agent_key)}
