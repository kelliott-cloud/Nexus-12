"""Mail connection management — connect Gmail, Microsoft, iCloud, IMAP accounts."""
import uuid
import logging
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from nexus_utils import now_iso
from nexus_config import FEATURE_FLAGS

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {
    "gmail": {"name": "Gmail", "auth_type": "oauth", "imap_host": "imap.gmail.com", "smtp_host": "smtp.gmail.com"},
    "microsoft": {"name": "Microsoft 365", "auth_type": "oauth", "imap_host": "outlook.office365.com", "smtp_host": "smtp.office365.com"},
    "icloud": {"name": "iCloud Mail", "auth_type": "app_password", "imap_host": "imap.mail.me.com", "smtp_host": "smtp.mail.me.com"},
    "imap": {"name": "Generic IMAP", "auth_type": "password", "imap_host": "", "smtp_host": ""},
}


class ConnectionCreate(BaseModel):
    provider: str = Field(..., description="gmail, microsoft, icloud, imap")
    email: str = Field(default="")
    display_name: str = Field(default="")
    delegation_mode: str = Field(default="recommend", description="observe, recommend, draft, safe_auto, full")
    # For IMAP/iCloud
    imap_host: Optional[str] = None
    smtp_host: Optional[str] = None
    port: Optional[int] = None
    app_password: Optional[str] = None


def register_mail_connection_routes(api_router, db, get_current_user):

    def _check_flag():
        if not FEATURE_FLAGS.get("smart_inbox", {}).get("enabled", False):
            raise HTTPException(501, FEATURE_FLAGS.get("smart_inbox", {}).get("reason", "Smart Inbox not enabled"))

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.get("/workspaces/{ws_id}/mail/connections")
    async def list_connections(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        conns = await db.mail_connections.find(
            {"workspace_id": ws_id}, {"_id": 0, "oauth_tokens": 0, "app_password": 0}
        ).to_list(20)
        return {"connections": conns}

    @api_router.post("/workspaces/{ws_id}/mail/connections")
    async def create_connection(ws_id: str, data: ConnectionCreate, request: Request, bg: BackgroundTasks):
        _check_flag()
        user = await _authed(request, ws_id)
        if data.provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(400, f"Unsupported provider. Use: {list(SUPPORTED_PROVIDERS.keys())}")

        provider_info = SUPPORTED_PROVIDERS[data.provider]
        conn_id = f"mconn_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        connection = {
            "connection_id": conn_id, "workspace_id": ws_id,
            "provider": data.provider, "provider_name": provider_info["name"],
            "email": data.email, "display_name": data.display_name or data.email,
            "auth_type": provider_info["auth_type"],
            "delegation_mode": data.delegation_mode,
            "imap_host": data.imap_host or provider_info["imap_host"],
            "smtp_host": data.smtp_host or provider_info["smtp_host"],
            "status": "active" if data.provider in ("icloud", "imap") else "pending_oauth",
            "sync_status": "pending",
            "message_count": 0, "thread_count": 0,
            "created_by": user["user_id"], "created_at": now,
        }

        # Encrypt app password if provided (iCloud/IMAP)
        if data.app_password:
            from routes.routes_ai_keys import get_fernet
            f = get_fernet()
            connection["app_password"] = f.encrypt(data.app_password.encode()).decode()
            connection["status"] = "active"

        await db.mail_connections.insert_one(connection)
        connection.pop("_id", None)
        connection.pop("app_password", None)
        connection.pop("oauth_tokens", None)

        # Start initial sync for password-based connections
        if connection["status"] == "active":
            from mail.sync_engine import run_initial_sync
            bg.add_task(run_initial_sync, db, conn_id)

        return connection

    @api_router.put("/workspaces/{ws_id}/mail/connections/{conn_id}")
    async def update_connection(ws_id: str, conn_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        body = await request.json()
        updates = {}
        for field in ["display_name", "delegation_mode", "email"]:
            if field in body:
                updates[field] = body[field]
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_at"] = now_iso()
        result = await db.mail_connections.update_one(
            {"connection_id": conn_id, "workspace_id": ws_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Connection not found")
        return {"status": "updated"}

    @api_router.delete("/workspaces/{ws_id}/mail/connections/{conn_id}")
    async def delete_connection(ws_id: str, conn_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        result = await db.mail_connections.delete_one(
            {"connection_id": conn_id, "workspace_id": ws_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Connection not found")
        # Cleanup related data
        await db.mail_threads.delete_many({"connection_id": conn_id, "workspace_id": ws_id})
        await db.mail_messages.delete_many({"connection_id": conn_id, "workspace_id": ws_id})
        await db.mail_actions.delete_many({"connection_id": conn_id, "workspace_id": ws_id})
        return {"status": "deleted"}

    @api_router.get("/workspaces/{ws_id}/mail/providers")
    async def list_providers(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        return {"providers": [{"id": k, **v} for k, v in SUPPORTED_PROVIDERS.items()]}
