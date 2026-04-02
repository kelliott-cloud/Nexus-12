"""Error Tracking Routes — Self-hosted error capture and viewer for production errors.
Captures frontend and backend errors with stack traces, context, and deduplication.
"""
import uuid
import logging
import hashlib
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import Request
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorReport(BaseModel):
    message: str
    stack: Optional[str] = None
    source: str = "frontend"
    component: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    extra: Optional[dict] = None


def register_error_tracking_routes(api_router, db, get_current_user):

    @api_router.post("/errors/report")
    async def report_error(data: ErrorReport, request: Request):
        """Capture a frontend or backend error."""
        user_id = None
        try:
            user = await get_current_user(request)
            user_id = user.get("user_id")
        except Exception as e:
            logger.warning(f"Error tracking auth check failed: {e}")
        fingerprint = hashlib.sha256(
            f"{data.message}:{data.source}:{data.component or ''}".encode()
        ).hexdigest()

        # Check if this error already exists
        existing = await db.error_events.find_one({"fingerprint": fingerprint}, {"_id": 0, "error_id": 1, "count": 1})
        if existing:
            await db.error_events.update_one(
                {"fingerprint": fingerprint},
                {"$inc": {"count": 1}, "$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
            )
            return {"status": "recorded", "error_id": existing["error_id"], "deduplicated": True}

        error_id = f"err_{uuid.uuid4().hex[:12]}"
        await db.error_events.insert_one({
            "error_id": error_id,
            "fingerprint": fingerprint,
            "message": data.message[:2000],
            "stack": (data.stack or "")[:5000],
            "source": data.source,
            "component": data.component,
            "url": data.url,
            "user_agent": data.user_agent,
            "user_id": user_id,
            "extra": data.extra or {},
            "count": 1,
            "resolved": False,
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        })
        return {"status": "recorded", "error_id": error_id}

    @api_router.get("/admin/errors")
    async def list_errors(request: Request, resolved: str = "false", limit: int = 50, skip: int = 0):
        """List captured errors (admin only)."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            from fastapi import HTTPException
            raise HTTPException(403, "Admin only")

        query = {}
        if resolved == "false":
            query["resolved"] = False
        elif resolved == "true":
            query["resolved"] = True

        errors = await db.error_events.find(query, {"_id": 0}).sort("last_seen", -1).skip(skip).limit(limit).to_list(limit)
        total = await db.error_events.count_documents(query)
        return {"errors": errors, "total": total}

    @api_router.put("/admin/errors/{error_id}/resolve")
    async def resolve_error(error_id: str, request: Request):
        """Mark an error as resolved."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            from fastapi import HTTPException
            raise HTTPException(403, "Admin only")
        await db.error_events.update_one(
            {"error_id": error_id},
            {"$set": {"resolved": True, "resolved_by": user["user_id"], "resolved_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"status": "resolved"}

    @api_router.delete("/admin/errors/{error_id}")
    async def delete_error(error_id: str, request: Request):
        """Delete an error event."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            from fastapi import HTTPException
            raise HTTPException(403, "Admin only")
        await db.error_events.delete_one({"error_id": error_id})
        return {"status": "deleted"}

    @api_router.get("/admin/errors/stats")
    async def error_stats(request: Request):
        """Get error statistics."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            from fastapi import HTTPException
            raise HTTPException(403, "Admin only")
        total = await db.error_events.count_documents({})
        unresolved = await db.error_events.count_documents({"resolved": False})
        frontend = await db.error_events.count_documents({"source": "frontend"})
        backend = await db.error_events.count_documents({"source": "backend"})
        return {"total": total, "unresolved": unresolved, "frontend": frontend, "backend": backend}
