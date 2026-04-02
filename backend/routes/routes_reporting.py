"""Enterprise Reporting Engine — Event ingestion, analytics aggregation, and reporting.

Captures every AI interaction as a structured event for the three-tier reporting system:
- Super Admin: Full platform telemetry
- Org Admin: Org-scoped usage and cost governance
- Individual User: Personal usage insights

Events are stored in `reporting_events` with pre-computed rollups in `reporting_rollups`.
"""
import uuid
import logging
import os
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

from nexus_config import PROVIDER_PRICING
from nexus_utils import validate_external_url



def estimate_tokens(text):
    """Rough token estimation (~4 chars per token)."""
    return max(1, len(text or "") // 4)


def estimate_cost(provider, input_tokens, output_tokens):
    """Estimate cost in USD based on provider pricing."""
    rates = PROVIDER_PRICING.get(provider, {"input": 5.0, "output": 15.0})
    return round((input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000, 6)


async def log_ai_event(db, user_id, org_id, workspace_id, channel_id,
                        provider, model, agent_key, key_type,
                        input_text, output_text, latency_ms,
                        status_code=200, error_type=None, thread_id=None):
    """Log a single AI interaction event to the reporting pipeline."""
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    cost = estimate_cost(provider, input_tokens, output_tokens)
    now = datetime.now(timezone.utc)

    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
        "timestamp": now.isoformat(),
        "date_key": now.strftime("%Y-%m-%d"),
        "hour_key": now.strftime("%Y-%m-%d-%H"),
        "org_id": org_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "session_id": thread_id,
        "provider": provider,
        "model": model,
        "agent_key": agent_key,
        "key_type": key_type or "platform",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_ms": latency_ms,
        "estimated_cost_usd": cost,
        "status_code": status_code,
        "error_type": error_type,
    }
    try:
        await db.reporting_events.insert_one(event)
    except Exception as e:
        logger.warning(f"Event logging failed: {e}")
    return event


async def compute_rollups(db, date_key=None):
    """Compute daily rollups from raw events. Called by background task."""
    if not date_key:
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {"date_key": date_key}},
        {"$group": {
            "_id": {
                "date": "$date_key",
                "org_id": "$org_id",
                "user_id": "$user_id",
                "provider": "$provider",
                "model": "$model",
                "key_type": "$key_type",
            },
            "total_events": {"$sum": 1},
            "total_input_tokens": {"$sum": "$input_tokens"},
            "total_output_tokens": {"$sum": "$output_tokens"},
            "total_tokens": {"$sum": "$total_tokens"},
            "total_cost_usd": {"$sum": "$estimated_cost_usd"},
            "avg_latency_ms": {"$avg": "$latency_ms"},
            "p95_latency_ms": {"$push": "$latency_ms"},
            "error_count": {"$sum": {"$cond": [{"$ne": ["$error_type", None]}, 1, 0]}},
        }},
    ]
    try:
        results = await db.reporting_events.aggregate(pipeline).to_list(500)
        for r in results:
            key = r["_id"]
            rollup_id = f"roll_{date_key}_{key.get('org_id', 'none')}_{key.get('user_id', '')}_{key.get('provider', '')}_{key.get('model', '')}"
            latencies = sorted(r.get("p95_latency_ms", []) or [])
            p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
            await db.reporting_rollups.update_one(
                {"rollup_id": rollup_id},
                {"$set": {
                    "rollup_id": rollup_id,
                    "granularity": "daily",
                    **key,
                    "total_events": r["total_events"],
                    "total_input_tokens": r["total_input_tokens"],
                    "total_output_tokens": r["total_output_tokens"],
                    "total_tokens": r["total_tokens"],
                    "total_cost_usd": r["total_cost_usd"],
                    "avg_latency_ms": r["avg_latency_ms"],
                    "p95_latency_ms": p95,
                    "error_count": r["error_count"],
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
        logger.info(f"Computed {len(results)} daily rollups for {date_key}")
    except Exception as e:
        logger.warning(f"Rollup computation failed: {e}")


def register_reporting_routes(api_router, db, get_current_user):
    """Register the enterprise reporting API endpoints."""

    # ============ SUPER ADMIN — Platform-Level ============

    @api_router.get("/reports/platform/health")
    async def platform_health(request: Request):
        """Platform health metrics — Super Admin only."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        week_ago = (now - timedelta(days=7)).isoformat()
        month_ago = (now - timedelta(days=30)).isoformat()

        dau = await db.reporting_events.distinct("user_id", {"timestamp": {"$gte": today}})
        wau = await db.reporting_events.distinct("user_id", {"timestamp": {"$gte": week_ago}})
        mau = await db.reporting_events.distinct("user_id", {"timestamp": {"$gte": month_ago}})
        total_orgs = await db.organizations.count_documents({})
        total_events_today = await db.reporting_events.count_documents({"timestamp": {"$gte": today}})

        # Latency stats
        latency_pipeline = [
            {"$match": {"timestamp": {"$gte": today}}},
            {"$group": {"_id": None,
                        "avg": {"$avg": "$latency_ms"},
                        "p95": {"$percentile": {"input": "$latency_ms", "p": [0.95], "method": "approximate"}},
                        "p99": {"$percentile": {"input": "$latency_ms", "p": [0.99], "method": "approximate"}},
                        }},
        ]
        try:
            latency = await db.reporting_events.aggregate(latency_pipeline).to_list(1)
            latency_data = latency[0] if latency else {"avg": 0, "p95": [0], "p99": [0]}
        except Exception:
            latency_data = {"avg": 0, "p95": [0], "p99": [0]}

        # Error rates by provider
        error_pipeline = [
            {"$match": {"timestamp": {"$gte": today}}},
            {"$group": {"_id": "$provider",
                        "total": {"$sum": 1},
                        "errors": {"$sum": {"$cond": [{"$ne": ["$error_type", None]}, 1, 0]}}}},
        ]
        error_rates = await db.reporting_events.aggregate(error_pipeline).to_list(20)

        # Token consumption by provider
        token_pipeline = [
            {"$match": {"timestamp": {"$gte": today}}},
            {"$group": {"_id": "$provider",
                        "tokens": {"$sum": "$total_tokens"},
                        "cost": {"$sum": "$estimated_cost_usd"}}},
        ]
        token_data = await db.reporting_events.aggregate(token_pipeline).to_list(20)

        # BYOK vs Platform split
        key_pipeline = [
            {"$match": {"timestamp": {"$gte": month_ago}}},
            {"$group": {"_id": "$key_type", "count": {"$sum": 1}, "tokens": {"$sum": "$total_tokens"}}},
        ]
        key_split = await db.reporting_events.aggregate(key_pipeline).to_list(5)

        return {
            "dau": len(dau), "wau": len(wau), "mau": len(mau),
            "total_orgs": total_orgs,
            "events_today": total_events_today,
            "latency": {
                "avg_ms": round(latency_data.get("avg", 0) or 0),
                "p95_ms": round((latency_data.get("p95", [0]) or [0])[0] if isinstance(latency_data.get("p95"), list) else latency_data.get("p95", 0)),
                "p99_ms": round((latency_data.get("p99", [0]) or [0])[0] if isinstance(latency_data.get("p99"), list) else latency_data.get("p99", 0)),
            },
            "error_rates": {r["_id"]: {"total": r["total"], "errors": r["errors"], "rate": round(r["errors"] / max(r["total"], 1) * 100, 1)} for r in error_rates},
            "token_consumption": {r["_id"]: {"tokens": r["tokens"], "cost_usd": round(r["cost"], 4)} for r in token_data},
            "key_type_split": {r["_id"]: {"count": r["count"], "tokens": r["tokens"]} for r in key_split},
        }

    @api_router.get("/reports/platform/business")
    async def platform_business(request: Request):
        """Business intelligence metrics — Super Admin only."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        now = datetime.now(timezone.utc)
        month_ago = (now - timedelta(days=30)).isoformat()

        # Revenue by org (from payments)
        revenue_pipeline = [
            {"$match": {"payment_status": "paid"}},
            {"$group": {"_id": "$plan_id", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        ]
        revenue = await db.payment_transactions.aggregate(revenue_pipeline).to_list(10)

        # Feature adoption
        feature_counts = {
            "multi_agent": await db.channels.count_documents({"ai_agents.2": {"$exists": True}}),
            "persist_collab": await db.channels.count_documents({"auto_collab_persist": True}),
            "directives": await db.directives.count_documents({"is_active": True}),
            "code_repo": await db.code_repos.count_documents({}),
            "wiki": await db.wiki_pages.count_documents({"is_deleted": {"$ne": True}}),
            "browser": 0,
        }

        # Org growth (signups per week for last 8 weeks)
        growth = []
        for i in range(8):
            week_start = (now - timedelta(weeks=i+1)).isoformat()
            week_end = (now - timedelta(weeks=i)).isoformat()
            count = await db.organizations.count_documents({"created_at": {"$gte": week_start, "$lt": week_end}})
            growth.append({"week": i, "signups": count})

        # Churn indicators (users with declining usage)
        churn_pipeline = [
            {"$match": {"timestamp": {"$gte": month_ago}}},
            {"$group": {"_id": "$user_id", "events": {"$sum": 1}, "last_active": {"$max": "$timestamp"}}},
            {"$match": {"events": {"$lt": 5}}},
            {"$count": "at_risk"},
        ]
        churn = await db.reporting_events.aggregate(churn_pipeline).to_list(1)
        churn_count = churn[0]["at_risk"] if churn else 0

        return {
            "revenue_by_plan": {r["_id"]: {"total": r["total"], "count": r["count"]} for r in revenue},
            "feature_adoption": feature_counts,
            "org_growth_weekly": growth,
            "churn_risk_users": churn_count,
        }

    # ============ ORG ADMIN — Org-Level ============

    @api_router.get("/reports/org/{org_id}/usage")
    async def org_usage(org_id: str, request: Request, days: int = 30):
        """Org-scoped usage metrics."""
        user = await get_current_user(request)
        # Verify org admin access
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
        )
        from routes_admin import is_super_admin
        if not membership and not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Org admin access required")

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get org workspace IDs
        org_workspaces = await db.workspaces.find({"org_id": org_id}, {"_id": 0, "workspace_id": 1}).to_list(100)
        ws_ids = [w["workspace_id"] for w in org_workspaces]

        # Aggregate usage
        pipeline = [
            {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_events": {"$sum": 1},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "unique_users": {"$addToSet": "$user_id"},
                "avg_latency": {"$avg": "$latency_ms"},
            }},
        ]
        agg = await db.reporting_events.aggregate(pipeline).to_list(1)
        summary = agg[0] if agg else {"total_events": 0, "total_tokens": 0, "total_cost": 0, "unique_users": [], "avg_latency": 0}

        # Top users
        top_users_pipeline = [
            {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$user_id", "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}, "events": {"$sum": 1}}},
            {"$sort": {"tokens": -1}},
            {"$limit": 10},
        ]
        top_users = await db.reporting_events.aggregate(top_users_pipeline).to_list(10)

        # Model distribution
        model_pipeline = [
            {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$provider", "tokens": {"$sum": "$total_tokens"}, "events": {"$sum": 1}}},
            {"$sort": {"tokens": -1}},
        ]
        model_dist = await db.reporting_events.aggregate(model_pipeline).to_list(20)

        # Daily trend
        daily_pipeline = [
            {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$date_key", "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}, "events": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        daily = await db.reporting_events.aggregate(daily_pipeline).to_list(90)

        # BYOK vs platform split
        key_split_pipeline = [
            {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$key_type", "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}}},
        ]
        key_split = await db.reporting_events.aggregate(key_split_pipeline).to_list(5)

        return {
            "period_days": days,
            "summary": {
                "total_events": summary["total_events"],
                "total_tokens": summary["total_tokens"],
                "total_cost_usd": round(summary["total_cost"], 4),
                "active_users": len(summary.get("unique_users") or []),
                "avg_latency_ms": round(summary.get("avg_latency", 0) or 0),
            },
            "top_users": [{"user_id": u["_id"], "tokens": u["tokens"], "cost_usd": round(u["cost"], 4), "events": u["events"]} for u in top_users],
            "model_distribution": [{"provider": m["_id"], "tokens": m["tokens"], "events": m["events"]} for m in model_dist],
            "daily_trend": [{"date": d["_id"], "tokens": d["tokens"], "cost_usd": round(d["cost"], 4), "events": d["events"]} for d in daily],
            "key_type_split": {r["_id"]: {"tokens": r["tokens"], "cost_usd": round(r["cost"], 4)} for r in key_split},
        }

    @api_router.get("/reports/org/{org_id}/users")
    async def org_user_report(org_id: str, request: Request, days: int = 30):
        """Per-user activity report for org admin."""
        user = await get_current_user(request)
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
        )
        from routes_admin import is_super_admin
        if not membership and not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Org admin access required")

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        org_workspaces = await db.workspaces.find({"org_id": org_id}, {"_id": 0, "workspace_id": 1}).to_list(100)
        ws_ids = [w["workspace_id"] for w in org_workspaces]

        pipeline = [
            {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": since}}},
            {"$group": {
                "_id": "$user_id",
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$estimated_cost_usd"},
                "events": {"$sum": 1},
                "sessions": {"$addToSet": "$session_id"},
                "providers": {"$addToSet": "$provider"},
                "last_active": {"$max": "$timestamp"},
            }},
            {"$sort": {"tokens": -1}},
        ]
        user_data = await db.reporting_events.aggregate(pipeline).to_list(500)

        # Enrich with user names
        for ud in user_data:
            u = await db.users.find_one({"user_id": ud["_id"]}, {"_id": 0, "name": 1, "email": 1})
            ud["name"] = u.get("name", "") if u else ""
            ud["email"] = u.get("email", "") if u else ""

        return {"users": [{
            "user_id": u["_id"], "name": u.get("name", ""), "email": u.get("email", ""),
            "tokens": u["tokens"], "cost_usd": round(u["cost"], 4), "events": u["events"],
            "session_count": len(u.get("sessions") or []), "providers_used": u.get("providers") or [],
            "last_active": u.get("last_active", ""),
        } for u in user_data]}

    # ============ INDIVIDUAL USER — Personal ============

    @api_router.get("/reports/me/usage")
    async def my_usage(request: Request, days: int = 30):
        """Personal usage metrics for the current user."""
        user = await get_current_user(request)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        pipeline = [
            {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_tokens": {"$sum": "$total_tokens"},
                "input_tokens": {"$sum": "$input_tokens"},
                "output_tokens": {"$sum": "$output_tokens"},
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "total_events": {"$sum": 1},
                "avg_latency": {"$avg": "$latency_ms"},
                "active_days": {"$addToSet": "$date_key"},
            }},
        ]
        agg = await db.reporting_events.aggregate(pipeline).to_list(1)
        summary = agg[0] if agg else {}

        # By provider
        provider_pipeline = [
            {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$provider", "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}, "events": {"$sum": 1}}},
            {"$sort": {"tokens": -1}},
        ]
        by_provider = await db.reporting_events.aggregate(provider_pipeline).to_list(20)

        # Daily trend
        daily_pipeline = [
            {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$date_key", "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}}},
            {"$sort": {"_id": 1}},
        ]
        daily = await db.reporting_events.aggregate(daily_pipeline).to_list(90)

        # Favorite model
        fav_pipeline = [
            {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$model", "tokens": {"$sum": "$total_tokens"}}},
            {"$sort": {"tokens": -1}},
            {"$limit": 1},
        ]
        fav = await db.reporting_events.aggregate(fav_pipeline).to_list(1)

        return {
            "period_days": days,
            "total_tokens": summary.get("total_tokens", 0),
            "input_tokens": summary.get("input_tokens", 0),
            "output_tokens": summary.get("output_tokens", 0),
            "total_cost_usd": round(summary.get("total_cost", 0), 4),
            "total_sessions": summary.get("total_events", 0),
            "avg_latency_ms": round(summary.get("avg_latency", 0) or 0),
            "active_days": len(summary.get("active_days") or []),
            "io_ratio": round(summary.get("input_tokens", 0) / max(summary.get("output_tokens", 1), 1), 2),
            "favorite_model": fav[0]["_id"] if fav else None,
            "by_provider": [{"provider": p["_id"], "tokens": p["tokens"], "cost_usd": round(p["cost"], 4)} for p in by_provider],
            "daily_trend": [{"date": d["_id"], "tokens": d["tokens"], "cost_usd": round(d["cost"], 4)} for d in daily],
        }

    # ============ EXPORTS ============

    @api_router.get("/reports/export")
    async def export_report(request: Request, report_type: str = "usage", format: str = "json",
                             org_id: str = None, days: int = 30):
        """Export reports in JSON, CSV, or PDF format."""
        user = await get_current_user(request)

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = {"timestamp": {"$gte": since}}

        # Scope based on access
        from routes_admin import is_super_admin
        is_admin = await is_super_admin(db, user["user_id"])
        if org_id and not is_admin:
            membership = await db.org_memberships.find_one(
                {"org_id": org_id, "user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
            )
            if not membership:
                raise HTTPException(403, "Access denied")
            org_ws = await db.workspaces.find({"org_id": org_id}, {"_id": 0, "workspace_id": 1}).to_list(100)
            query["workspace_id"] = {"$in": [w["workspace_id"] for w in org_ws]}
        elif not is_admin:
            query["user_id"] = user["user_id"]

        events = await db.reporting_events.find(query, {"_id": 0}).sort("timestamp", -1).limit(500).to_list(500)

        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            if events:
                fields = ["timestamp", "provider", "model", "agent_key", "key_type", "input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd", "latency_ms", "status_code"]
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                for e in events:
                    writer.writerow({k: e.get(k, "") for k in fields})
            return Response(content=output.getvalue(), media_type="text/csv",
                          headers={"Content-Disposition": f"attachment; filename=nexus_report_{report_type}.csv"})

        if format == "pdf":
            # Generate simple PDF report
            try:
                pdf_content = _generate_pdf_report(events, report_type, days)
                return Response(content=pdf_content, media_type="application/pdf",
                              headers={"Content-Disposition": f"attachment; filename=nexus_report_{report_type}.pdf"})
            except Exception as pdf_err:
                logger.error(f"PDF generation error: {pdf_err}")
                raise HTTPException(500, f"PDF generation failed: {str(pdf_err)[:100]}")

        return {"events": events[:1000], "total": len(events), "format": "json"}

    # ============ ALERTING ============

    @api_router.get("/reports/alerts")
    async def get_alerts(request: Request):
        """Get active reporting alerts."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        alerts = await db.reporting_alerts.find(
            {"resolved": False}, {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        return {"alerts": alerts}

    @api_router.post("/reports/alerts/{alert_id}/resolve")
    async def resolve_alert(alert_id: str, request: Request):
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        await db.reporting_alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"resolved": True, "resolved_by": user["user_id"], "resolved_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"resolved": True}

    # ============ BUDGET & COST GOVERNANCE (Org Admin) ============

    @api_router.put("/reports/org/{org_id}/budget")
    async def set_org_budget(org_id: str, request: Request):
        """Set monthly token/cost budget for an org — org admin only."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
        )
        if not membership and not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Org admin access required")
        body = await request.json()
        # Validate budget fields
        cost_limit = body.get("monthly_cost_limit_usd")
        token_limit = body.get("monthly_token_limit")
        daily_limit = body.get("per_user_daily_limit")
        if cost_limit is not None and (not isinstance(cost_limit, (int, float)) or cost_limit < 0):
            raise HTTPException(422, "monthly_cost_limit_usd must be a non-negative number")
        if token_limit is not None and (not isinstance(token_limit, (int, float)) or token_limit < 0):
            raise HTTPException(422, "monthly_token_limit must be a non-negative number")
        if daily_limit is not None and (not isinstance(daily_limit, (int, float)) or daily_limit < 0):
            raise HTTPException(422, "per_user_daily_limit must be a non-negative number")
        await db.org_budgets.update_one(
            {"org_id": org_id},
            {"$set": {
                "org_id": org_id,
                "monthly_token_limit": body.get("monthly_token_limit"),
                "monthly_cost_limit_usd": body.get("monthly_cost_limit_usd"),
                "per_user_daily_limit": body.get("per_user_daily_limit"),
                "updated_by": user["user_id"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"status": "budget_set"}

    @api_router.get("/reports/org/{org_id}/budget")
    async def get_org_budget(org_id: str, request: Request):
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
        )
        if not membership and not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Org admin access required")
        budget = await db.org_budgets.find_one({"org_id": org_id}, {"_id": 0})
        return budget or {"org_id": org_id, "monthly_token_limit": None, "monthly_cost_limit_usd": None}

    # ============ SCHEDULED REPORTS ============

    @api_router.post("/reports/schedules")
    async def create_report_schedule(request: Request):
        """Create a scheduled report delivery (daily/weekly/monthly via email)."""
        user = await get_current_user(request)
        body = await request.json()
        cadence = body.get("cadence", "weekly")
        if cadence not in ("daily", "weekly", "monthly"):
            raise HTTPException(400, "cadence must be daily, weekly, or monthly")
        schedule = {
            "schedule_id": f"rsched_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "email": body.get("email", user.get("email", "")),
            "cadence": cadence,
            "report_type": body.get("report_type", "usage"),
            "org_id": body.get("org_id"),
            "workspace_id": body.get("workspace_id"),
            "enabled": True,
            "last_sent": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.report_schedules.insert_one(schedule)
        return {"schedule_id": schedule["schedule_id"], "cadence": cadence}

    @api_router.get("/reports/schedules")
    async def list_report_schedules(request: Request):
        user = await get_current_user(request)
        schedules = await db.report_schedules.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).to_list(20)
        return {"schedules": schedules}

    @api_router.delete("/reports/schedules/{schedule_id}")
    async def delete_report_schedule(schedule_id: str, request: Request):
        user = await get_current_user(request)
        await db.report_schedules.delete_one({"schedule_id": schedule_id, "user_id": user["user_id"]})
        return {"deleted": True}

    # ============ WEBHOOK ALERTS ============

    @api_router.post("/reports/webhooks")
    async def create_alert_webhook(request: Request):
        """Register a webhook URL for alert delivery (Slack, PagerDuty, etc.)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        body = await request.json()
        url = body.get("url", "").strip()
        if not url or not url.startswith("http"):
            raise HTTPException(400, "Valid webhook URL required")
        webhook = {
            "webhook_id": f"wh_{uuid.uuid4().hex[:12]}",
            "url": url,
            "name": body.get("name", "Alert Webhook"),
            "events": body.get("events", ["provider_error", "budget_threshold"]),
            "enabled": True,
            "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.alert_webhooks.insert_one(webhook)
        return {"webhook_id": webhook["webhook_id"]}

    @api_router.get("/reports/webhooks")
    async def list_alert_webhooks(request: Request):
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        hooks = await db.alert_webhooks.find({"enabled": True}, {"_id": 0}).to_list(20)
        return {"webhooks": hooks}

    @api_router.delete("/reports/webhooks/{webhook_id}")
    async def delete_alert_webhook(webhook_id: str, request: Request):
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        await db.alert_webhooks.delete_one({"webhook_id": webhook_id})
        return {"deleted": True}

    # ============ NLP ANALYTICS QUERY ============

    @api_router.post("/reports/query")
    async def natural_language_query(request: Request):
        """Answer analytics questions in natural language."""
        user = await get_current_user(request)
        body = await request.json()
        question = body.get("question", "").strip().lower()
        if not question:
            raise HTTPException(400, "question required")
        
        now = datetime.now(timezone.utc)
        result = {"question": question, "answer": "", "data": {}}
        
        if "token" in question and ("today" in question or "this" in question):
            since = now.replace(hour=0, minute=0, second=0).isoformat()
            agg = await db.reporting_events.aggregate([
                {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
                {"$group": {"_id": None, "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}}},
            ]).to_list(1)
            d = agg[0] if agg else {"tokens": 0, "cost": 0}
            result["answer"] = f"You've used {d['tokens']:,} tokens today (estimated cost: ${d['cost']:.4f})."
            result["data"] = d
        elif "last week" in question or "past week" in question:
            since = (now - timedelta(days=7)).isoformat()
            agg = await db.reporting_events.aggregate([
                {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
                {"$group": {"_id": None, "tokens": {"$sum": "$total_tokens"}, "cost": {"$sum": "$estimated_cost_usd"}, "events": {"$sum": 1}}},
            ]).to_list(1)
            d = agg[0] if agg else {"tokens": 0, "cost": 0, "events": 0}
            result["answer"] = f"Last 7 days: {d['tokens']:,} tokens across {d['events']} interactions (${d['cost']:.4f})."
            result["data"] = d
        elif "most used" in question or "favorite" in question or "popular" in question:
            agg = await db.reporting_events.aggregate([
                {"$match": {"user_id": user["user_id"]}},
                {"$group": {"_id": "$provider", "tokens": {"$sum": "$total_tokens"}}},
                {"$sort": {"tokens": -1}}, {"$limit": 3},
            ]).to_list(3)
            if agg:
                top = ", ".join(f"{a['_id']} ({a['tokens']:,} tokens)" for a in agg)
                result["answer"] = f"Your most used providers: {top}."
                result["data"] = {"top_providers": agg}
            else:
                result["answer"] = "No usage data found yet."
        else:
            result["answer"] = "I can answer questions like: 'How many tokens did I use today?', 'What's my usage last week?', 'What's my most used model?'"
        
        return result

    # ============ COST ALLOCATION TAGS ============

    @api_router.put("/reports/org/{org_id}/cost-tags")
    async def set_cost_allocation_tags(org_id: str, request: Request):
        """Set cost allocation tags for an org (department-level cost attribution)."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user["user_id"], "role": {"$in": ["admin", "owner"]}}, {"_id": 0}
        )
        if not membership and not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Org admin required")
        body = await request.json()
        tags = body.get("tags") or []
        await db.cost_allocation_tags.update_one(
            {"org_id": org_id},
            {"$set": {"org_id": org_id, "tags": tags, "updated_by": user["user_id"],
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"org_id": org_id, "tags": tags}

    @api_router.get("/reports/org/{org_id}/cost-tags")
    async def get_cost_allocation_tags(org_id: str, request: Request):
        await get_current_user(request)
        doc = await db.cost_allocation_tags.find_one({"org_id": org_id}, {"_id": 0})
        return doc or {"org_id": org_id, "tags": []}


def _generate_pdf_report(events, report_type, days):
    """Generate a proper PDF report using fpdf2."""
    from fpdf import FPDF
    
    total_tokens = sum(e.get("total_tokens", 0) for e in events)
    total_cost = sum(e.get("estimated_cost_usd", 0) for e in events)
    providers = {}
    for e in events:
        p = e.get("provider", "unknown")
        if p not in providers:
            providers[p] = {"tokens": 0, "cost": 0, "events": 0}
        providers[p]["tokens"] += e.get("total_tokens", 0)
        providers[p]["cost"] += e.get("estimated_cost_usd", 0)
        providers[p]["events"] += 1

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    
    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, f"Nexus Platform - {report_type.title()} Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Period: Last {days} days | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    
    # Summary
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total Events: {len(events):,}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total Tokens: {total_tokens:,}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Estimated Cost: ${total_cost:,.4f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    
    # Provider breakdown table
    if providers:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "By Provider", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(50, 6, "Provider", border=1)
        pdf.cell(40, 6, "Tokens", border=1, align="R")
        pdf.cell(35, 6, "Cost (USD)", border=1, align="R")
        pdf.cell(30, 6, "Events", border=1, align="R")
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for p, d in sorted(providers.items(), key=lambda x: -x[1]["tokens"]):
            pdf.cell(50, 6, p[:20], border=1)
            pdf.cell(40, 6, f"{d['tokens']:,}", border=1, align="R")
            pdf.cell(35, 6, f"${d['cost']:,.4f}", border=1, align="R")
            pdf.cell(30, 6, str(d["events"]), border=1, align="R")
            pdf.ln()
    
    return bytes(pdf.output())


async def run_alerting_check(db):
    """Background task to check for anomalies and create alerts."""
    now = datetime.now(timezone.utc)
    hour_ago = (now - timedelta(hours=1)).isoformat()

    # Check error rates
    error_pipeline = [
        {"$match": {"timestamp": {"$gte": hour_ago}}},
        {"$group": {"_id": "$provider", "total": {"$sum": 1},
                    "errors": {"$sum": {"$cond": [{"$ne": ["$error_type", None]}, 1, 0]}}}},
    ]
    try:
        rates = await db.reporting_events.aggregate(error_pipeline).to_list(20)
        for r in rates:
            if r["total"] > 10 and r["errors"] / r["total"] > 0.05:
                alert_id = f"alert_{uuid.uuid4().hex[:12]}"
                existing = await db.reporting_alerts.find_one(
                    {"alert_type": "provider_error", "provider": r["_id"], "resolved": False}, {"_id": 0}
                )
                if not existing:
                    alert_data = {
                        "alert_id": alert_id,
                        "alert_type": "provider_error",
                        "provider": r["_id"],
                        "severity": "high",
                        "message": f"{r['_id']} error rate at {r['errors']/r['total']*100:.1f}% ({r['errors']}/{r['total']} requests in last hour)",
                        "resolved": False,
                        "created_at": now.isoformat(),
                    }
                    await db.reporting_alerts.insert_one(alert_data)
                    await deliver_alert_webhooks(db, alert_data)

        # Check budget thresholds
        budgets = await db.org_budgets.find({"monthly_cost_limit_usd": {"$ne": None}}, {"_id": 0}).to_list(100)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        for budget in budgets:
            org_ws = await db.workspaces.find({"org_id": budget["org_id"]}, {"_id": 0, "workspace_id": 1}).to_list(50)
            ws_ids = [w["workspace_id"] for w in org_ws]
            if not ws_ids:
                continue
            cost_agg = await db.reporting_events.aggregate([
                {"$match": {"workspace_id": {"$in": ws_ids}, "timestamp": {"$gte": month_start}}},
                {"$group": {"_id": None, "cost": {"$sum": "$estimated_cost_usd"}}},
            ]).to_list(1)
            if cost_agg:
                current_cost = cost_agg[0]["cost"]
                limit = budget["monthly_cost_limit_usd"]
                pct = current_cost / limit * 100 if limit else 0
                if pct >= 90:
                    existing = await db.reporting_alerts.find_one(
                        {"alert_type": "budget_threshold", "org_id": budget["org_id"], "resolved": False}, {"_id": 0}
                    )
                    if not existing:
                        await db.reporting_alerts.insert_one({
                            "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
                            "alert_type": "budget_threshold",
                            "org_id": budget["org_id"],
                            "severity": "high" if pct >= 100 else "warning",
                            "message": f"Org budget at {pct:.0f}% (${current_cost:.2f} / ${limit:.2f})",
                            "resolved": False,
                            "created_at": now.isoformat(),
                        })
    except Exception as e:
        logger.warning(f"Alerting check failed: {e}")



async def deliver_alert_webhooks(db, alert):
    """Send alert to all registered webhook URLs."""
    import httpx
    hooks = await db.alert_webhooks.find({"enabled": True}, {"_id": 0}).to_list(20)
    for hook in hooks:
        if alert.get("alert_type") not in hook.get("events") or []:
            continue
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(hook["url"], json={
                    "source": "nexus-platform",
                    "alert_id": alert.get("alert_id"),
                    "alert_type": alert.get("alert_type"),
                    "severity": alert.get("severity"),
                    "message": alert.get("message"),
                    "timestamp": alert.get("created_at"),
                })
        except Exception as e:
            logger.warning(f"Webhook delivery failed for {hook.get('webhook_id')}: {e}")


async def run_scheduled_reports(db):
    """Check and send scheduled reports that are due."""
    now = datetime.now(timezone.utc)
    schedules = await db.report_schedules.find({"enabled": True}, {"_id": 0}).to_list(100)
    
    for sched in schedules:
        last = sched.get("last_sent")
        cadence = sched.get("cadence", "weekly")
        
        # Check if due
        due = False
        if not last:
            due = True
        else:
            last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
            if cadence == "daily" and (now - last_dt).days >= 1:
                due = True
            elif cadence == "weekly" and (now - last_dt).days >= 7:
                due = True
            elif cadence == "monthly" and (now - last_dt).days >= 28:
                due = True
        
        if not due:
            continue
        
        # Generate and send report
        try:
            days = {"daily": 1, "weekly": 7, "monthly": 30}.get(cadence, 7)
            since = (now - timedelta(days=days)).isoformat()
            query = {"timestamp": {"$gte": since}}
            if sched.get("org_id"):
                org_ws = await db.workspaces.find({"org_id": sched["org_id"]}, {"_id": 0, "workspace_id": 1}).to_list(100)
                query["workspace_id"] = {"$in": [w["workspace_id"] for w in org_ws]}
            elif sched.get("workspace_id"):
                query["workspace_id"] = sched["workspace_id"]
            else:
                query["user_id"] = sched["user_id"]
            
            events = await db.reporting_events.find(query, {"_id": 0}).to_list(500)
            total_tokens = sum(e.get("total_tokens", 0) for e in events)
            total_cost = sum(e.get("estimated_cost_usd", 0) for e in events)
            
            from routes_email import send_email
            html = (
                f"<h2>Nexus {cadence.title()} Report</h2>"
                f"<p>Period: Last {days} days</p>"
                f"<table style='border-collapse:collapse'>"
                f"<tr><td style='padding:4px 12px;border:1px solid #ddd'><b>Events</b></td><td style='padding:4px 12px;border:1px solid #ddd'>{len(events):,}</td></tr>"
                f"<tr><td style='padding:4px 12px;border:1px solid #ddd'><b>Tokens</b></td><td style='padding:4px 12px;border:1px solid #ddd'>{total_tokens:,}</td></tr>"
                f"<tr><td style='padding:4px 12px;border:1px solid #ddd'><b>Est. Cost</b></td><td style='padding:4px 12px;border:1px solid #ddd'>${total_cost:.4f}</td></tr>"
                f"</table>"
                f"<p style='color:#888;font-size:12px'>Generated by Nexus Platform</p>"
            )
            await send_email(sched["email"], f"Nexus {cadence.title()} Usage Report", html)
            await db.report_schedules.update_one(
                {"schedule_id": sched["schedule_id"]},
                {"$set": {"last_sent": now.isoformat()}}
            )
            logger.info(f"Sent {cadence} report to {sched['email']}")
        except Exception as e:
            logger.warning(f"Scheduled report failed for {sched.get('schedule_id')}: {e}")
