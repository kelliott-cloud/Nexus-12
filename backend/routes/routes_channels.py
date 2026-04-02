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

from nexus_utils import sanitize_html
from state import state_get, state_set, state_delete

def register_channels_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    from nexus_models import SessionExchange, WorkspaceCreate, ChannelCreate, MessageCreate, WorkspaceUpdate, ChannelUpdate

    
    @api_router.get("/workspaces/{workspace_id}/channels")
    async def get_channels(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        channels = await db.channels.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).to_list(100)
        return channels
    
    @api_router.post("/workspaces/{workspace_id}/channels")
    async def create_channel(workspace_id: str, data: ChannelCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        channel_id = f"ch_{uuid.uuid4().hex[:12]}"
        channel = {
            "channel_id": channel_id,
            "workspace_id": workspace_id,
            "name": data.name,
            "description": data.description,
            "ai_agents": data.ai_agents,
            "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.channels.insert_one(channel)
        result = await db.channels.find_one(
            {"channel_id": channel_id}, {"_id": 0}
        )
        return result
    
    @api_router.get("/channels/{channel_id}")
    async def get_channel(channel_id: str, request: Request):
        await get_current_user(request)
        channel = await db.channels.find_one(
            {"channel_id": channel_id}, {"_id": 0}
        )
        if not channel:
            raise HTTPException(404, "Channel not found")
        return channel
    
    @api_router.put("/channels/{channel_id}")
    async def update_channel(channel_id: str, data: ChannelUpdate, request: Request):
        """Update channel name, description, or AI agents"""
        await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id})
        if not channel:
            raise HTTPException(404, "Channel not found")
        
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.name is not None and data.name.strip():
            updates["name"] = data.name.strip()
        if data.description is not None:
            updates["description"] = data.description.strip()
        if data.ai_agents is not None:
            updates["ai_agents"] = data.ai_agents
        
        await db.channels.update_one(
            {"channel_id": channel_id},
            {"$set": updates}
        )
        
        updated = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        return updated
    
    @api_router.delete("/channels/{channel_id}")
    async def delete_channel(channel_id: str, request: Request):
        """Delete a channel and all its messages"""
        await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id})
        if not channel:
            raise HTTPException(404, "Channel not found")
        
        await db.messages.delete_many({"channel_id": channel_id})
        await db.channels.delete_one({"channel_id": channel_id})
        
        return {"message": "Channel deleted"}
    

    @api_router.get("/channels/{channel_id}/error-log")
    async def get_channel_error_log(channel_id: str, request: Request, agent: str = None, limit: int = 100):
        """Get error log for a channel — filterable by agent. Includes errors + rate limits."""
        await get_current_user(request)
        query = {
            "channel_id": channel_id,
            "action_type": {"$in": ["error", "rate_limited"]},
        }
        if agent:
            query["$or"] = [{"agent_key": agent}, {"agent": agent}]
        
        errors = await db.workspace_activities.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        total = await db.workspace_activities.count_documents(query)
        return {"errors": errors, "total": total, "channel_id": channel_id}

    @api_router.get("/channels/{channel_id}/error-log/export")
    async def export_channel_error_log(channel_id: str, request: Request, agent: str = None, format: str = "csv"):
        """Download error log as CSV or JSON."""
        await get_current_user(request)
        query = {
            "channel_id": channel_id,
            "action_type": {"$in": ["error", "rate_limited"]},
        }
        if agent:
            query["$or"] = [{"agent_key": agent}, {"agent": agent}]
        
        errors = await db.workspace_activities.find(query, {"_id": 0}).sort("timestamp", -1).limit(500).to_list(500)
        
        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            fields = ["timestamp", "agent", "agent_key", "action_type", "status", "summary"]
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for e in errors:
                writer.writerow({k: str(e.get(k, "")) for k in fields})
            from fastapi.responses import Response as RawResponse
            return RawResponse(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=error_log_{channel_id}.csv"}
            )
        
        return {"errors": errors, "total": len(errors)}


    @api_router.get("/channels/{channel_id}/transcript")
    async def download_transcript(channel_id: str, request: Request):
        """Download channel conversation as a text transcript"""
        await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")
        messages = await db.messages.find(
            {"channel_id": channel_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(5000)
        lines = []
        lines.append(f"Transcript: {channel.get('name', channel_id)}")
        lines.append(f"Exported: {datetime.now(timezone.utc).isoformat()}")
        lines.append("=" * 60)
        for msg in messages:
            sender = msg.get("sender_name", msg.get("sender_type", "unknown"))
            ts = msg.get("created_at", "")
            content = msg.get("content", "")
            lines.append(f"\n[{ts}] {sender}:")
            lines.append(content)
        transcript = "\n".join(lines)
        from fastapi.responses import Response as RawResponse
        safe_name = channel.get("name", channel_id).replace(" ", "_")[:50]
        return RawResponse(
            content=transcript.encode("utf-8"),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="transcript_{safe_name}.txt"'}
        )

