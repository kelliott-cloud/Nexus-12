"""Benchmark Comparison, Collaboration Templates, Review Analytics, Security Dashboard."""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)


def register_advanced_features_routes(api_router, db, get_current_user):

    # ============ Benchmark Comparison ============

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/compare")
    async def compare_benchmarks(ws_id: str, agent_id: str, request: Request, run_ids: str = ""):
        """Compare multiple benchmark runs side-by-side."""
        await get_current_user(request)
        ids = [r.strip() for r in run_ids.split(",") if r.strip()] if run_ids else []
        if not ids:
            runs = await db.benchmark_runs.find(
                {"agent_id": agent_id, "workspace_id": ws_id, "status": "completed"},
                {"_id": 0}
            ).sort("started_at", -1).limit(5).to_list(5)
        else:
            runs = await db.benchmark_runs.find(
                {"run_id": {"$in": ids}, "agent_id": agent_id}, {"_id": 0}
            ).to_list(len(ids))

        comparison = []
        for run in runs:
            summary = run.get("summary") or {}
            by_category = {}
            for r in run.get("results") or []:
                cat = r.get("category", "general")
                if cat not in by_category:
                    by_category[cat] = {"total": 0, "passed": 0, "score_sum": 0}
                by_category[cat]["total"] += 1
                by_category[cat]["score_sum"] += r.get("overall_score", 0)
                if r.get("passed"):
                    by_category[cat]["passed"] += 1
            for cat in by_category:
                by_category[cat]["avg_score"] = round(by_category[cat]["score_sum"] / max(by_category[cat]["total"], 1), 1)

            comparison.append({
                "run_id": run["run_id"], "suite_name": run.get("suite_name", ""),
                "started_at": run.get("started_at", ""),
                "avg_score": summary.get("avg_score", 0),
                "pass_rate": summary.get("pass_rate", 0),
                "total_cases": summary.get("total_cases", 0),
                "passed": summary.get("passed", 0),
                "by_category": by_category,
            })

        # Trend data
        trend = [{"run_id": c["run_id"], "date": c["started_at"][:10], "score": c["avg_score"], "pass_rate": c["pass_rate"]} for c in comparison]
        return {"comparison": comparison, "trend": trend}

    # ============ Collaboration Templates Library ============

    @api_router.get("/orchestration-templates")
    async def list_orch_templates(request: Request, category: str = ""):
        await get_current_user(request)
        query = {"is_active": True}
        if category:
            query["category"] = category
        templates = await db.orchestration_templates.find(query, {"_id": 0}).sort("usage_count", -1).limit(30).to_list(30)
        if not templates:
            templates = _get_builtin_templates()
            for t in templates:
                t["_source"] = "builtin"
        return {"templates": templates}

    @api_router.post("/orchestration-templates")
    async def publish_orch_template(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        tpl_id = f"otpl_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        template = {
            "template_id": tpl_id, "name": body.get("name", ""),
            "description": body.get("description", ""),
            "category": body.get("category", "general"),
            "steps": body.get("steps") or [], "execution_mode": body.get("execution_mode", "sequential"),
            "tags": body.get("tags") or [], "is_active": True,
            "usage_count": 0, "publisher_id": user["user_id"],
            "publisher_name": user.get("name", ""), "created_at": now,
        }
        await db.orchestration_templates.insert_one(template)
        template.pop("_id", None)
        return template

    @api_router.post("/workspaces/{ws_id}/orchestration-templates/{tpl_id}/install")
    async def install_orch_template(ws_id: str, tpl_id: str, request: Request):
        user = await get_current_user(request)
        tpl = await db.orchestration_templates.find_one({"template_id": tpl_id}, {"_id": 0})
        if not tpl:
            builtin = {t["template_id"]: t for t in _get_builtin_templates()}
            tpl = builtin.get(tpl_id)
        if not tpl:
            raise HTTPException(404, "Template not found")

        orch_id = f"orch_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        steps = []
        for i, s in enumerate(tpl.get("steps") or []):
            steps.append({
                "step_id": s.get("step_id", f"step_{i}"),
                "agent_id": s.get("agent_id", ""),
                "prompt_template": s.get("prompt_template", "{input}"),
                "depends_on": s.get("depends_on") or [],
                "condition": s.get("condition", ""),
            })
        orch = {
            "orchestration_id": orch_id, "workspace_id": ws_id,
            "name": f"{tpl['name']} (from template)", "description": tpl.get("description", ""),
            "execution_mode": tpl.get("execution_mode", "sequential"),
            "steps": steps, "step_count": len(steps),
            "created_by": user["user_id"], "run_count": 0,
            "from_template": tpl_id, "created_at": now, "updated_at": now,
        }
        await db.orchestrations.insert_one(orch)
        orch.pop("_id", None)
        await db.orchestration_templates.update_one({"template_id": tpl_id}, {"$inc": {"usage_count": 1}})
        return orch

    # ============ Review Analytics ============

    @api_router.get("/marketplace/review-analytics")
    async def review_analytics(request: Request, template_id: str = ""):
        await get_current_user(request)
        match = {}
        if template_id:
            match["template_id"] = template_id

        # Overall stats
        pipeline_stats = [
            {"$match": {**match, "flagged": {"$ne": True}}},
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}, "total": {"$sum": 1},
                        "five": {"$sum": {"$cond": [{"$eq": ["$rating", 5]}, 1, 0]}},
                        "four": {"$sum": {"$cond": [{"$eq": ["$rating", 4]}, 1, 0]}},
                        "three": {"$sum": {"$cond": [{"$eq": ["$rating", 3]}, 1, 0]}},
                        "two": {"$sum": {"$cond": [{"$eq": ["$rating", 2]}, 1, 0]}},
                        "one": {"$sum": {"$cond": [{"$eq": ["$rating", 1]}, 1, 0]}}}},
        ]
        stats_result = await db.marketplace_reviews.aggregate(pipeline_stats).to_list(1)
        stats = stats_result[0] if stats_result else {"avg_rating": 0, "total": 0, "five": 0, "four": 0, "three": 0, "two": 0, "one": 0}
        stats.pop("_id", None)

        # Rating trend (last 30 days, grouped by day)
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        pipeline_trend = [
            {"$match": {**match, "flagged": {"$ne": True}, "created_at": {"$gte": thirty_days_ago}}},
            {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
            {"$group": {"_id": "$date", "avg_rating": {"$avg": "$rating"}, "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        trend = []
        async for doc in db.marketplace_reviews.aggregate(pipeline_trend):
            trend.append({"date": doc["_id"], "avg_rating": round(doc["avg_rating"], 1), "count": doc["count"]})

        # Top reviewed templates
        pipeline_top = [
            {"$match": {"flagged": {"$ne": True}}},
            {"$group": {"_id": "$template_id", "avg_rating": {"$avg": "$rating"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        top_reviewed = []
        async for doc in db.marketplace_reviews.aggregate(pipeline_top):
            top_reviewed.append({"template_id": doc["_id"], "avg_rating": round(doc["avg_rating"], 1), "review_count": doc["count"]})

        # Sentiment (simple: 4-5 = positive, 3 = neutral, 1-2 = negative)
        pos = stats.get("five", 0) + stats.get("four", 0)
        neu = stats.get("three", 0)
        neg = stats.get("two", 0) + stats.get("one", 0)
        total = max(pos + neu + neg, 1)
        sentiment = {"positive_pct": round(pos / total * 100, 1), "neutral_pct": round(neu / total * 100, 1), "negative_pct": round(neg / total * 100, 1)}

        return {"stats": stats, "trend": trend, "top_reviewed": top_reviewed, "sentiment": sentiment}

    # ============ Security Dashboard ============

    @api_router.get("/admin/security-dashboard")
    async def security_dashboard(request: Request):
        user = await get_current_user(request)
        now = datetime.now(timezone.utc)
        day_ago = (now - timedelta(hours=24)).isoformat()
        week_ago = (now - timedelta(days=7)).isoformat()

        # Failed login attempts (24h)
        failed_logins_24h = await db.login_attempts.count_documents({"count": {"$gt": 0}})
        locked_accounts = await db.login_attempts.count_documents({"locked_until": {"$gte": day_ago}})

        # Active sessions
        active_sessions = await db.user_sessions.count_documents({"expires_at": {"$gte": now.isoformat()}})

        # Webhook health
        total_webhooks = await db.webhooks.count_documents({})
        enabled_webhooks = await db.webhooks.count_documents({"enabled": True})
        disabled_webhooks = total_webhooks - enabled_webhooks
        dead_letters = await db.webhook_dead_letters.count_documents({})

        # Webhook delivery stats (7 days)
        pipeline_delivery = [
            {"$match": {"timestamp": {"$gte": week_ago}}},
            {"$group": {"_id": "$success", "count": {"$sum": 1}}},
        ]
        delivery_success = 0
        delivery_fail = 0
        async for doc in db.webhook_deliveries.aggregate(pipeline_delivery):
            if doc["_id"]:
                delivery_success = doc["count"]
            else:
                delivery_fail = doc["count"]

        # API key usage
        api_keys_stored = await db.platform_settings.count_documents({"key": {"$regex": "^integration_"}})

        # Workspace stats
        total_workspaces = await db.workspaces.count_documents({})
        total_users = await db.users.count_documents({})

        # Recent security events
        recent_events = []
        async for evt in db.login_attempts.find(
            {"count": {"$gte": 3}}, {"_id": 0, "email": 1, "count": 1, "locked_until": 1}
        ).sort("locked_until", -1).limit(10):
            recent_events.append({"type": "failed_login", "email": evt.get("email", ""), "attempts": evt.get("count", 0), "locked_until": evt.get("locked_until")})

        return {
            "auth": {
                "failed_logins_24h": failed_logins_24h,
                "locked_accounts": locked_accounts,
                "active_sessions": active_sessions,
                "total_users": total_users,
            },
            "webhooks": {
                "total": total_webhooks, "enabled": enabled_webhooks,
                "disabled": disabled_webhooks, "dead_letters": dead_letters,
                "deliveries_7d": {"success": delivery_success, "failed": delivery_fail,
                    "success_rate": round(delivery_success / max(delivery_success + delivery_fail, 1) * 100, 1)},
            },
            "platform": {
                "total_workspaces": total_workspaces,
                "api_keys_configured": api_keys_stored,
            },
            "recent_events": recent_events,
        }

    @api_router.get("/admin/observability")
    async def observability_dashboard(request: Request):
        """Platform observability — request metrics, error rates, latency."""
        user = await get_current_user(request)
        now = datetime.now(timezone.utc)
        hour_ago = (now - timedelta(hours=1)).isoformat()
        day_ago = (now - timedelta(hours=24)).isoformat()

        # AI call stats (24h)
        ai_pipeline = [
            {"$match": {"created_at": {"$gte": day_ago}}},
            {"$group": {"_id": "$provider", "calls": {"$sum": 1}, "errors": {"$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
                        "avg_latency": {"$avg": {"$ifNull": ["$latency_ms", 0]}}, "total_cost": {"$sum": {"$ifNull": ["$cost_usd", 0]}}}},
        ]
        ai_stats = {}
        try:
            async for doc in db.ai_call_logs.aggregate(ai_pipeline):
                ai_stats[doc["_id"] or "unknown"] = {"calls": doc["calls"], "errors": doc["errors"], "avg_latency_ms": int(doc["avg_latency"]), "cost_usd": round(doc["total_cost"], 4)}
        except Exception as _e:
            import logging; logging.getLogger("routes/routes_advanced_features").warning(f"Suppressed: {_e}")

        # Pipeline/operator stats (24h)
        pipeline_runs = await db.a2a_runs.count_documents({"started_at": {"$gte": day_ago}})
        pipeline_ok = await db.a2a_runs.count_documents({"started_at": {"$gte": day_ago}, "status": "completed"})
        operator_runs = await db.operator_sessions.count_documents({"created_at": {"$gte": day_ago}})
        operator_ok = await db.operator_sessions.count_documents({"created_at": {"$gte": day_ago}, "status": "completed"})

        # Message volume
        messages_1h = await db.messages.count_documents({"created_at": {"$gte": hour_ago}})
        messages_24h = await db.messages.count_documents({"created_at": {"$gte": day_ago}})

        # Error tracking
        try:
            collections = await db.list_collection_names()
            errors_24h = await db.error_tracking.count_documents({"created_at": {"$gte": day_ago}}) if "error_tracking" in collections else 0
        except Exception:
            errors_24h = 0

        return {
            "timestamp": now.isoformat(),
            "ai_providers": ai_stats,
            "pipelines_24h": {"total": pipeline_runs, "completed": pipeline_ok, "success_rate": round(pipeline_ok / max(pipeline_runs, 1) * 100, 1)},
            "operator_24h": {"total": operator_runs, "completed": operator_ok, "success_rate": round(operator_ok / max(operator_runs, 1) * 100, 1)},
            "messages": {"last_1h": messages_1h, "last_24h": messages_24h},
            "errors_24h": errors_24h,
        }


def _get_builtin_templates():
    """Built-in orchestration templates."""
    return [
        {
            "template_id": "otpl_research_summarize",
            "name": "Research & Summarize",
            "description": "Agent 1 researches a topic, Agent 2 summarizes findings into a concise brief.",
            "category": "research",
            "execution_mode": "sequential",
            "steps": [
                {"step_id": "research", "agent_id": "", "prompt_template": "Research the following topic thoroughly: {input}", "depends_on": [], "condition": ""},
                {"step_id": "summarize", "agent_id": "", "prompt_template": "Summarize the following research into a concise 3-paragraph brief: {input}", "depends_on": ["research"], "condition": ""},
            ],
            "tags": ["research", "summarization"], "usage_count": 0, "is_active": True,
        },
        {
            "template_id": "otpl_draft_review_edit",
            "name": "Draft, Review & Edit",
            "description": "Agent 1 drafts content, Agent 2 reviews for quality, Agent 3 applies final edits.",
            "category": "content",
            "execution_mode": "sequential",
            "steps": [
                {"step_id": "draft", "agent_id": "", "prompt_template": "Write a first draft about: {input}", "depends_on": [], "condition": ""},
                {"step_id": "review", "agent_id": "", "prompt_template": "Review this draft for clarity, accuracy, and tone. Provide specific feedback: {input}", "depends_on": ["draft"], "condition": ""},
                {"step_id": "edit", "agent_id": "", "prompt_template": "Apply the review feedback and produce a polished final version: {input}", "depends_on": ["review"], "condition": ""},
            ],
            "tags": ["content", "writing", "editing"], "usage_count": 0, "is_active": True,
        },
        {
            "template_id": "otpl_parallel_analysis",
            "name": "Multi-Perspective Analysis",
            "description": "Multiple agents analyze the same input from different angles simultaneously.",
            "category": "analysis",
            "execution_mode": "parallel",
            "steps": [
                {"step_id": "technical", "agent_id": "", "prompt_template": "Analyze this from a technical/engineering perspective: {input}", "depends_on": [], "condition": ""},
                {"step_id": "business", "agent_id": "", "prompt_template": "Analyze this from a business/market perspective: {input}", "depends_on": [], "condition": ""},
                {"step_id": "user", "agent_id": "", "prompt_template": "Analyze this from a user experience perspective: {input}", "depends_on": [], "condition": ""},
            ],
            "tags": ["analysis", "multi-perspective"], "usage_count": 0, "is_active": True,
        },
        {
            "template_id": "otpl_code_review",
            "name": "Code Review Pipeline",
            "description": "Agent 1 reviews code for bugs, Agent 2 checks style/best practices, Agent 3 suggests optimizations.",
            "category": "development",
            "execution_mode": "sequential",
            "steps": [
                {"step_id": "bugs", "agent_id": "", "prompt_template": "Review this code for bugs and potential issues: {input}", "depends_on": [], "condition": ""},
                {"step_id": "style", "agent_id": "", "prompt_template": "Review this code for style, best practices, and readability: {input}", "depends_on": [], "condition": ""},
                {"step_id": "optimize", "agent_id": "", "prompt_template": "Suggest performance optimizations for this code: {input}", "depends_on": [], "condition": ""},
            ],
            "tags": ["development", "code-review"], "usage_count": 0, "is_active": True,
        },
        {
            "template_id": "otpl_qa_pipeline",
            "name": "Q&A Knowledge Pipeline",
            "description": "Agent 1 retrieves relevant knowledge, Agent 2 formulates a comprehensive answer.",
            "category": "knowledge",
            "execution_mode": "sequential",
            "steps": [
                {"step_id": "retrieve", "agent_id": "", "prompt_template": "Find all relevant information about: {input}", "depends_on": [], "condition": ""},
                {"step_id": "answer", "agent_id": "", "prompt_template": "Using the retrieved information, provide a comprehensive answer to: {input}", "depends_on": ["retrieve"], "condition": ""},
            ],
            "tags": ["knowledge", "qa"], "usage_count": 0, "is_active": True,
        },
    ]
