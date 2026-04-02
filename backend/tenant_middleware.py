"""Tenant Isolation Middleware — Enforces workspace access at the middleware layer.
Eliminates the need for require_workspace_access() in individual route handlers."""
import re
import logging
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Routes that bypass tenant isolation (no workspace_id in path)
BYPASS_PREFIXES = [
    "/api/auth", "/api/health", "/api/billing/plans", "/api/billing/subscription",
    "/api/modules/registry", "/api/modules/bundles", "/api/developer",
    "/api/admin", "/api/notifications", "/api/ai-models", "/api/user",
    "/api/catalog", "/api/marketplace", "/api/settings", "/api/bridge",
    "/api/cloudflare/health", "/api/cloudflare/kv", "/api/openclaw/health",
    "/api/cursor/mcp", "/api/orchestration-templates",
]

# WebSocket paths — handled by their own auth
WS_PREFIXES = ["/api/ws/"]


async def tenant_isolation_middleware(request: Request, call_next, db=None):
    """Verify workspace access for all /api/workspaces/{ws_id}/ routes."""
    path = request.url.path

    # Skip non-API routes
    if not path.startswith("/api/"):
        return await call_next(request)

    # Skip bypass routes
    for bp in BYPASS_PREFIXES:
        if path.startswith(bp):
            return await call_next(request)

    # Skip WebSocket
    for ws in WS_PREFIXES:
        if path.startswith(ws):
            return await call_next(request)

    # Extract workspace_id from URL
    ws_match = re.search(r"/workspaces/([^/]+)", path)
    if not ws_match:
        return await call_next(request)

    ws_id = ws_match.group(1)

    # Skip non-workspace-ID patterns (e.g., /workspaces/bulk-delete)
    if ws_id in ("bulk-delete", "search", "export", "import", "templates"):
        return await call_next(request)

    # Get user from session cookie or Authorization header
    user_id = None
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                session_token = auth_header.replace("Bearer ", "")

        if session_token and db:
            session = await db.user_sessions.find_one(
                {"session_token": session_token},
                {"_id": 0, "user_id": 1, "expires_at": 1}
            )
            if session:
                from datetime import datetime as _dt, timezone as _tz
                expires_at = session.get("expires_at", "")
                if isinstance(expires_at, str) and expires_at:
                    expires_at = _dt.fromisoformat(expires_at.replace("Z", "+00:00"))
                if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=_tz.utc)
                if not expires_at or expires_at < _dt.now(_tz.utc):
                    pass  # Expired — let route handler deal with 401
                else:
                    user_id = session["user_id"]
    except Exception as _e:
        import logging; logging.getLogger("tenant_middleware").warning(f"Suppressed: {_e}")

    if not user_id:
        # No auth — let the route handler deal with 401
        return await call_next(request)

    # Check workspace access
    if db:
        try:
            from data_guard import TenantIsolation
            has_access = await TenantIsolation.verify_workspace_access(db, user_id, ws_id)
            if not has_access:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "You do not have access to this workspace"}
                )
            # Attach to request state for downstream use
            request.state.user_id = user_id
            request.state.ws_id = ws_id
        except Exception as e:
            logger.debug(f"Tenant middleware check failed: {e}")

    return await call_next(request)
