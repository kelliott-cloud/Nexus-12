"""Advanced Billing — Invoices, Statements, Account Management, Org Billing, Payment History"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)

CREDIT_COSTS = {
    "ai_collaboration": 10, "image_generation": 25, "workflow_run": 15,
    "video_generation": 50, "audio_generation": 5, "file_upload": 2, "export": 1,
}



class BillingAddressUpdate(BaseModel):
    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    tax_id: str = ""
    company_name: str = ""

class SpendingLimitUpdate(BaseModel):
    monthly_limit_usd: float = 0
    alert_threshold_pct: int = 80


def register_advanced_billing_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ======================================================
    # USER BILLING ACCOUNT
    # ======================================================

    @api_router.get("/billing/account")
    async def get_billing_account(request: Request):
        """Get user's complete billing account info"""
        user = await get_current_user(request)
        uid = user["user_id"]

        # Get or create billing account
        account = await db.billing_accounts.find_one({"user_id": uid}, {"_id": 0})
        if not account:
            account = {
                "user_id": uid, "account_type": "user",
                "plan": user.get("plan", "free"),
                "billing_address": {}, "tax_id": "", "company_name": "",
                "payment_methods": [], "default_payment_method": None,
                "auto_billing_enabled": True,
                "created_at": now_iso(),
            }
            await db.billing_accounts.insert_one(account)
            account.pop("_id", None)

        # Get current credit balance
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        credits = await db.credit_balances.find_one({"user_id": uid, "month": month_key}, {"_id": 0})

        return {
            "account": account,
            "credits": credits,
            "plan": user.get("plan", "free"),
        }

    @api_router.put("/billing/account/address")
    async def update_billing_address(data: BillingAddressUpdate, request: Request):
        user = await get_current_user(request)
        address = data.dict()
        await db.billing_accounts.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"billing_address": address, "tax_id": data.tax_id, "company_name": data.company_name}},
            upsert=True,
        )
        return {"message": "Address updated"}

    # ======================================================
    # INVOICES & STATEMENTS
    # ======================================================

    @api_router.get("/billing/invoices")
    async def list_invoices(request: Request, limit: int = 12):
        """List user's invoices"""
        user = await get_current_user(request)
        invoices = await db.invoices.find({"user_id": user["user_id"]}, {"_id": 0}).sort("period_end", -1).limit(limit).to_list(limit)
        return {"invoices": invoices}

    @api_router.post("/billing/invoices/generate")
    async def generate_invoice(request: Request):
        """Generate an invoice for the current or specified month"""
        user = await get_current_user(request)
        body = await request.json()
        month = body.get("month", datetime.now(timezone.utc).strftime("%Y-%m"))
        uid = user["user_id"]

        # Check if already generated
        existing = await db.invoices.find_one({"user_id": uid, "period": month})
        if existing:
            return await db.invoices.find_one({"user_id": uid, "period": month}, {"_id": 0})

        # Get credit usage for the month
        credits = await db.credit_balances.find_one({"user_id": uid, "month": month}, {"_id": 0})
        from nexus_utils import safe_regex
        transactions = await db.credit_transactions.find(
            {"user_id": uid, "timestamp": {"$regex": f"^{safe_regex(month)}"}}, {"_id": 0}
        ).to_list(500)

        # Build line items
        line_items = []
        action_totals = {}
        for tx in transactions:
            action = tx.get("action", "other")
            action_totals[action] = action_totals.get(action, 0) + tx.get("credits", 0)

        for action, total_credits in action_totals.items():
            cost_per = CREDIT_COSTS.get(action, 1)
            line_items.append({
                "description": action.replace("_", " ").title(),
                "quantity": total_credits // max(cost_per, 1),
                "unit_price_credits": cost_per,
                "total_credits": total_credits,
            })

        # Get plan info
        plan = user.get("plan", "free")
        from routes_pricing import PLAN_CREDITS
        plan_config = PLAN_CREDITS.get(plan, PLAN_CREDITS["free"])

        # Calculate amounts
        allocated = credits.get("allocated", plan_config["monthly_credits"]) if credits else plan_config["monthly_credits"]
        used = credits.get("used", 0) if credits else 0
        overage = max(0, used - allocated)
        overage_cost = overage * plan_config["overage_rate"]

        # Plan subscription cost
        from routes_billing import PLANS as BILLING_PLANS
        plan_price = BILLING_PLANS.get(plan, {}).get("price", 0)

        invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        invoice = {
            "invoice_id": invoice_id, "user_id": uid,
            "period": month, "period_start": f"{month}-01",
            "period_end": f"{month}-28",  # Simplified
            "status": "generated",  # generated, sent, paid, overdue
            "plan": plan, "plan_price": plan_price,
            "credits_allocated": allocated, "credits_used": used,
            "credits_overage": overage, "overage_cost": round(overage_cost, 2),
            "subtotal": round(plan_price + overage_cost, 2),
            "tax": 0, "total": round(plan_price + overage_cost, 2),
            "line_items": line_items,
            "billing_address": (await db.billing_accounts.find_one({"user_id": uid}, {"billing_address": 1, "_id": 0}) or {}).get("billing_address") or {},
            "generated_at": now, "due_date": f"{month}-28",
            "paid_at": None,
        }
        await db.invoices.insert_one(invoice)
        return {k: v for k, v in invoice.items() if k != "_id"}

    @api_router.get("/billing/invoices/{invoice_id}")
    async def get_invoice(invoice_id: str, request: Request):
        await get_current_user(request)
        inv = await db.invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        return inv

    @api_router.get("/billing/invoices/{invoice_id}/export")
    async def export_invoice(invoice_id: str, request: Request, format: str = "json"):
        """Export invoice as JSON or CSV"""
        await get_current_user(request)
        inv = await db.invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Invoice", inv["invoice_id"], "Period", inv["period"], "Total", f"${inv['total']}"])
            writer.writerow([])
            writer.writerow(["Description", "Quantity", "Credits per Unit", "Total Credits"])
            for item in inv.get("line_items") or []:
                writer.writerow([item["description"], item["quantity"], item["unit_price_credits"], item["total_credits"]])
            writer.writerow([])
            writer.writerow(["Plan", inv["plan"], "Price", f"${inv['plan_price']}"])
            writer.writerow(["Overage", f"{inv['credits_overage']} credits", "Cost", f"${inv['overage_cost']}"])
            writer.writerow(["Total", "", "", f"${inv['total']}"])
            return {"content": output.getvalue(), "format": "csv", "filename": f"invoice-{inv['period']}.csv"}
        return inv

    # ======================================================
    # PAYMENT HISTORY
    # ======================================================

    @api_router.get("/billing/payments")
    async def list_payments(request: Request, limit: int = 20):
        user = await get_current_user(request)
        payments = await db.payments.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        return {"payments": payments}

    @api_router.get("/billing/payments/{payment_id}/receipt")
    async def get_receipt(payment_id: str, request: Request):
        await get_current_user(request)
        payment = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
        if not payment:
            raise HTTPException(404, "Payment not found")
        return {"receipt": payment, "receipt_number": f"RCP-{payment_id.upper()[-8:]}"}

    # ======================================================
    # ORGANIZATION BILLING
    # ======================================================

    @api_router.get("/orgs/{org_id}/billing/account")
    async def get_org_billing(org_id: str, request: Request):
        """Get org billing account"""
        await get_current_user(request)
        account = await db.org_billing.find_one({"org_id": org_id}, {"_id": 0})
        if not account:
            account = {
                "org_id": org_id, "plan": "free",
                "billing_address": {}, "tax_id": "", "company_name": "",
                "billing_contacts": [], "payment_methods": [],
                "spending_limit_usd": 0, "alert_threshold_pct": 80,
                "auto_billing_enabled": True,
                "created_at": now_iso(),
            }
            await db.org_billing.insert_one(account)
            account.pop("_id", None)
        return account

    @api_router.put("/orgs/{org_id}/billing/address")
    async def update_org_billing_address(org_id: str, data: BillingAddressUpdate, request: Request):
        await get_current_user(request)
        await db.org_billing.update_one(
            {"org_id": org_id},
            {"$set": {"billing_address": data.dict(), "tax_id": data.tax_id, "company_name": data.company_name}},
            upsert=True,
        )
        return {"message": "Address updated"}

    @api_router.put("/orgs/{org_id}/billing/spending-limit")
    async def set_org_spending_limit(org_id: str, data: SpendingLimitUpdate, request: Request):
        await get_current_user(request)
        await db.org_billing.update_one(
            {"org_id": org_id},
            {"$set": {"spending_limit_usd": data.monthly_limit_usd, "alert_threshold_pct": data.alert_threshold_pct}},
            upsert=True,
        )
        return {"message": "Spending limit updated"}

    @api_router.post("/orgs/{org_id}/billing/contacts")
    async def add_billing_contact(org_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        contact = {"email": body.get("email", ""), "name": body.get("name", ""), "role": body.get("role", "billing"), "added_at": now_iso()}
        await db.org_billing.update_one({"org_id": org_id}, {"$push": {"billing_contacts": contact}}, upsert=True)
        return {"message": "Contact added"}

    @api_router.get("/orgs/{org_id}/billing/cost-allocation")
    async def get_cost_allocation(org_id: str, request: Request):
        """Cost breakdown by workspace"""
        await get_current_user(request)
        ws_list = await db.workspaces.find({"org_id": org_id}, {"_id": 0, "workspace_id": 1, "name": 1}).to_list(50)
        allocations = []
        for ws in ws_list:
            # Count actions per workspace
            pipeline = [
                {"$match": {"workspace_id": ws["workspace_id"]}},
                {"$group": {"_id": "$agent", "count": {"$sum": 1}}}
            ]
            ai_calls = 0
            async for doc in db.analytics.aggregate(pipeline):
                ai_calls += doc["count"]
            # Estimate cost
            estimated_credits = ai_calls * CREDIT_COSTS.get("ai_collaboration", 10)
            allocations.append({
                "workspace_id": ws["workspace_id"], "workspace_name": ws["name"],
                "ai_calls": ai_calls, "estimated_credits": estimated_credits,
            })
        allocations.sort(key=lambda x: x["estimated_credits"], reverse=True)
        return {"allocations": allocations, "total_credits": sum(a["estimated_credits"] for a in allocations)}

    @api_router.get("/orgs/{org_id}/billing/invoices")
    async def list_org_invoices(org_id: str, request: Request):
        await get_current_user(request)
        invoices = await db.invoices.find({"org_id": org_id}, {"_id": 0}).sort("period_end", -1).to_list(12)
        return {"invoices": invoices}

    # ======================================================
    # SUBSCRIPTION MANAGEMENT
    # ======================================================

    @api_router.get("/billing/plan-history")
    async def get_plan_history(request: Request):
        user = await get_current_user(request)
        history = await db.plan_changes.find({"user_id": user["user_id"]}, {"_id": 0}).sort("changed_at", -1).to_list(20)
        return {"history": history}

    @api_router.post("/billing/change-plan")
    async def change_plan(request: Request):
        """Request plan change (upgrade/downgrade)"""
        user = await get_current_user(request)
        body = await request.json()
        new_plan = body.get("plan", "")
        if new_plan not in ("free", "pro", "enterprise"):
            raise HTTPException(400, "Invalid plan")
        old_plan = user.get("plan", "free")
        if old_plan == new_plan:
            raise HTTPException(400, "Already on this plan")

        now = now_iso()
        change_id = f"pc_{uuid.uuid4().hex[:12]}"
        await db.plan_changes.insert_one({
            "change_id": change_id, "user_id": user["user_id"],
            "old_plan": old_plan, "new_plan": new_plan,
            "change_type": "upgrade" if (["free", "pro", "enterprise"].index(new_plan) > ["free", "pro", "enterprise"].index(old_plan)) else "downgrade",
            "status": "pending",  # pending, active, cancelled
            "effective_date": now[:10],
            "changed_at": now,
        })

        # Update user plan
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"plan": new_plan}})

        return {"change_id": change_id, "old_plan": old_plan, "new_plan": new_plan, "status": "active"}

    # ======================================================
    # BILLING NOTIFICATIONS
    # ======================================================

    @api_router.get("/billing/notifications")
    async def get_billing_notifications(request: Request):
        user = await get_current_user(request)
        uid = user["user_id"]
        notifications = []

        # Check credit usage
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        credits = await db.credit_balances.find_one({"user_id": uid, "month": month}, {"_id": 0})
        if credits:
            usage_pct = credits.get("used", 0) / max(credits.get("allocated", 1), 1) * 100
            if usage_pct >= 90:
                notifications.append({"type": "warning", "title": "Credit limit approaching", "message": f"You've used {usage_pct:.0f}% of your monthly credits.", "action": "upgrade"})
            if credits.get("overage", 0) > 0:
                notifications.append({"type": "alert", "title": "Overage charges", "message": f"You have ${credits.get('overage_cost', 0):.2f} in overage charges this month.", "action": "view_invoice"})

        # Check for unpaid invoices
        unpaid = await db.invoices.count_documents({"user_id": uid, "status": {"$in": ["generated", "sent"]}, "total": {"$gt": 0}})
        if unpaid > 0:
            notifications.append({"type": "info", "title": "Unpaid invoices", "message": f"You have {unpaid} unpaid invoice(s).", "action": "view_invoices"})

        return {"notifications": notifications}

    # ======================================================
    # USAGE SUMMARY (for billing context)
    # ======================================================

    @api_router.get("/billing/usage-summary")
    async def get_usage_summary(request: Request, months: int = 3):
        """Usage summary for billing context"""
        user = await get_current_user(request)
        uid = user["user_id"]
        summaries = []

        for i in range(months):
            d = datetime.now(timezone.utc) - timedelta(days=30 * i)
            month = d.strftime("%Y-%m")
            credits = await db.credit_balances.find_one({"user_id": uid, "month": month}, {"_id": 0})
            if credits:
                summaries.append({
                    "month": month, "allocated": credits.get("allocated", 0),
                    "used": credits.get("used", 0), "overage": credits.get("overage", 0),
                    "overage_cost": credits.get("overage_cost", 0),
                    "breakdown": credits.get("breakdown") or {},
                })
            else:
                summaries.append({"month": month, "allocated": 0, "used": 0, "overage": 0, "overage_cost": 0, "breakdown": {}})

        return {"summaries": summaries}
