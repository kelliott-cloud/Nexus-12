"""Nexus State — Redis-backed state with in-memory fallback.

Every namespace maps to an in-memory dict (for single-process) and a Redis hash (for multi-instance).
If REDIS_URL is not set, behavior is identical to raw dict access.

Namespaces:
  collab:active   -> active_collaborations
  collab:persist  -> persist_sessions
  collab:auto     -> auto_collab_sessions
  collab:stop     -> hard_stop (5 min TTL)
  collab:batch    -> pending_batch
  collab:priority -> human_priority (2 min TTL)
  editor          -> _editor_sessions
  ratelimit       -> handled by redis_client.py
"""
import json
import logging
_state_logger = logging.getLogger('state')
from collaboration_engine import (
    active_collaborations, persist_sessions, auto_collab_sessions,
    hard_stop, pending_batch, human_priority,
)

logger = logging.getLogger(__name__)

_NAMESPACE_MAP = {
    "collab:active": active_collaborations,
    "collab:persist": persist_sessions,
    "collab:auto": auto_collab_sessions,
    "collab:stop": hard_stop,
    "collab:batch": pending_batch,
    "collab:priority": human_priority,
    "task:active": {},
}

_NAMESPACE_TTL = {
    "collab:stop": 300,
    "collab:priority": 120,
}


async def _get_redis():
    try:
        from redis_client import get_redis
        return await get_redis()
    except Exception:
        return None


async def state_get(namespace: str, key: str):
    """Get a value. Tries Redis first, falls back to in-memory."""
    r = await _get_redis()
    if r:
        try:
            val = await r.get(f"{namespace}:{key}")
            if val is not None:
                return json.loads(val)
        except Exception as _e:
            _state_logger.warning(f"State operation failed: {_e}")
    mem = _NAMESPACE_MAP.get(namespace, {})
    return mem.get(key)


async def state_set(namespace: str, key: str, value, ttl: int = None):
    """Set a value in both Redis and memory."""
    if namespace not in _NAMESPACE_MAP:
        _NAMESPACE_MAP[namespace] = {}
    mem = _NAMESPACE_MAP[namespace]
    mem[key] = value
    r = await _get_redis()
    if r:
        try:
            ex = ttl or _NAMESPACE_TTL.get(namespace, 86400)
            await r.set(f"{namespace}:{key}", json.dumps(value, default=str), ex=ex)
        except Exception as _e:
            _state_logger.warning(f"State operation failed: {_e}")


async def state_delete(namespace: str, key: str):
    """Delete from both Redis and memory."""
    mem = _NAMESPACE_MAP.get(namespace)
    if mem:
        mem.pop(key, None)
    r = await _get_redis()
    if r:
        try:
            await r.delete(f"{namespace}:{key}")
        except Exception as _e:
            _state_logger.warning(f"State operation failed: {_e}")


async def state_exists(namespace: str, key: str) -> bool:
    """Check if a key exists."""
    r = await _get_redis()
    if r:
        try:
            return bool(await r.exists(f"{namespace}:{key}"))
        except Exception as _e:
            _state_logger.warning(f"State operation failed: {_e}")
    mem = _NAMESPACE_MAP.get(namespace, {})
    return key in mem


async def state_list(namespace: str) -> list:
    """List all keys in a namespace."""
    r = await _get_redis()
    if r:
        try:
            keys = []
            async for key in r.scan_iter(f"{namespace}:*", count=100):
                keys.append(key.replace(f"{namespace}:", "", 1))
            return keys
        except Exception as _e:
            _state_logger.warning(f"State operation failed: {_e}")
    mem = _NAMESPACE_MAP.get(namespace, {})
    return list(mem.keys())
