"""Additional Features — Channel archiving, message pinning, workspace export."""
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def register_additional_features(api_router, db, get_current_user):

    # ============ F5: Channel Archiving ============
    @api_router.post("/channels/{channel_id}/archive")
    async def archive_channel(channel_id: str, request: Request):
        user = await get_current_user(request)
        await db.channels.update_one(
            {"channel_id": channel_id},
            {"$set": {"archived": True, "archived_by": user["user_id"], "archived_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"archived": True, "channel_id": channel_id}

    @api_router.post("/channels/{channel_id}/unarchive")
    async def unarchive_channel(channel_id: str, request: Request):
        await get_current_user(request)
        await db.channels.update_one({"channel_id": channel_id}, {"$unset": {"archived": "", "archived_by": "", "archived_at": ""}})
        return {"archived": False, "channel_id": channel_id}

    # ============ F8: Message Pinning ============
    @api_router.post("/channels/{channel_id}/messages/{message_id}/pin")
    async def pin_message(channel_id: str, message_id: str, request: Request):
        user = await get_current_user(request)
        await db.messages.update_one(
            {"message_id": message_id, "channel_id": channel_id},
            {"$set": {"pinned": True, "pinned_by": user["user_id"], "pinned_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"pinned": True}

    @api_router.post("/channels/{channel_id}/messages/{message_id}/unpin")
    async def unpin_message(channel_id: str, message_id: str, request: Request):
        await get_current_user(request)
        await db.messages.update_one(
            {"message_id": message_id, "channel_id": channel_id},
            {"$unset": {"pinned": "", "pinned_by": "", "pinned_at": ""}}
        )
        return {"pinned": False}


    # Workspace export handled by routes_export_audit.py

    # ============ F3: Agent Performance Metrics ============
    @api_router.get("/channels/{channel_id}/agent-performance")
    async def channel_agent_performance(channel_id: str, request: Request):
        """Get per-agent performance metrics for a channel."""
        await get_current_user(request)
        pipeline = [
            {"$match": {"channel_id": channel_id}},
            {"$group": {
                "_id": "$agent",
                "total_events": {"$sum": 1},
                "avg_latency": {"$avg": "$response_time_ms"},
                "errors": {"$sum": {"$cond": [{"$eq": ["$action_type", "error"]}, 1, 0]}},
                "rate_limits": {"$sum": {"$cond": [{"$eq": ["$action_type", "rate_limited"]}, 1, 0]}},
                "responses": {"$sum": {"$cond": [{"$eq": ["$action_type", "ai_response"]}, 1, 0]}},
                "tool_calls": {"$sum": {"$cond": [{"$eq": ["$action_type", "tool_call"]}, 1, 0]}},
            }},
            {"$sort": {"total_events": -1}},
        ]
        results = await db.workspace_activities.aggregate(pipeline).to_list(20)
        return {"agents": [{
            "agent": r["_id"],
            "total_events": r["total_events"],
            "avg_latency_ms": round(r.get("avg_latency", 0) or 0),
            "errors": r["errors"],
            "rate_limits": r["rate_limits"],
            "responses": r["responses"],
            "tool_calls": r["tool_calls"],
            "error_rate": round(r["errors"] / max(r["total_events"], 1) * 100, 1),
        } for r in results]}

    # ============ F9: Typing Indicators ============
    # Typing indicators handled by routes_tier23.py
