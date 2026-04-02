"""Redis Client — Shared async connection with pool, health checks, and configurable fallback.
Set REDIS_REQUIRED=true in production to enforce Redis availability.
"""
import os
import time
import logging

logger = logging.getLogger(__name__)

_redis = None
_available = False
_last_failure = 0
_last_latency_ms = -1
RETRY_AFTER = 60

REDIS_REQUIRED = os.environ.get("REDIS_REQUIRED", "").lower() in ("true", "1", "yes")
REDIS_URL = os.environ.get("REDIS_URL", "")
REDIS_MAX_CONNECTIONS = int(os.environ.get("REDIS_MAX_CONNECTIONS", "20"))
REDIS_SOCKET_TIMEOUT = int(os.environ.get("REDIS_SOCKET_TIMEOUT", "5"))
REDIS_CONNECT_TIMEOUT = int(os.environ.get("REDIS_CONNECT_TIMEOUT", "5"))


def is_available():
    return _available


def get_latency_ms():
    """Return last measured Redis latency in ms, or -1 if unavailable."""
    return _last_latency_ms


async def get_redis():
    """Get async Redis connection with connection pooling. Returns None if unavailable."""
    global _redis, _available, _last_failure, _last_latency_ms

    if not REDIS_URL:
        if REDIS_REQUIRED:
            raise RuntimeError("REDIS_REQUIRED=true but REDIS_URL is not set")
        return None

    if _redis == "failed":
        if time.time() - _last_failure < RETRY_AFTER:
            return None
        _redis = None

    if _redis is not None and _available:
        try:
            t0 = time.monotonic()
            await _redis.ping()
            _last_latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return _redis
        except Exception:
            _redis = None
            _available = False
            _last_latency_ms = -1

    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            max_connections=REDIS_MAX_CONNECTIONS,
        )
        t0 = time.monotonic()
        await _redis.ping()
        _last_latency_ms = round((time.monotonic() - t0) * 1000, 1)
        _available = True
        logger.info(f"Redis connected: {REDIS_URL[:30]}... (pool={REDIS_MAX_CONNECTIONS}, latency={_last_latency_ms}ms)")
        return _redis
    except Exception as e:
        _available = False
        _redis = "failed"
        _last_failure = time.time()
        _last_latency_ms = -1
        if REDIS_REQUIRED:
            raise RuntimeError(f"REDIS_REQUIRED=true but connection failed: {e}")
        logger.warning(f"Redis connection failed: {e} — using in-memory fallback (retry in {RETRY_AFTER}s)")
        return None


async def health_check() -> dict:
    """Detailed Redis health check for status endpoints."""
    if not REDIS_URL:
        return {
            "status": "disabled" if not REDIS_REQUIRED else "error",
            "note": "REDIS_URL not configured" + (" (REQUIRED)" if REDIS_REQUIRED else " — in-memory fallback active"),
        }
    try:
        r = await get_redis()
        if r:
            info = await r.info(section="server")
            return {
                "status": "operational",
                "latency_ms": _last_latency_ms,
                "version": info.get("redis_version", "unknown"),
                "connected_clients": (await r.info(section="clients")).get("connected_clients", "?"),
                "max_connections": REDIS_MAX_CONNECTIONS,
            }
        return {"status": "degraded", "note": "Connection failed, using in-memory fallback", "retry_in_s": max(0, int(RETRY_AFTER - (time.time() - _last_failure)))}
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}


async def rate_limit_check(key: str, limit: int = 120, window: int = 60) -> bool:
    """Check rate limit via Redis INCR+EXPIRE. Returns True if allowed."""
    r = await get_redis()
    if not r:
        return True
    try:
        current = await r.incr(f"rl:{key}")
        if current == 1:
            await r.expire(f"rl:{key}", window)
        return current <= limit
    except Exception:
        return True


async def acquire_lock(lock_name: str, ttl: int = 300) -> bool:
    """Distributed lock via Redis SETNX."""
    r = await get_redis()
    if not r:
        logger.warning(f"Running {lock_name} without distributed lock (Redis unavailable)")
        return True  # Single-instance fallback
    try:
        acquired = await r.set(f"lock:{lock_name}", "1", nx=True, ex=ttl)
        return bool(acquired)
    except Exception as e:
        logger.warning(f"Lock acquire failed for {lock_name}: {e}")
        return True


async def release_lock(lock_name: str):
    r = await get_redis()
    if r:
        try:
            await r.delete(f"lock:{lock_name}")
        except Exception as _e:
            import logging; logging.getLogger("redis_client").warning(f"Suppressed: {_e}")
