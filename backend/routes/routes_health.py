"""Health check routes — extracted from server.py (N7-019)."""
import json
from fastapi import Response, Request, HTTPException


def register_health_routes(api_router, db, get_current_user=None):

    @api_router.get("/health")
    async def health_check():
        from instance_registry import get_instance_id
        try:
            await db.command("ping")
            return {"status": "healthy", "database": "connected", "instance_id": get_instance_id()}
        except Exception as e:
            return Response(content=f'{{"status":"unhealthy","database":"disconnected","error":"{str(e)[:100]}"}}', status_code=503, media_type="application/json")

    @api_router.get("/health/startup")
    async def startup_probe():
        """Full readiness check for K8s startup probe — includes Redis."""
        from instance_registry import get_instance_id
        checks = {"database": False, "instance_id": False, "redis": False}
        try:
            await db.command("ping")
            checks["database"] = True
        except Exception as _e:
            import logging; logging.getLogger("routes/routes_health").warning(f"Suppressed: {_e}")
        iid = get_instance_id()
        checks["instance_id"] = bool(iid)
        try:
            from redis_client import get_redis, REDIS_REQUIRED
            r = await get_redis()
            checks["redis"] = bool(r) if REDIS_REQUIRED else True
        except Exception:
            checks["redis"] = False
        all_ok = all(checks.values())
        return Response(
            content=json.dumps({"ready": all_ok, "checks": checks, "instance_id": iid}),
            status_code=200 if all_ok else 503,
            media_type="application/json"
        )

    @api_router.get("/health/live")
    async def liveness_probe():
        """Lightweight liveness check — confirms event loop is responsive."""
        return {"alive": True}

    @api_router.get("/admin/circuit-breakers")
    async def get_circuit_breaker_status(request: Request):
        """FG-012: Circuit breaker visibility for AI providers (admin only)."""
        if get_current_user:
            user = await get_current_user(request)
            from routes.routes_admin import is_super_admin
            if not await is_super_admin(db, user["user_id"]):
                raise HTTPException(403, "Admin access required")
        from keystone import circuit_breaker
        status = circuit_breaker.get_status()
        # Add all known providers even if no state yet
        known = ["chatgpt", "claude", "gemini", "groq", "deepseek", "mistral", "cohere", "perplexity", "grok"]
        for p in known:
            if p not in status:
                status[p] = {"state": "closed", "failures": 0}
        return {"circuit_breakers": status}

    @api_router.get("/admin/db-health")
    async def get_db_health(request: Request):
        """FG-010: MongoDB connection pool monitoring (admin only)."""
        if get_current_user:
            user = await get_current_user(request)
            from routes.routes_admin import is_super_admin
            if not await is_super_admin(db, user["user_id"]):
                raise HTTPException(403, "Admin access required")
        try:
            stats = await db.command("serverStatus")
            connections = stats.get("connections", {})
            opcounters = stats.get("opcounters", {})
            mem = stats.get("mem", {})
            collections = await db.list_collection_names()
            coll_sizes = {}
            for c in collections[:30]:
                try:
                    s = await db.command("collStats", c)
                    coll_sizes[c] = {"count": s.get("count", 0), "size_mb": round(s.get("size", 0) / 1024 / 1024, 2)}
                except Exception as _e:
                    coll_sizes[c] = {"error": str(_e)[:50]}
            return {
                "connections": {"current": connections.get("current"), "available": connections.get("available"), "total_created": connections.get("totalCreated")},
                "opcounters": {k: v for k, v in opcounters.items() if k in ("insert", "query", "update", "delete", "getmore")},
                "memory_mb": {"resident": mem.get("resident"), "virtual": mem.get("virtual")},
                "collections": coll_sizes,
                "total_collections": len(collections),
            }
        except Exception as e:
            return {"error": str(e)[:200]}
