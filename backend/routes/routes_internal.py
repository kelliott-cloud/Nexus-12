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


    @api_router.post("/internal/orch-schedules")
    async def trigger_orch_schedules(request: Request):
        """Run one pass of orchestration schedule checks."""
        _verify_internal_key(request)
        from routes_orch_schedules import run_orchestration_schedules
        await run_orchestration_schedules(db)
        return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}

    @api_router.post("/internal/cost-snapshot")
    async def trigger_cost_snapshot(request: Request):
        """Compute cost snapshots and check budget alerts."""
        _verify_internal_key(request)
        from cost_batch_job import run_cost_snapshot
        from routes_cost_alerts import check_cost_alerts
        await run_cost_snapshot(db)
        await check_cost_alerts(db)
        return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}

    @api_router.post("/internal/training-refresh")
    async def trigger_training_refresh(request: Request):
        """Re-crawl stale training sources for agents with auto_refresh enabled."""
        _verify_internal_key(request)
        import uuid as _uuid
        from agent_training_crawler import (
            fetch_page_content, chunk_content, tokenize_for_retrieval,
            classify_category, classify_source_authority, score_chunk_quality, _extract_domain,
        )
        agents = await db.nexus_agents.find(
            {"training.auto_refresh": True, "training.enabled": True},
            {"_id": 0, "agent_id": 1, "workspace_id": 1, "training": 1}
        ).to_list(50)
        from datetime import timedelta
        refreshed = 0
        for agent in agents:
            interval = (agent.get("training") or {}).get("refresh_interval_days", 30)
            last = (agent.get("training") or {}).get("last_trained")
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - last_dt < timedelta(days=interval):
                        continue
                except Exception:
                    pass
            sessions = await db.agent_training_sessions.find(
                {"agent_id": agent["agent_id"], "source_type": {"$in": ["url", "topics"]}},
                {"_id": 0, "urls": 1, "manual_urls": 1}
            ).sort("created_at", -1).limit(3).to_list(3)
            urls = []
            for s in sessions:
                urls.extend(s.get("urls") or [])
                urls.extend(s.get("manual_urls") or [])
            if not urls:
                continue
            session_id = f"refresh_{_uuid.uuid4().hex[:12]}"
            total = 0
            for url in list(set(urls))[:5]:
                page = await fetch_page_content(url)
                if page.get("error"):
                    continue
                chunks = chunk_content(page.get("text", ""), page.get("title", ""))
                domain = _extract_domain(url)
                auth = classify_source_authority(domain)
                for cd in chunks:
                    quality = await score_chunk_quality(cd["content"], "refresh")
                    if quality < 0.3:
                        continue
                    tokens = tokenize_for_retrieval(cd["content"])
                    await db.agent_knowledge.insert_one({
                        "chunk_id": f"kn_{_uuid.uuid4().hex[:12]}",
                        "agent_id": agent["agent_id"], "workspace_id": agent["workspace_id"],
                        "session_id": session_id,
                        "content": cd["content"], "summary": cd["content"][:200],
                        "category": classify_category(cd["content"]),
                        "topic": "auto-refresh", "tags": ["auto-refresh"],
                        "source": {"type": "web", "url": url, "title": page.get("title", ""), "domain": domain},
                        "tokens": tokens, "token_count": cd.get("token_count", len(tokens)),
                        "quality_score": quality, "source_authority": auth,
                        "flagged": False, "times_retrieved": 0,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    total += 1
            if total > 0:
                await db.nexus_agents.update_one(
                    {"agent_id": agent["agent_id"]},
                    {"$set": {"training.last_trained": datetime.now(timezone.utc).isoformat()},
                     "$inc": {"training.total_chunks": total}}
                )
                try:
                    from routes_agent_training import _post_training_enrich
                    await _post_training_enrich(db, agent["agent_id"], agent["workspace_id"], session_id)
                except Exception:
                    pass
                refreshed += 1
        return {"agents_refreshed": refreshed, "timestamp": datetime.now(timezone.utc).isoformat()}

    @api_router.post("/internal/leaderboard-snapshot")
    async def trigger_leaderboard_snapshot(request: Request):
        """Create a daily leaderboard snapshot."""
        _verify_internal_key(request)
        import uuid as _uuid
        agents = await db.nexus_agents.find(
            {}, {"_id": 0, "agent_id": 1, "name": 1, "evaluation.overall_score": 1,
                 "stats.total_messages": 1, "base_model": 1, "workspace_id": 1}
        ).limit(100).to_list(100)
        ranked = sorted(agents, key=lambda a: (a.get("evaluation") or {}).get("overall_score", 0), reverse=True)
        data = [{"rank": i+1, "agent_id": a.get("agent_id"), "name": a.get("name"),
                 "score": (a.get("evaluation") or {}).get("overall_score", 0)}
                for i, a in enumerate(ranked[:25])]
        await db.leaderboard_snapshots.insert_one({
            "snapshot_id": f"lbs_{_uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data, "total_agents": len(agents),
        })
        return {"agents_ranked": len(data), "timestamp": datetime.now(timezone.utc).isoformat()}

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
