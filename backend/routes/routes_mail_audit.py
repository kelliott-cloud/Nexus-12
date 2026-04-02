"""Mail audit log routes — view action history, compliance trail."""
from fastapi import HTTPException, Request
from nexus_config import FEATURE_FLAGS


def register_mail_audit_routes(api_router, db, get_current_user):
    def _check_flag():
        if not FEATURE_FLAGS.get("smart_inbox", {}).get("enabled", False):
            raise HTTPException(501, FEATURE_FLAGS.get("smart_inbox", {}).get("reason", "Smart Inbox not enabled"))

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.get("/workspaces/{ws_id}/mail/audit")
    async def list_audit_log(ws_id: str, request: Request, limit: int = 50, offset: int = 0, event_type: str = ""):
        _check_flag()
        await _authed(request, ws_id)
        query = {"workspace_id": ws_id}
        if event_type:
            query["event_type"] = event_type
        total = await db.mail_audit_log.count_documents(query)
        logs = await db.mail_audit_log.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
        return {"logs": logs, "total": total, "offset": offset, "limit": limit}

    @api_router.get("/workspaces/{ws_id}/mail/audit/events")
    async def list_event_types(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        events = await db.mail_audit_log.distinct("event_type", {"workspace_id": ws_id})
        return {"event_types": sorted(events)}
