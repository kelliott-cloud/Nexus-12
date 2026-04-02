"""AI Cost Intelligence — Real-time cost tracking, budgets, alerts, and smart model routing.

Provides granular cost attribution per workspace/project/agent/user with budget caps and alerts.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



def register_cost_intelligence_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.get("/workspaces/{ws_id}/costs")
    async def get_workspace_costs(ws_id: str, request: Request, period: str = "30d"):
        """Real-time cost dashboard for a workspace."""
        user = await get_current_user(request)
        
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        # Aggregate from reporting_events
        pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
            {"$group": {
                "_id": "$agent_key",
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "total_tokens_in": {"$sum": "$tokens_in"},
                "total_tokens_out": {"$sum": "$tokens_out"},
                "call_count": {"$sum": 1},
            }}
        ]
        
        by_model = []
        async for doc in db.reporting_events.aggregate(pipeline):
            by_model.append({
                "model": doc["_id"] or "unknown",
                "cost_usd": round(doc["total_cost"], 4),
                "tokens_in": doc["total_tokens_in"],
                "tokens_out": doc["total_tokens_out"],
                "calls": doc["call_count"],
            })
        
        total_cost = sum(m["cost_usd"] for m in by_model)
        total_calls = sum(m["calls"] for m in by_model)
        
        # Daily breakdown
        daily_pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
            {"$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "cost": {"$sum": "$estimated_cost_usd"},
                "calls": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
        ]
        daily = []
        async for doc in db.reporting_events.aggregate(daily_pipeline):
            daily.append({"date": doc["_id"], "cost_usd": round(doc["cost"], 4), "calls": doc["calls"]})
        
        return {
            "period": period,
            "total_cost_usd": round(total_cost, 2),
            "total_calls": total_calls,
            "by_model": sorted(by_model, key=lambda x: x["cost_usd"], reverse=True),
            "daily": daily,
            "avg_cost_per_call": round(total_cost / max(total_calls, 1), 4),
        }

    @api_router.get("/workspaces/{ws_id}/costs/actual")
    async def get_actual_costs(ws_id: str, request: Request, period: str = "monthly"):
        """Actual costs computed by the hourly batch job, grouped by provider and model."""
        user = await get_current_user(request)

        snapshots = await db.cost_snapshots.find(
            {"workspace_id": ws_id, "period": period},
            {"_id": 0}
        ).sort("actual_cost_usd", -1).to_list(100)

        total_doc = await db.cost_snapshots.find_one(
            {"workspace_id": ws_id, "period": "monthly_total"},
            {"_id": 0}
        )

        return {
            "period": period,
            "by_model": snapshots,
            "totals": total_doc or {},
            "last_computed": snapshots[0].get("computed_at") if snapshots else None,
        }

    @api_router.post("/workspaces/{ws_id}/costs/refresh")
    async def refresh_costs(ws_id: str, request: Request):
        """Manually trigger a cost snapshot refresh for this workspace."""
        user = await get_current_user(request)
        from cost_batch_job import run_cost_snapshot
        await run_cost_snapshot(db)
        return {"message": "Cost snapshot refreshed"}

    @api_router.get("/workspaces/{ws_id}/costs/by-project")
    async def costs_by_project(ws_id: str, request: Request):
        user = await get_current_user(request)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": cutoff}, "event_type": "ai_call"}},
            {"$group": {"_id": "$channel_id", "cost": {"$sum": "$estimated_cost_usd"}, "calls": {"$sum": 1}}},
            {"$sort": {"cost": -1}},
        ]
        
        results = []
        async for doc in db.reporting_events.aggregate(pipeline):
            ch = await db.channels.find_one({"channel_id": doc["_id"]}, {"_id": 0, "name": 1})
            results.append({
                "channel_id": doc["_id"],
                "channel_name": ch.get("name", "") if ch else "",
                "cost_usd": round(doc["cost"], 4),
                "calls": doc["calls"],
            })
        
        return {"by_channel": results}

    # ============ Budget Caps ============

    @api_router.get("/workspaces/{ws_id}/budget")
    async def get_budget(ws_id: str, request: Request):
        user = await get_current_user(request)
        budget = await db.workspace_budgets.find_one({"workspace_id": ws_id}, {"_id": 0})
        if not budget:
            return {"workspace_id": ws_id, "monthly_cap_usd": 0, "alert_threshold_pct": 80, "current_month_spend": 0}
        
        # Calculate current month spend
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
        pipeline = [
            {"$match": {"workspace_id": ws_id, "created_at": {"$gte": month_start}, "event_type": "ai_call"}},
            {"$group": {"_id": None, "total": {"$sum": "$estimated_cost_usd"}}},
        ]
        total = 0
        async for doc in db.reporting_events.aggregate(pipeline):
            total = doc["total"]
        
        budget["current_month_spend"] = round(total, 2)
        budget["pct_used"] = round(total / max(budget.get("monthly_cap_usd", 1), 0.01) * 100, 1) if budget.get("monthly_cap_usd") else 0
        return budget

    @api_router.put("/workspaces/{ws_id}/budget")
    async def set_budget(ws_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        await db.workspace_budgets.update_one(
            {"workspace_id": ws_id},
            {"$set": {
                "workspace_id": ws_id,
                "monthly_cap_usd": body.get("monthly_cap_usd", 0),
                "alert_threshold_pct": body.get("alert_threshold_pct", 80),
                "per_user_limit_usd": body.get("per_user_limit_usd", 0),
                "updated_by": user["user_id"],
                "updated_at": now_iso(),
            }},
            upsert=True,
        )
        return {"message": "Budget updated"}

    # ============ Prompt Library ============

    @api_router.get("/workspaces/{ws_id}/prompts")
    async def list_prompts(ws_id: str, request: Request, category: str = None):
        user = await get_current_user(request)
        query = {"workspace_id": ws_id}
        if category:
            query["category"] = category
        prompts = await db.prompt_library.find(query, {"_id": 0}).sort("use_count", -1).to_list(100)
        return prompts

    @api_router.post("/workspaces/{ws_id}/prompts")
    async def save_prompt(ws_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        prompt_id = f"prompt_{uuid.uuid4().hex[:12]}"
        prompt = {
            "prompt_id": prompt_id,
            "workspace_id": ws_id,
            "title": body.get("title", ""),
            "content": body.get("content", ""),
            "category": body.get("category", "general"),
            "variables": body.get("variables") or [],
            "tags": body.get("tags") or [],
            "use_count": 0,
            "avg_rating": 0,
            "avg_cost": 0,
            "created_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.prompt_library.insert_one(prompt)
        prompt.pop("_id", None)
        return prompt

    @api_router.post("/prompts/{prompt_id}/rate")
    async def rate_prompt(prompt_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        rating = body.get("rating", 5)
        await db.prompt_library.update_one(
            {"prompt_id": prompt_id},
            {"$inc": {"use_count": 1}, "$set": {"avg_rating": rating}}
        )
        return {"rated": prompt_id}
