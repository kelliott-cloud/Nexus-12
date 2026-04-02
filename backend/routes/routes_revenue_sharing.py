"""Agent Marketplace Revenue Sharing — Stripe-based payments for agent marketplace.

Enables agent creators to monetize their agents:
- Set prices on published agents
- Process purchases via Stripe Checkout
- Track revenue with platform commission
- View payout/earnings dashboard
"""
import os
import logging
import uuid
from datetime import datetime, timezone
from fastapi import Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

PLATFORM_FEE_PCT = 20  # 20% platform fee


class AgentPricingRequest(BaseModel):
    price_usd: float = Field(..., ge=0.0, le=10000.0)
    pricing_model: str = Field("one_time", pattern="^(one_time|monthly)$")


class PurchaseRequest(BaseModel):
    origin_url: str


def register_revenue_sharing_routes(api_router, db, get_current_user):

    async def _get_stripe_key():
        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "STRIPE_API_KEY")
        if not api_key:
            raise HTTPException(500, "Stripe not configured")
        return api_key

    # ---- Agent Pricing ----

    @api_router.put("/marketplace/agents/{agent_id}/pricing")
    async def set_agent_pricing(agent_id: str, data: AgentPricingRequest, request: Request):
        """Set or update pricing for a marketplace agent."""
        user = await get_current_user(request)
        agent = await db.marketplace_agents.find_one(
            {"agent_id": agent_id}, {"_id": 0, "publisher_id": 1}
        )
        if not agent:
            raise HTTPException(404, "Marketplace agent not found")
        if agent.get("publisher_id") != user["user_id"]:
            raise HTTPException(403, "Only the publisher can set pricing")

        await db.marketplace_agents.update_one(
            {"agent_id": agent_id},
            {"$set": {
                "pricing": {
                    "price_usd": data.price_usd,
                    "pricing_model": data.pricing_model,
                    "platform_fee_pct": PLATFORM_FEE_PCT,
                    "creator_share_pct": 100 - PLATFORM_FEE_PCT,
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        return {
            "agent_id": agent_id,
            "price_usd": data.price_usd,
            "pricing_model": data.pricing_model,
            "platform_fee_pct": PLATFORM_FEE_PCT,
            "creator_share_pct": 100 - PLATFORM_FEE_PCT,
        }

    @api_router.get("/marketplace/agents/{agent_id}/pricing")
    async def get_agent_pricing(agent_id: str, request: Request):
        """Get pricing for a marketplace agent."""
        await get_current_user(request)
        agent = await db.marketplace_agents.find_one(
            {"agent_id": agent_id}, {"_id": 0, "pricing": 1, "name": 1}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")
        pricing = agent.get("pricing", {"price_usd": 0, "pricing_model": "one_time"})
        return {"agent_id": agent_id, "name": agent.get("name", ""), **pricing}

    # ---- Purchase Flow ----

    @api_router.post("/marketplace/agents/{agent_id}/purchase")
    async def purchase_agent(agent_id: str, data: PurchaseRequest, request: Request):
        """Initiate purchase of a marketplace agent via Stripe Checkout."""
        user = await get_current_user(request)
        agent = await db.marketplace_agents.find_one(
            {"agent_id": agent_id}, {"_id": 0, "name": 1, "pricing": 1, "publisher_id": 1}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")

        pricing = agent.get("pricing") or {}
        price = pricing.get("price_usd", 0)
        if price <= 0:
            raise HTTPException(400, "This agent is free — no purchase needed")
        if agent.get("publisher_id") == user["user_id"]:
            raise HTTPException(400, "Cannot purchase your own agent")

        # Check if already purchased
        existing = await db.agent_purchases.find_one({
            "agent_id": agent_id, "buyer_id": user["user_id"], "status": "completed"
        })
        if existing:
            raise HTTPException(400, "You already own this agent")

        import stripe as stripe_sdk
        stripe_sdk.api_key = await _get_stripe_key()
        origin = data.origin_url.rstrip("/")
        success_url = f"{origin}/dashboard?marketplace_purchase=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin}/dashboard?marketplace_purchase=cancelled"

        session = stripe_sdk.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": agent.get("name", "AI Agent")},
                    "unit_amount": int(price * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "agent_purchase",
                "agent_id": agent_id,
                "buyer_id": user["user_id"],
                "publisher_id": agent.get("publisher_id", ""),
                "agent_name": agent.get("name", ""),
            }
        )

        # Record transaction
        txn = {
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "session_id": session.id,
            "agent_id": agent_id,
            "agent_name": agent.get("name", ""),
            "buyer_id": user["user_id"],
            "publisher_id": agent.get("publisher_id", ""),
            "amount_usd": price,
            "platform_fee_usd": round(price * PLATFORM_FEE_PCT / 100, 2),
            "creator_earnings_usd": round(price * (100 - PLATFORM_FEE_PCT) / 100, 2),
            "currency": "usd",
            "payment_status": "pending",
            "status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(txn)
        txn.pop("_id", None)

        return {"checkout_url": session.url, "session_id": session.id, "transaction": txn}

    @api_router.get("/marketplace/purchase/status/{session_id}")
    async def check_purchase_status(session_id: str, request: Request):
        """Check purchase payment status and finalize if paid."""
        user = await get_current_user(request)
        import stripe as stripe_sdk
        stripe_sdk.api_key = await _get_stripe_key()
        session = stripe_sdk.checkout.Session.retrieve(session_id)

        txn = await db.payment_transactions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not txn:
            raise HTTPException(404, "Transaction not found")

        payment_status = session.payment_status or "unpaid"
        if payment_status == "paid" and txn.get("status") != "completed":
            now = datetime.now(timezone.utc).isoformat()
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "paid", "status": "completed", "completed_at": now}}
            )
            # Record purchase
            await db.agent_purchases.update_one(
                {"agent_id": txn["agent_id"], "buyer_id": txn["buyer_id"]},
                {"$set": {
                    "agent_id": txn["agent_id"],
                    "buyer_id": txn["buyer_id"],
                    "publisher_id": txn["publisher_id"],
                    "purchased_at": now,
                    "amount_usd": txn["amount_usd"],
                    "status": "completed",
                    "session_id": session_id,
                }},
                upsert=True,
            )
            # Update creator earnings
            await db.creator_earnings.update_one(
                {"user_id": txn["publisher_id"]},
                {
                    "$inc": {
                        "total_earnings_usd": txn["creator_earnings_usd"],
                        "total_sales": 1,
                    },
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"user_id": txn["publisher_id"], "created_at": now},
                },
                upsert=True,
            )

        return {
            "session_id": session_id,
            "payment_status": payment_status,
            "status": "completed" if payment_status == "paid" else txn.get("status", "pending"),
            "amount_usd": txn.get("amount_usd", 0),
        }

    # ---- Webhook ----

    @api_router.post("/webhook/stripe-marketplace")
    async def stripe_marketplace_webhook(request: Request):
        """Handle Stripe webhook events for marketplace purchases."""
        try:
            import stripe as stripe_sdk
            stripe_sdk.api_key = await _get_stripe_key()
            body = await request.body()
            sig = request.headers.get("Stripe-Signature", "")
            webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
            if webhook_secret:
                event = stripe_sdk.Webhook.construct_event(body, sig, webhook_secret)
            else:
                import json as _json
                event = stripe_sdk.Event.construct_from(_json.loads(body), stripe_sdk.api_key)
            logger.info(f"Stripe marketplace webhook: {event.type}")

            if event.payment_status == "paid":
                txn = await db.payment_transactions.find_one(
                    {"session_id": event.session_id}, {"_id": 0}
                )
                if txn and txn.get("status") != "completed":
                    now = datetime.now(timezone.utc).isoformat()
                    await db.payment_transactions.update_one(
                        {"session_id": event.session_id},
                        {"$set": {"payment_status": "paid", "status": "completed", "completed_at": now}}
                    )
            return {"received": True}
        except Exception as e:
            logger.warning(f"Webhook processing error: {e}")
            return {"received": True, "error": str(e)}

    # ---- Revenue Dashboard ----

    @api_router.get("/marketplace/revenue/dashboard")
    async def revenue_dashboard(request: Request):
        """Get revenue dashboard data for the current user (as creator)."""
        user = await get_current_user(request)
        user_id = user["user_id"]

        # Earnings summary
        earnings = await db.creator_earnings.find_one(
            {"user_id": user_id}, {"_id": 0}
        )
        total_earnings = earnings.get("total_earnings_usd", 0) if earnings else 0
        total_sales = earnings.get("total_sales", 0) if earnings else 0

        # Recent transactions (as creator)
        transactions = await db.payment_transactions.find(
            {"publisher_id": user_id, "status": "completed"},
            {"_id": 0, "transaction_id": 1, "agent_name": 1, "amount_usd": 1,
             "platform_fee_usd": 1, "creator_earnings_usd": 1, "completed_at": 1, "buyer_id": 1}
        ).sort("completed_at", -1).limit(20).to_list(20)

        # Per-agent revenue breakdown
        agent_pipeline = [
            {"$match": {"publisher_id": user_id, "status": "completed"}},
            {"$group": {
                "_id": "$agent_id",
                "agent_name": {"$first": "$agent_name"},
                "total_revenue": {"$sum": "$amount_usd"},
                "creator_earnings": {"$sum": "$creator_earnings_usd"},
                "sales_count": {"$sum": 1},
            }},
            {"$sort": {"total_revenue": -1}},
        ]
        per_agent = []
        async for doc in db.payment_transactions.aggregate(agent_pipeline):
            per_agent.append({
                "agent_id": doc["_id"],
                "agent_name": doc["agent_name"],
                "total_revenue_usd": round(doc["total_revenue"], 2),
                "creator_earnings_usd": round(doc["creator_earnings"], 2),
                "sales_count": doc["sales_count"],
            })

        # Purchases (as buyer)
        purchases = await db.agent_purchases.find(
            {"buyer_id": user_id, "status": "completed"},
            {"_id": 0, "agent_id": 1, "amount_usd": 1, "purchased_at": 1}
        ).sort("purchased_at", -1).limit(20).to_list(20)

        return {
            "creator": {
                "total_earnings_usd": round(total_earnings, 2),
                "total_sales": total_sales,
                "platform_fee_pct": PLATFORM_FEE_PCT,
                "per_agent": per_agent,
                "recent_transactions": transactions,
            },
            "buyer": {
                "total_purchases": len(purchases),
                "purchases": purchases,
            },
        }

    @api_router.get("/marketplace/agents/{agent_id}/revenue")
    async def agent_revenue_detail(agent_id: str, request: Request):
        """Get detailed revenue for a specific agent (creator only)."""
        user = await get_current_user(request)
        agent = await db.marketplace_agents.find_one(
            {"agent_id": agent_id}, {"_id": 0, "publisher_id": 1, "name": 1, "pricing": 1}
        )
        if not agent:
            raise HTTPException(404, "Agent not found")
        if agent.get("publisher_id") != user["user_id"]:
            raise HTTPException(403, "Only the publisher can view revenue details")

        transactions = await db.payment_transactions.find(
            {"agent_id": agent_id, "status": "completed"},
            {"_id": 0, "transaction_id": 1, "amount_usd": 1, "creator_earnings_usd": 1,
             "platform_fee_usd": 1, "completed_at": 1}
        ).sort("completed_at", -1).limit(50).to_list(50)

        total_revenue = sum(t.get("amount_usd", 0) for t in transactions)
        total_earnings = sum(t.get("creator_earnings_usd", 0) for t in transactions)

        return {
            "agent_id": agent_id,
            "agent_name": agent.get("name", ""),
            "pricing": agent.get("pricing") or {},
            "total_revenue_usd": round(total_revenue, 2),
            "total_earnings_usd": round(total_earnings, 2),
            "total_sales": len(transactions),
            "transactions": transactions,
        }
