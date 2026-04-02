from nexus_utils import now_iso
"""Nexus Connect — Send notifications and sync data with Slack, Jira, GitHub, and more.

Webhook-based outbound integrations that push Nexus events to external tools.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
import httpx

logger = logging.getLogger(__name__)


def register_nexus_connect_routes(api_router, db, get_current_user):

    @api_router.get("/workspaces/{ws_id}/connections")
    async def list_connections(ws_id: str, request: Request):
        user = await get_current_user(request)
        conns = await db.nexus_connections.find({"workspace_id": ws_id}, {"_id": 0}).to_list(20)
        return conns

    @api_router.post("/workspaces/{ws_id}/connections")
    async def create_connection(ws_id: str, request: Request):
        """Create an outbound webhook connection to an external service."""
        user = await get_current_user(request)
        body = await request.json()
        
        conn_id = f"nxc_{uuid.uuid4().hex[:12]}"
        conn = {
            "connection_id": conn_id,
            "workspace_id": ws_id,
            "name": body.get("name", ""),
            "type": body.get("type", "webhook"),
            "service": body.get("service", "slack"),
            "webhook_url": body.get("webhook_url", ""),
            "events": body.get("events", ["ai_response", "task_created", "deployment_completed"]),
            "active": True,
            "created_by": user["user_id"],
            "created_at": now_iso(),
            "last_triggered": None,
            "trigger_count": 0,
        }
        await db.nexus_connections.insert_one(conn)
        conn.pop("_id", None)
        return conn

    @api_router.put("/connections/{conn_id}")
    async def update_connection(conn_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        update = {"updated_at": now_iso()}
        for f in ["name", "webhook_url", "events", "active"]:
            if f in body:
                update[f] = body[f]
        await db.nexus_connections.update_one({"connection_id": conn_id}, {"$set": update})
        return {"updated": conn_id}

    @api_router.delete("/connections/{conn_id}")
    async def delete_connection(conn_id: str, request: Request):
        user = await get_current_user(request)
        await db.nexus_connections.delete_one({"connection_id": conn_id})
        return {"deleted": conn_id}

    @api_router.post("/connections/{conn_id}/test")
    async def test_connection(conn_id: str, request: Request):
        """Send a test message to the webhook."""
        user = await get_current_user(request)
        conn = await db.nexus_connections.find_one({"connection_id": conn_id}, {"_id": 0})
        if not conn:
            raise HTTPException(404, "Connection not found")
        
        payload = {
            "event": "test",
            "source": "nexus_cloud",
            "message": "This is a test message from Nexus Cloud.",
            "timestamp": now_iso(),
        }
        
        if conn["service"] == "slack":
            payload = {"text": "Test from Nexus Cloud — your integration is working."}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(conn["webhook_url"], json=payload)
                success = resp.status_code < 400
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}
        
        return {"success": success, "status_code": resp.status_code}


async def send_nexus_event(db, workspace_id: str, event_type: str, data: dict):
    """Send an event to all active connections for this workspace that listen for this event type."""
    connections = await db.nexus_connections.find(
        {"workspace_id": workspace_id, "active": True},
        {"_id": 0}
    ).to_list(10)
    
    for conn in connections:
        if event_type not in conn.get("events") or [] and "*" not in conn.get("events") or []:
            continue
        
        payload = {"event": event_type, "source": "nexus_cloud", "data": data, "timestamp": now_iso()}
        
        if conn.get("service") == "slack":
            text = f"*Nexus Cloud* — {event_type}\n"
            for k, v in data.items():
                text += f"  {k}: {v}\n"
            payload = {"text": text}
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(conn["webhook_url"], json=payload)
            await db.nexus_connections.update_one(
                {"connection_id": conn["connection_id"]},
                {"$set": {"last_triggered": now_iso()}, "$inc": {"trigger_count": 1}}
            )
        except Exception as e:
            logger.debug(f"Nexus Connect send failed: {e}")
