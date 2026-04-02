"""Module Enforcement Middleware — Blocks API routes for disabled modules."""
import re
import time
import logging
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)

# Short TTL cache for module configs (avoid DB hit on every request)
_module_cache = {}
_CACHE_TTL = 30  # seconds


async def module_enforcement_middleware(request: Request, call_next, db=None):
    """Check if the requested route belongs to an enabled module."""
    path = request.url.path

    # Bypass: non-workspace routes (auth, billing, health, admin, modules registry)
    bypass_prefixes = ["/api/auth", "/api/health", "/api/billing", "/api/admin",
                       "/api/modules/registry", "/api/modules/bundles", "/api/developer",
                       "/api/cloudflare", "/api/openclaw", "/api/bridge",
                       "/api/notifications", "/api/ai-models", "/api/user",
                       "/api/catalog", "/api/marketplace", "/api/settings",
                       "/api/helper", "/api/platform/profile"]
    for bp in bypass_prefixes:
        if path.startswith(bp):
            return await call_next(request)

    # Bypass: non-API routes
    if not path.startswith("/api/"):
        return await call_next(request)

    # Platform Profile enforcement (above workspace modules)
    from platform_profile import get_route_feature, get_feature_state
    route_suffix = path.replace("/api/workspaces/", "").split("/", 1)[-1] if "/workspaces/" in path else path.replace("/api", "")
    feature_key = get_route_feature(route_suffix)
    if feature_key:
        state = get_feature_state(feature_key)
        if state == "off":
            from starlette.responses import Response as _Resp
            return _Resp(status_code=404, content='{"detail":"Not found"}', media_type="application/json")
    if not path.startswith("/api/"):
        return await call_next(request)

    # Extract workspace_id from URL
    ws_match = re.search(r"/workspaces/([^/]+)", path)
    if not ws_match:
        # Channel-scoped or other — let through (channel access is checked separately)
        return await call_next(request)

    ws_id = ws_match.group(1)

    # Get module config (cached)
    now = time.time()
    cached = _module_cache.get(ws_id)
    if cached and (now - cached[1]) < _CACHE_TTL:
        module_config = cached[0]
    else:
        if db:
            ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "module_config": 1})
            module_config = (ws or {}).get("module_config")
            _module_cache[ws_id] = (module_config, now)
        else:
            module_config = None

    # Backward compat: no module_config = all modules enabled
    if not module_config or not module_config.get("modules"):
        return await call_next(request)

    # Check route against module registry
    from module_registry import MODULE_REGISTRY
    route_suffix = path.replace(f"/api/workspaces/{ws_id}", "")

    for mid, mod in MODULE_REGISTRY.items():
        if mod["always_on"]:
            continue
        for prefix in mod["route_prefixes"]:
            if route_suffix.startswith(prefix):
                # This route belongs to this module
                mod_config = (module_config.get("modules") or {}).get(mid, {})
                if not mod_config.get("enabled", True):  # default True for backward compat
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"This feature requires the {mod['name']} module. Activate it in workspace settings.",
                            "module_required": mid,
                            "module_name": mod["name"],
                        }
                    )
                break

    return await call_next(request)


def clear_module_cache(ws_id=None):
    """Clear module config cache. Called when modules are updated."""
    if ws_id:
        _module_cache.pop(ws_id, None)
    else:
        _module_cache.clear()
