"""Billing Routes — Direct Stripe SDK for checkout, status, and webhooks."""
import os
import uuid
import logging
import stripe
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

PLANS = {
    "free": {"name": "Free", "price": 0.0, "price_label": "$0/mo", "credits": 100, "collaborations": 5, "features": {"ai_messages": 50, "workspaces": 2, "ai_models": 3, "storage_gb": 0.5, "content_gen": 5, "research_sessions": 1, "integrations": "Upgrade to unlock", "workflow_runs": 5, "nexus_ai_credits": "BYOK only"}},
    "starter": {"name": "Starter", "price": 19.0, "price_label": "$19/mo", "credits": 1000, "collaborations": 50, "features": {"ai_messages": 500, "workspaces": 5, "ai_models": 5, "storage_gb": 5, "content_gen": 50, "research_sessions": 10, "integrations": 2, "workflow_runs": 50, "nexus_ai_credits": "1,000 credits/mo"}},
    "pro": {"name": "Pro", "price": 49.0, "price_label": "$49/mo (flat rate)", "credits": 5000, "collaborations": -1, "popular": True, "features": {"ai_messages": 5000, "workspaces": 20, "ai_models": 9, "storage_gb": 10, "content_gen": 500, "research_sessions": 50, "integrations": 6, "workflow_runs": 500, "nexus_ai_credits": "5,000 credits/mo"}},
    "team": {"name": "Team", "price": 29.0, "price_label": "$29/user/mo (per seat)", "credits": 5000, "collaborations": -1, "features": {"ai_messages": "5,000 per user", "workspaces": 50, "ai_models": 9, "storage_gb": 10, "content_gen": 500, "research_sessions": 50, "integrations": 6, "workflow_runs": 500, "sso": "Included", "rbac": "Included", "nexus_ai_credits": "5,000 credits/user/mo"}},
    "enterprise": {"name": "Enterprise", "price": 0.0, "price_label": "Custom", "credits": 50000, "collaborations": -1, "features": {"ai_messages": -1, "workspaces": -1, "ai_models": 9, "storage_gb": 100, "content_gen": -1, "research_sessions": -1, "integrations": -1, "workflow_runs": -1, "nexus_ai_credits": "50,000 credits/mo"}},
}


class CheckoutData(BaseModel):
    plan_id: str
    origin_url: str


def register_billing_routes(api_router, db, get_current_user):

    @api_router.get("/billing/plans")
    async def get_plans(request: Request):
        return {"plans": PLANS}

    @api_router.get("/billing/my-plan")
    async def get_my_plan(request: Request):
        user = await get_current_user(request)
        plan_id = user.get("plan", "free")
        # Check org plan inheritance
        membership = await db.org_memberships.find_one(
            {"user_id": user["user_id"]}, {"_id": 0, "org_id": 1})
        if membership:
            org = await db.organizations.find_one(
                {"org_id": membership["org_id"]}, {"_id": 0, "plan": 1})
            org_plan = (org.get("plan") or "free") if org else "free"
            plan_order = {"free": 0, "starter": 1, "pro": 2, "team": 3, "enterprise": 4}
            if plan_order.get(org_plan, 0) > plan_order.get(plan_id, 0):
                plan_id = org_plan
        plan = PLANS.get(plan_id, PLANS["free"])
        return {"plan_id": plan_id, **plan}

    @api_router.get("/billing/subscription")
    async def get_subscription(request: Request):
        """Get current user subscription info. Checks org plan as fallback."""
        user = await get_current_user(request)
        plan_id = user.get("plan", "free")
        
        # If user has an org, check if org plan is higher
        if plan_id == "free" or user.get("plan_source") != "org":
            # Check org membership for plan inheritance
            membership = await db.org_memberships.find_one(
                {"user_id": user["user_id"]}, {"_id": 0, "org_id": 1})
            if membership:
                org = await db.organizations.find_one(
                    {"org_id": membership["org_id"]}, {"_id": 0, "plan": 1})
                org_plan = (org.get("plan") or "free") if org else "free"
                plan_order = {"free": 0, "starter": 1, "pro": 2, "team": 3, "enterprise": 4}
                if plan_order.get(org_plan, 0) > plan_order.get(plan_id, 0):
                    plan_id = org_plan
                    # Sync the user's plan to match org
                    await db.users.update_one(
                        {"user_id": user["user_id"]},
                        {"$set": {"plan": org_plan, "plan_source": "org", "plan_org_id": membership["org_id"]}}
                    )
        
        plan = PLANS.get(plan_id, PLANS["free"])
        usage = user.get("usage") or {}
        return {
            "plan_id": plan_id, **plan,
            "usage": usage,
            "ai_collaboration_used": usage.get("ai_collaboration", 0),
            "ai_collaboration_limit": plan.get("collaborations", 5),
        }

    @api_router.post("/billing/checkout")
    async def create_checkout(data: CheckoutData, request: Request):
        user = await get_current_user(request)
        plan = PLANS.get(data.plan_id)
        if not plan or plan["price"] <= 0:
            raise HTTPException(400, f"Invalid plan: {data.plan_id}")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "STRIPE_API_KEY")
        if not api_key:
            raise HTTPException(503, "Stripe not configured")
        # Rate limit: max 5 checkouts per user per hour
        from datetime import timedelta
        recent = await db.payment_transactions.count_documents({
            "user_id": user["user_id"],
            "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
        })
        if recent >= 5:
            raise HTTPException(429, "Too many checkout attempts. Try again later.")
        stripe.api_key = api_key

        success_url = f"{data.origin_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{data.origin_url}/billing"

        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(plan["price"] * 100),
                    "product_data": {"name": f"Nexus {plan['name']} Plan"},
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user["user_id"], "plan_id": data.plan_id, "email": user.get("email", "")},
        )

        await db.payment_transactions.insert_one({
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "session_id": session.id,
            "user_id": user["user_id"],
            "email": user.get("email", ""),
            "plan_id": data.plan_id,
            "amount": plan["price"],
            "currency": "usd",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"url": session.url, "session_id": session.id}

    @api_router.get("/billing/checkout/status/{session_id}")
    async def checkout_status(session_id: str, request: Request):
        user = await get_current_user(request)
        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "STRIPE_API_KEY")
        if not api_key:
            raise HTTPException(503, "Stripe not configured")
        stripe.api_key = api_key

        session = stripe.checkout.Session.retrieve(session_id)
        payment_status = session.payment_status or "unpaid"

        txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if txn and txn.get("payment_status") != "paid" and payment_status == "paid":
            plan_id = txn.get("plan_id", "")
            if plan_id:
                await db.users.update_one(
                    {"user_id": txn["user_id"]},
                    {"$set": {"plan": plan_id, "plan_upgraded_at": datetime.now(timezone.utc).isoformat()}}
                )
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "paid", "status": "complete", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )

        return {
            "status": session.status,
            "payment_status": payment_status,
            "amount_total": session.amount_total,
            "currency": session.currency,
        }

    @api_router.post("/webhook/stripe")
    async def stripe_webhook(request: Request):
        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "STRIPE_API_KEY")
        webhook_secret = await get_integration_key(db, "STRIPE_WEBHOOK_SECRET")
        if not api_key:
            return {"status": "ignored"}
        stripe.api_key = api_key

        body = await request.body()
        signature = request.headers.get("Stripe-Signature", "")

        if not webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET not configured — rejecting webhook")
            raise HTTPException(503, "Webhook verification not configured")
        try:
            event = stripe.Webhook.construct_event(body, signature, webhook_secret)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid webhook signature")

        event_type = event.get("type", "") if isinstance(event, dict) else event.type
        if event_type == "checkout.session.completed":
            session_data = (event.get("data") or {}).get("object") or {} if isinstance(event, dict) else event.data.object
            sid = session_data.get("id", "") if isinstance(session_data, dict) else session_data.id
            payment = session_data.get("payment_status", "") if isinstance(session_data, dict) else session_data.payment_status

            if payment == "paid":
                txn = await db.payment_transactions.find_one({"session_id": sid}, {"_id": 0})
                if txn and txn.get("payment_status") != "paid":
                    plan_id = txn.get("plan_id", "")
                    if plan_id:
                        await db.users.update_one(
                            {"user_id": txn["user_id"]},
                            {"$set": {"plan": plan_id, "plan_upgraded_at": datetime.now(timezone.utc).isoformat()}}
                        )
                    await db.payment_transactions.update_one(
                        {"session_id": sid},
                        {"$set": {"payment_status": "paid", "webhook_processed": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
                    )
        return {"status": "processed"}

    @api_router.get("/billing/transactions")
    async def get_transactions(request: Request):
        user = await get_current_user(request)
        txns = await db.payment_transactions.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"transactions": txns}
