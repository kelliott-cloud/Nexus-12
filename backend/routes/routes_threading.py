from nexus_utils import now_iso
"""Conversation Threading — Thread-based replies for multi-agent conversations.

Enables threaded replies to specific messages, keeping the main channel clean
while allowing focused conversations with individual agents.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



def register_threading_routes(api_router, db, get_current_user):

    @api_router.get("/messages/{message_id}/thread")
    async def get_thread(message_id: str, request: Request):
        """Get all replies in a thread."""
        await get_current_user(request)
        replies = await db.messages.find(
            {"thread_id": message_id},
            {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        
        # Get thread summary
        parent = await db.messages.find_one({"message_id": message_id}, {"_id": 0, "content": 1, "sender_name": 1, "thread_count": 1})
        
        return {
            "parent_message_id": message_id,
            "replies": replies,
            "reply_count": len(replies),
            "participants": list(set(r.get("sender_name", "") for r in replies)),
        }

    @api_router.post("/messages/{message_id}/thread")
    async def reply_to_thread(message_id: str, request: Request):
        """Post a reply in a thread."""
        user = await get_current_user(request)
        body = await request.json()
        content = body.get("content", "").strip()
        if not content:
            raise HTTPException(400, "Content required")
        
        # Get the parent message to find the channel
        parent = await db.messages.find_one({"message_id": message_id}, {"_id": 0})
        if not parent:
            raise HTTPException(404, "Parent message not found")
        
        reply_id = f"msg_{uuid.uuid4().hex[:12]}"
        reply = {
            "message_id": reply_id,
            "channel_id": parent["channel_id"],
            "thread_id": message_id,
            "sender_type": "human",
            "sender_id": user["user_id"],
            "sender_name": user.get("name", "User"),
            "content": content,
            "created_at": now_iso(),
        }
        await db.messages.insert_one(reply)
        reply.pop("_id", None)
        
        # Update thread count on parent
        await db.messages.update_one(
            {"message_id": message_id},
            {"$inc": {"thread_count": 1}, "$set": {"last_thread_reply_at": now_iso()}}
        )
        
        return reply

    @api_router.get("/channels/{channel_id}/thread-summary")
    async def channel_thread_summary(channel_id: str, request: Request):
        """Get active threads in a channel."""
        await get_current_user(request)
        threaded = await db.messages.find(
            {"channel_id": channel_id, "thread_count": {"$gt": 0}},
            {"_id": 0, "message_id": 1, "sender_name": 1, "content": 1, "thread_count": 1, "last_thread_reply_at": 1}
        ).sort("last_thread_reply_at", -1).limit(20).to_list(20)
        
        for t in threaded:
            t["content_preview"] = (t.get("content") or "")[:100]
        
        return {"threads": threaded, "active_count": len(threaded)}
