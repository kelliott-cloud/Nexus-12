"""Extracted from server.py — auto-generated module."""
import os
import uuid
import secrets
import asyncio
import logging
import time
import httpx
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

from nexus_utils import sanitize_html, safe_regex
from state import state_get, state_set, state_delete

def register_messages_routes(api_router, db, get_current_user, ws_manager):
    from nexus_models import SessionExchange, WorkspaceCreate, ChannelCreate, MessageCreate, WorkspaceUpdate, ChannelUpdate

    async def _require_channel_access(user, channel_id):
        """Verify user has access to the channel's workspace (NX8-003)."""
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
        if not channel:
            raise HTTPException(404, "Channel not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, channel["workspace_id"])

    @api_router.get("/channels/{channel_id}/messages")
    async def get_messages(channel_id: str, request: Request, after: Optional[str] = None):
        user = await get_current_user(request)
        await _require_channel_access(user, channel_id)
        query = {"channel_id": channel_id}
        if after:
            query["created_at"] = {"$gt": after}
        # Get the most recent messages (not oldest) to ensure new messages always show
        messages = await db.messages.find(
            query, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        # Reverse to display in chronological order
        messages.reverse()
        return messages
    
    @api_router.post("/messages/{message_id}/react")
    async def react_to_message(message_id: str, request: Request):
        user = await get_current_user(request)
        msg = await db.messages.find_one({"message_id": message_id}, {"_id": 0, "channel_id": 1})
        if msg: await _require_channel_access(user, msg["channel_id"])
        body = await request.json()
        reaction = body.get("reaction", "thumbs_up")
        await db.messages.update_one(
            {"message_id": message_id},
            {"$addToSet": {f"reactions.{reaction}": user["user_id"]}}
        )
        # Conversation learning: extract knowledge from thumbs-up on agent messages
        if reaction == "thumbs_up":
            try:
                from conversation_learning import extract_knowledge_from_feedback
                chunk = await extract_knowledge_from_feedback(db, message_id, user["user_id"])
                if chunk:
                    return {"reacted": True, "learned": True, "chunk_id": chunk.get("chunk_id")}
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Conversation learning failed: {e}")
        return {"reacted": True}
    
    @api_router.post("/messages/{message_id}/pin")
    async def pin_message(message_id: str, request: Request):
        user = await get_current_user(request)
        msg = await db.messages.find_one({"message_id": message_id}, {"_id": 0, "channel_id": 1})
        if msg: await _require_channel_access(user, msg["channel_id"])
        msg = await db.messages.find_one({"message_id": message_id})
        pinned = not msg.get("pinned", False) if msg else False
        await db.messages.update_one({"message_id": message_id}, {"$set": {"pinned": pinned}})
        return {"pinned": pinned}
    
    @api_router.get("/channels/{channel_id}/search-messages")
    async def search_messages(channel_id: str, request: Request, q: str = ""):
        user = await get_current_user(request)
        await _require_channel_access(user, channel_id)
        if not q.strip():
            return {"messages": []}
        msgs = await db.messages.find(
            {"channel_id": channel_id, "content": {"$regex": safe_regex(q), "$options": "i"}},
            {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"messages": msgs}
    
    @api_router.get("/channels/{channel_id}/pinned")
    async def get_pinned_messages(channel_id: str, request: Request):
        user = await get_current_user(request)
        await _require_channel_access(user, channel_id)
        msgs = await db.messages.find(
            {"channel_id": channel_id, "pinned": True}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return {"messages": msgs}
    
    
    
    @api_router.post("/channels/{channel_id}/messages")
    async def create_message(channel_id: str, data: MessageCreate, request: Request):
        from routes_ai_tools import parse_mentions
        user = await get_current_user(request)
        await _require_channel_access(user, channel_id)
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    
        # Parse @mentions from content
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        channel_agents = channel.get("ai_agents") or [] if channel else []
        nexus_agents_list = await db.nexus_agents.find(
            {"workspace_id": channel.get("workspace_id", "")}, {"_id": 0}
        ).to_list(50) if channel else []
        mention_data = parse_mentions(data.content, channel_agents, nexus_agents_list)
    
        message = {
            "message_id": msg_id,
            "channel_id": channel_id,
            "sender_type": "human",
            "sender_id": user["user_id"],
            "sender_name": user["name"],
            "ai_model": None,
            "content": sanitize_html(data.content),
            "mentions": mention_data,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.messages.insert_one(message)
        result = await db.messages.find_one(
            {"message_id": msg_id}, {"_id": 0}
        )
        
        # Broadcast via WebSocket for real-time delivery
        try:
            await ws_manager.broadcast(channel_id, {"type": "new_message", "message": result})
        except Exception as _exc:
            logger.debug(f"Non-critical error: {_exc}")

        # Knowledge Graph ambient learning hook (fire-and-forget)
        try:
            from knowledge_graph_hooks import on_message_created
            import asyncio as _aio
            ch_doc = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
            if ch_doc:
                _aio.create_task(on_message_created(db, message, ch_doc, ch_doc.get("workspace_id", "")))
        except Exception:
            pass

        # Human Priority: if agents are running, signal them to pause
        if await state_get("collab:active", f"{channel_id}_running"):
            await state_set("collab:priority", channel_id, {
                "pause_requested": True,
                "human_msg_id": msg_id,
                "processed": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Post system message so user knows agents are pausing
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": channel_id,
                "sender_type": "system",
                "sender_id": "system",
                "sender_name": "System",
                "content": "_Pausing agent work to process your message..._",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        return result
    
