"""Internal API — HTTP triggers for background tasks.

Protected by X-Internal-Key header when INTERNAL_API_KEY is set.
These endpoints allow external schedulers (K8s CronJob, Cloud Scheduler) 
to trigger tasks instead of relying on in-process asyncio loops.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


def _verify_internal_key(request: Request):
    if not INTERNAL_API_KEY:
        if os.environ.get("ENVIRONMENT", "development") == "production":
            raise HTTPException(503, "Internal API key not configured")
        return  # Dev mode — no auth required
    key = request.headers.get("X-Internal-Key", "")
    import hmac
    if not hmac.compare_digest(key, INTERNAL_API_KEY):
        raise HTTPException(403, "Invalid internal API key")


def register_internal_routes(api_router, db, get_current_user):

    @api_router.post("/internal/session-cleanup")
    async def trigger_session_cleanup(request: Request):
        """Purge expired sessions."""
        _verify_internal_key(request)
        result = await db.user_sessions.delete_many(
            {"expires_at": {"$lt": datetime.now(timezone.utc).isoformat()}}
        )
        return {"deleted": result.deleted_count}

    @api_router.post("/internal/reporting-rollup")
    async def trigger_reporting_rollup(request: Request):
        """Compute daily rollups and run alerting checks."""
        _verify_internal_key(request)
        from routes_reporting import compute_rollups, run_alerting_check
        await compute_rollups(db)
        await run_alerting_check(db)
        return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}

    @api_router.post("/internal/send-scheduled-reports")
    async def trigger_scheduled_reports(request: Request):
        """Send any due scheduled reports."""
        _verify_internal_key(request)
        from routes_reporting import run_scheduled_reports
        await run_scheduled_reports(db)
        return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}

    @api_router.post("/internal/schedule-check")
    async def trigger_schedule_check(request: Request):
        """Run the agent schedule checker once."""
        _verify_internal_key(request)
        from routes_agent_schedules import execute_due_schedules
        try:
            from nexus_config import AI_MODELS
            count = await execute_due_schedules(db, AI_MODELS)
            return {"executed": count}
        except ImportError:
            return {"error": "execute_due_schedules not available"}

    @api_router.get("/internal/health")
    async def internal_health(request: Request):
        """Deep health check for internal monitoring."""
        _verify_internal_key(request)
        from instance_registry import get_instance_id
        from redis_client import is_available as redis_available
        checks = {
            "database": False,
            "redis": redis_available(),
            "instance_id": get_instance_id() or "none",
        }
        try:
            await db.command("ping")
            checks["database"] = True
        except Exception as e:
            logger.warning(f"Health check DB ping failed: {e}")
        return {"healthy": checks["database"], "checks": checks}


    @api_router.post("/internal/kg-purge")
    async def trigger_kg_purge(request: Request):
        """Execute pending KG purge jobs (consent revocations)."""
        _verify_internal_key(request)
        from datetime import datetime, timezone
        from knowledge_graph import execute_kg_purge
        pending = await db.kg_purge_jobs.find(
            {"status": "pending", "execute_by": {"$lte": datetime.now(timezone.utc).isoformat()}}
        ).to_list(50)
        for job in pending:
            await execute_kg_purge(db, job["job_id"])
        return {"purged": len(pending)}
