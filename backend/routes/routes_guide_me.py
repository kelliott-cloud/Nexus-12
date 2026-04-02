"""Guide Me — AI-assisted browser guidance within Nexus"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def register_guide_me_routes(api_router, db, get_current_user):

    # Agents that support browser guidance (have vision/tool-use capabilities)
    GUIDE_CAPABLE_AGENTS = {
        "claude", "chatgpt", "gemini", "deepseek", "groq", "mistral", "cohere", "grok"
    }
    GUIDE_INCAPABLE_AGENTS = {"mercury", "pi"}  # No vision/tool-use APIs

    @api_router.get("/guide-me/agents")
    async def get_guide_agents(request: Request):
        """Get which agents are capable of browser guidance"""
        await get_current_user(request)
        return {
            "capable": list(GUIDE_CAPABLE_AGENTS),
            "incapable": list(GUIDE_INCAPABLE_AGENTS),
        }

    @api_router.post("/guide-me/session")
    async def create_guide_session(request: Request):
        """Create a new Guide Me session"""
        user = await get_current_user(request)
        body = await request.json()
        agent_key = body.get("agent", "")
        url = body.get("url", "")
        workspace_id = body.get("workspace_id", "")

        if agent_key not in GUIDE_CAPABLE_AGENTS:
            raise HTTPException(400, f"{agent_key} does not support browser guidance")

        session_id = f"gm_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        session = {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "user_id": user["user_id"],
            "agent": agent_key,
            "url": url,
            "status": "active",
            "messages": [],
            "created_at": now,
        }
        await db.guide_sessions.insert_one(session)
        return {k: v for k, v in session.items() if k != "_id"}

    @api_router.post("/guide-me/{session_id}/message")
    async def send_guide_message(session_id: str, request: Request):
        """Send a message in a Guide Me session"""
        user = await get_current_user(request)
        body = await request.json()
        content = body.get("content", "")
        current_url = body.get("current_url", "")

        session = await db.guide_sessions.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(404, "Session not found")

        now = datetime.now(timezone.utc).isoformat()
        msg = {
            "role": "user",
            "content": content,
            "url": current_url,
            "timestamp": now,
        }

        await db.guide_sessions.update_one(
            {"session_id": session_id},
            {"$push": {"messages": msg}}
        )

        return {"sent": True, "message": msg}

    @api_router.get("/guide-me/{session_id}")
    async def get_guide_session(session_id: str, request: Request):
        await get_current_user(request)
        session = await db.guide_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Session not found")
        return session

    @api_router.delete("/guide-me/{session_id}")
    async def end_guide_session(session_id: str, request: Request):
        await get_current_user(request)
        await db.guide_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"ended": True}
