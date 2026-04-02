"""Pricing Engine — Credits-based billing, overage calculations, free tier management, usage tracking"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Credit costs per action
CREDIT_COSTS = {
    "ai_collaboration": 10,   # Per AI collaboration round
    "image_generation": 25,   # Per image generated
    "workflow_run": 15,       # Per workflow execution
    "file_upload": 2,         # Per KB file upload
    "export": 1,              # Per export action
}

# Plan credit allocations
PLAN_CREDITS = {
    "free": {"monthly_credits": 100, "overage_rate": 0, "overage_allowed": False},
    "starter": {"monthly_credits": 1000, "overage_rate": 0.02, "overage_allowed": True},
    "pro": {"monthly_credits": 5000, "overage_rate": 0.01, "overage_allowed": True},
    "team": {"monthly_credits": 5000, "overage_rate": 0.01, "overage_allowed": True},  # per seat
    "enterprise": {"monthly_credits": 50000, "overage_rate": 0.005, "overage_allowed": True},
}

PLAN_FEATURES = {
    "free": {"ai_messages": 50, "workspaces": 2, "ai_models": 3, "storage_gb": 0.5, "content_gen": 5, "research_sessions": 1, "integrations": 0, "workflow_runs": 5, "support": "community", "sso": False},
    "starter": {"ai_messages": 500, "workspaces": 5, "ai_models": 5, "storage_gb": 5, "content_gen": 50, "research_sessions": 10, "integrations": 2, "workflow_runs": 50, "support": "email", "sso": False},
    "pro": {"ai_messages": 5000, "workspaces": 20, "ai_models": 9, "storage_gb": 10, "content_gen": 500, "research_sessions": 50, "integrations": 6, "workflow_runs": 500, "support": "priority", "sso": False},
    "team": {"ai_messages": 5000, "workspaces": 50, "ai_models": 9, "storage_gb": 10, "content_gen": 500, "research_sessions": 50, "integrations": 6, "workflow_runs": 500, "support": "priority", "sso": True},
    "enterprise": {"ai_messages": -1, "workspaces": -1, "ai_models": 9, "storage_gb": 100, "content_gen": -1, "research_sessions": -1, "integrations": -1, "workflow_runs": -1, "support": "dedicated", "sso": True},
}

PLAN_PRICES = {"free": 0, "starter": 19, "pro": 49, "team": 29, "enterprise": 0}  # team is per seat

FREE_TIER_LIMITS = {
    "max_workspaces": 3,
    "max_channels_per_workspace": 5,
    "max_collaborations_per_day": 10,
    "max_image_generations_per_day": 3,
    "max_workflow_runs_per_day": 5,
    "max_kb_entries": 50,
}


def register_pricing_routes(api_router, db, get_current_user):

    # ============ Credits Dashboard ============

    @api_router.get("/billing/credits")
    async def get_credit_balance(request: Request):
        """Get current credit balance and usage breakdown"""
        user = await get_current_user(request)
        plan = user.get("plan", "free")
        plan_config = PLAN_CREDITS.get(plan, PLAN_CREDITS["free"])

        # Get or create credit record for current month
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        credit_record = await db.credit_balances.find_one(
            {"user_id": user["user_id"], "month": month_key}, {"_id": 0}
        )

        if not credit_record:
            credit_record = {
                "user_id": user["user_id"],
                "month": month_key,
                "plan": plan,
                "allocated": plan_config["monthly_credits"],
                "used": 0,
                "overage": 0,
                "overage_cost": 0.0,
                "breakdown": {},
                "created_at": now.isoformat(),
            }
            await db.credit_balances.insert_one(credit_record)
            credit_record.pop("_id", None)

        remaining = max(0, credit_record["allocated"] - credit_record["used"])
        usage_pct = round(credit_record["used"] / max(credit_record["allocated"], 1) * 100, 1)

        return {
            "plan": plan,
            "month": month_key,
            "allocated": credit_record["allocated"],
            "used": credit_record["used"],
            "remaining": remaining,
            "usage_percent": usage_pct,
            "overage": credit_record["overage"],
            "overage_cost": round(credit_record.get("overage_cost", 0), 2),
            "overage_allowed": plan_config["overage_allowed"],
            "overage_rate": plan_config["overage_rate"],
            "breakdown": credit_record.get("breakdown") or {},
        }

    @api_router.get("/billing/credits/history")
    async def get_credit_history(request: Request, months: int = 6):
        """Get credit usage history across months"""
        user = await get_current_user(request)
        records = await db.credit_balances.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("month", -1).limit(months).to_list(months)
        return {"history": records}

    @api_router.get("/billing/credit-costs")
    async def get_credit_costs(request: Request):
        """Get credit costs per action"""
        await get_current_user(request)
        return {"costs": CREDIT_COSTS, "plan_credits": PLAN_CREDITS}

    # ============ Credit Consumption (internal helper) ============

    async def consume_credits(user_id: str, action: str, amount: int = 0, metadata: dict = None):
        """Deduct credits for an action. Returns True if allowed, False if blocked."""
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "plan": 1})
        plan = user.get("plan", "free") if user else "free"
        plan_config = PLAN_CREDITS.get(plan, PLAN_CREDITS["free"])
        cost = amount or CREDIT_COSTS.get(action, 0)

        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")

        # Get or create balance
        balance = await db.credit_balances.find_one({"user_id": user_id, "month": month_key})
        if not balance:
            await db.credit_balances.insert_one({
                "user_id": user_id, "month": month_key, "plan": plan,
                "allocated": plan_config["monthly_credits"], "used": 0,
                "overage": 0, "overage_cost": 0.0, "breakdown": {},
                "created_at": now.isoformat(),
            })
            balance = await db.credit_balances.find_one({"user_id": user_id, "month": month_key})

        new_used = balance.get("used", 0) + cost
        allocated = balance.get("allocated", plan_config["monthly_credits"])

        # Check if over limit
        if new_used > allocated:
            if not plan_config["overage_allowed"]:
                # Free tier: block
                return False
            # Paid: allow with overage charge
            overage_credits = new_used - allocated
            overage_cost = overage_credits * plan_config["overage_rate"]
        else:
            overage_credits = 0
            overage_cost = 0

        # Update balance
        update = {
            "$inc": {"used": cost, "overage": max(0, overage_credits - balance.get("overage", 0))},
            "$set": {"overage_cost": round(balance.get("overage_cost", 0) + (overage_cost - balance.get("overage_cost", 0) if overage_credits > 0 else 0), 4)},
        }
        # Update breakdown
        breakdown_key = f"breakdown.{action}"
        update["$inc"][breakdown_key] = cost

        await db.credit_balances.update_one({"user_id": user_id, "month": month_key}, update)

        # Log transaction
        await db.credit_transactions.insert_one({
            "tx_id": f"ctx_{uuid.uuid4().hex[:8]}",
            "user_id": user_id, "action": action, "credits": cost,
            "metadata": metadata or {},
            "timestamp": now.isoformat(),
        })

        return True

    @api_router.get("/billing/credits/transactions")
    async def get_credit_transactions(request: Request, limit: int = 50):
        """Get recent credit transactions"""
        user = await get_current_user(request)
        txns = await db.credit_transactions.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"transactions": txns}

    # ============ Free Tier Manager ============

    @api_router.get("/billing/free-tier/status")
    async def get_free_tier_status(request: Request):
        """Get current free tier usage vs limits"""
        user = await get_current_user(request)
        if user.get("plan", "free") != "free":
            return {"on_free_tier": False, "limits": {}, "usage": {}}

        user_id = user["user_id"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Count today's usage
        daily_key = f"{user_id}:{today}"
        daily = await db.daily_usage.find_one({"key": daily_key}, {"_id": 0})
        if not daily:
            daily = {"collaborations": 0, "image_generations": 0, "workflow_runs": 0}

        # Count totals
        total_workspaces = await db.workspaces.count_documents({"owner_id": user_id, "disabled": {"$ne": True}})
        total_kb = await db.workspace_memory.count_documents({"created_by": user_id})

        usage = {
            "workspaces": total_workspaces,
            "collaborations_today": daily.get("collaborations", 0),
            "image_generations_today": daily.get("image_generations", 0),
            "workflow_runs_today": daily.get("workflow_runs", 0),
            "kb_entries": total_kb,
        }

        limits_status = {}
        for key, limit_val in FREE_TIER_LIMITS.items():
            usage_key = key.replace("max_", "").replace("_per_day", "_today")
            current = usage.get(usage_key, 0)
            limits_status[key] = {
                "limit": limit_val,
                "used": current,
                "remaining": max(0, limit_val - current),
                "at_limit": current >= limit_val,
            }

        return {"on_free_tier": True, "limits": limits_status, "usage": usage}

    async def check_free_tier_limit(user_id: str, action: str) -> bool:
        """Check if a free tier user can perform an action. Returns True if allowed."""
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "plan": 1})
        if user.get("plan", "free") != "free":
            return True  # Paid users aren't limited

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_key = f"{user_id}:{today}"
        daily = await db.daily_usage.find_one({"key": daily_key})

        limit_map = {
            "ai_collaboration": ("collaborations", FREE_TIER_LIMITS["max_collaborations_per_day"]),
            "image_generation": ("image_generations", FREE_TIER_LIMITS["max_image_generations_per_day"]),
            "workflow_run": ("workflow_runs", FREE_TIER_LIMITS["max_workflow_runs_per_day"]),
        }

        if action not in limit_map:
            return True

        field, limit = limit_map[action]
        current = daily.get(field, 0) if daily else 0

        if current >= limit:
            return False

        # Increment
        await db.daily_usage.update_one(
            {"key": daily_key},
            {"$inc": {field: 1}, "$setOnInsert": {"key": daily_key, "user_id": user_id, "date": today}},
            upsert=True
        )
        return True

    @api_router.post("/billing/check-limit")
    async def check_action_limit(request: Request):
        """Check if an action is allowed under current plan limits"""
        user = await get_current_user(request)
        body = await request.json()
        action = body.get("action", "")
        allowed = await check_free_tier_limit(user["user_id"], action)
        credit_ok = await consume_credits(user["user_id"], action) if allowed else False
        return {"allowed": allowed and credit_ok, "action": action}

    # ============ Overage Calculations ============

    @api_router.get("/billing/overage-estimate")
    async def get_overage_estimate(request: Request):
        """Estimate end-of-month overage based on current usage rate"""
        user = await get_current_user(request)
        plan = user.get("plan", "free")
        plan_config = PLAN_CREDITS.get(plan, PLAN_CREDITS["free"])

        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        balance = await db.credit_balances.find_one({"user_id": user["user_id"], "month": month_key}, {"_id": 0})

        if not balance:
            return {"estimated_overage": 0, "estimated_cost": 0, "days_remaining": 0}

        day_of_month = now.day
        days_in_month = 30
        days_remaining = max(0, days_in_month - day_of_month)
        daily_rate = balance.get("used", 0) / max(day_of_month, 1)
        projected_total = daily_rate * days_in_month
        projected_overage = max(0, projected_total - balance.get("allocated", 0))
        projected_cost = projected_overage * plan_config["overage_rate"]

        return {
            "current_used": balance.get("used", 0),
            "allocated": balance.get("allocated", 0),
            "daily_rate": round(daily_rate, 1),
            "projected_total": round(projected_total),
            "projected_overage": round(projected_overage),
            "projected_cost": round(projected_cost, 2),
            "days_remaining": days_remaining,
        }

    # Make helpers available for other modules
    api_router.consume_credits = consume_credits
    api_router.check_free_tier_limit = check_free_tier_limit


    # ============ Feature Gates & Plans ============

    @api_router.get("/billing/plans-v2")
    async def get_plans(request: Request):
        await get_current_user(request)
        plans = []
        for key in ["free", "starter", "pro", "team", "enterprise"]:
            plans.append({
                "plan": key,
                "price": PLAN_PRICES[key],
                "price_label": "Custom" if key == "enterprise" else (f"${PLAN_PRICES[key]}/user/mo" if key == "team" else f"${PLAN_PRICES[key]}/mo"),
                "credits": PLAN_CREDITS[key]["monthly_credits"],
                "features": PLAN_FEATURES[key],
            })
        return {"plans": plans}

    @api_router.post("/billing/check-feature")
    async def check_feature_gate(request: Request):
        """Check if a specific feature is available on the user's plan"""
        user = await get_current_user(request)
        body = await request.json()
        feature = body.get("feature", "")
        plan = user.get("plan", "free")
        features = PLAN_FEATURES.get(plan, PLAN_FEATURES["free"])
        limit = features.get(feature)
        if limit is None:
            return {"allowed": True, "feature": feature, "reason": "No limit defined"}
        if limit == -1:
            return {"allowed": True, "feature": feature, "reason": "Unlimited"}
        if isinstance(limit, bool):
            return {"allowed": limit, "feature": feature, "reason": "Plan feature" if limit else "Upgrade required"}
        # Check current usage
        return {"allowed": True, "feature": feature, "limit": limit, "plan": plan}
