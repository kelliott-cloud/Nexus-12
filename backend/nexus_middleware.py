"""Nexus Rate-Limiting + Request-Size Middleware (production-safe)."""
import time
import logging
from collections import defaultdict
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)
_rate_limits = defaultdict(list)
_cleanup_counter = 0


async def rate_limit_and_size_middleware(request: Request, call_next):
    global _cleanup_counter
    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > 10_000_000:
            return Response(content='{"detail":"Request too large"}', status_code=413, media_type="application/json")
    except (ValueError, TypeError):
        return Response(content='{"detail":"Invalid content-length"}', status_code=400, media_type="application/json")

    user_key = None
    now = None
    tier_key = None
    tier_limit = 600

    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        user_key = f"ip:{ip}"
        try:
            session_token = request.cookies.get("session_token")
            if session_token:
                user_key = f"user:{session_token[:16]}"
        except Exception as e:
            logger.warning(f"Rate limit session extraction error: {e}")

        # Tiered rate limiting based on endpoint class
        path = request.url.path
        method = request.method
        if any(p in path for p in ["/collaborate", "/mcp/invoke", "/operator/", "/a2a/"]):
            tier_name = "ai_heavy"
            tier_limit = 30
        elif path in ("/api/auth/login", "/api/auth/register"):
            tier_name = "auth_strict"
            tier_limit = 5  # FG-006: 5/min for login/register
        elif path in ("/api/auth/forgot-password", "/api/auth/verify-email"):
            tier_name = "auth_strict"
            tier_limit = 3  # 3/min for password reset
        elif path.startswith("/api/auth/mfa"):
            tier_name = "auth_mfa"
            tier_limit = 10
        elif path.startswith("/api/auth"):
            tier_name = "auth"
            tier_limit = 15
        elif method in ("POST", "PUT", "DELETE"):
            tier_name = "write"
            tier_limit = 200
        else:
            tier_name = "read"
            tier_limit = 600

        tier_key = f"{user_key}:{tier_name}"

        # Try Redis first
        try:
            from redis_client import rate_limit_check, is_available
            if is_available():
                allowed = await rate_limit_check(tier_key, limit=tier_limit, window=60)
                if not allowed:
                    return Response(content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json", headers={"Retry-After": "60"})
                response = await call_next(request)
                return response
        except Exception as e:
            logger.warning(f"Redis rate limit error, falling back to in-memory: {e}")

        # In-memory fallback
        now = time.time()
        _rate_limits[tier_key] = [t for t in _rate_limits[tier_key] if now - t < 60]
        remaining = tier_limit - len(_rate_limits[tier_key])
        if remaining <= 0:
            return Response(
                content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json",
                headers={"X-RateLimit-Limit": str(tier_limit), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(now) + 60), "Retry-After": "60"})
        _rate_limits[tier_key].append(now)
        _cleanup_counter += 1
        if _cleanup_counter % 1000 == 0:
            stale = [k for k, ts in _rate_limits.items() if not ts or now - max(ts) > 300]
            for k in stale:
                del _rate_limits[k]
            # Cap: if still over 50k, evict oldest entries (LRU)
            if len(_rate_limits) > 50000:
                sorted_keys = sorted(_rate_limits.keys(),
                    key=lambda k: max(_rate_limits[k]) if _rate_limits[k] else 0)
                for k in sorted_keys[:10000]:
                    _rate_limits.pop(k, None)

    response = await call_next(request)

    # Rate limit headers (only for /api/ requests that used in-memory)
    if user_key and now and tier_key in _rate_limits:
        count = len([x for x in _rate_limits.get(tier_key, []) if now - x < 60])
        response.headers["X-RateLimit-Limit"] = str(tier_limit if user_key else 600)
        response.headers["X-RateLimit-Remaining"] = str(max((tier_limit if user_key else 600) - count, 0))

    return response


# ============================================================
# CSRF Protection (N7-003) — Double-Submit Cookie Pattern
# ============================================================
import secrets

async def csrf_middleware(request, call_next):
    """Validate CSRF token on mutating requests when session uses SameSite=None."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        response = await call_next(request)
        # Set CSRF cookie on all GET responses if not present
        if "csrf_token" not in request.cookies:
            token = secrets.token_urlsafe(32)
            response.set_cookie("csrf_token", token, httponly=False, secure=True, samesite="none", path="/", max_age=86400)
        return response

    # For mutations, validate CSRF token
    cookie_token = request.cookies.get("csrf_token", "")
    header_token = request.headers.get("x-csrf-token", "")

    # Skip CSRF for API-key authenticated requests (non-browser clients)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and "csrf_token" not in request.cookies:
        return await call_next(request)

    # Skip CSRF for auth endpoints (login, session exchange)
    path = request.url.path
    csrf_exempt = ["/api/auth/login", "/api/auth/register", "/api/auth/session",
                   "/api/auth/google/callback", "/api/auth/forgot-password"]
    if any(path.startswith(p) for p in csrf_exempt):
        return await call_next(request)

    # Validate: cookie must match header
    if cookie_token and header_token and cookie_token == header_token:
        return await call_next(request)

    # If no cookie at all, allow (first request before cookie is set)
    if not cookie_token:
        return await call_next(request)

    # CSRF mismatch — but don't block yet, just log (gradual rollout)
    import logging
    from starlette.responses import JSONResponse
    logging.getLogger("csrf").warning(f"CSRF token mismatch on {request.method} {path}")
    return JSONResponse({"detail": "CSRF token missing or invalid"}, status_code=403)


# ============================================================
# Request Correlation ID (FG-R07)
# ============================================================
import uuid as _uuid

async def correlation_id_middleware(request, call_next):
    """Attach X-Request-ID to every request/response for end-to-end tracing."""
    request_id = request.headers.get("x-request-id") or f"req_{_uuid.uuid4().hex[:16]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
