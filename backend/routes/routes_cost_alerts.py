from nexus_utils import now_iso
"""Cost Alerts — Notify workspace admins when spending exceeds thresholds.

Runs as part of the cost batch job cycle.
Stores alerts in workspace_cost_alerts collection.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("cost_alerts")



async def check_cost_alerts(db):
    """Check all workspaces for budget threshold breaches and generate alerts."""
    try:
        async for budget in db.workspace_budgets.find({}, {"_id": 0}):
            ws_id = budget.get("workspace_id")
            cap = budget.get("monthly_cap_usd", 0)
            if not ws_id or cap <= 0:
                continue

            # Get current spend from cost_snapshots
            total_doc = await db.cost_snapshots.find_one(
                {"workspace_id": ws_id, "period": "monthly_total"},
                {"_id": 0, "total_actual_cost_usd": 1}
            )
            current_spend = total_doc.get("total_actual_cost_usd", 0) if total_doc else 0
            pct = round((current_spend / cap) * 100, 1) if cap > 0 else 0

            alert_thresholds = budget.get("alert_thresholds", [50, 80, 90, 100])
            for threshold in alert_thresholds:
                if pct >= threshold:
                    # Check if we already sent this alert level this month
                    month = datetime.now(timezone.utc).strftime("%Y-%m")
                    existing = await db.workspace_cost_alerts.find_one({
                        "workspace_id": ws_id, "month": month, "threshold": threshold
                    })
                    if not existing:
                        alert = {
                            "workspace_id": ws_id,
                            "month": month,
                            "threshold": threshold,
                            "pct_used": pct,
                            "current_spend": round(current_spend, 2),
                            "budget_cap": cap,
                            "severity": "critical" if threshold >= 100 else "warning" if threshold >= 80 else "info",
                            "message": f"AI spending has reached {pct}% of your ${cap} monthly budget (${round(current_spend, 2)} spent).",
                            "acknowledged": False,
                            "created_at": now_iso(),
                        }
                        await db.workspace_cost_alerts.insert_one(alert)
                        alert.pop("_id", None)
                        logger.info(f"Cost alert: ws={ws_id} threshold={threshold}% spend=${current_spend:.2f}/{cap}")

                        # Emit webhook notification
                        try:
                            from routes_webhooks import emit_webhook_event
                            await emit_webhook_event(db, ws_id, "cost.alert.triggered", {
                                "threshold": threshold,
                                "pct_used": pct,
                                "current_spend": round(current_spend, 2),
                                "budget_cap": cap,
                                "severity": alert["severity"],
                                "message": alert["message"],
                            })
                        except Exception as e:
                            logger.warning(f"Non-critical error at line 70: {e}")

    except Exception as e:
        logger.error(f"Cost alert check failed: {e}")


def register_cost_alert_routes(api_router, db, get_current_user):
    from fastapi import Request

    @api_router.get("/workspaces/{ws_id}/cost-alerts")
    async def get_cost_alerts(ws_id: str, request: Request):
        """Get cost alerts for this workspace."""
        user = await get_current_user(request)
        alerts = await db.workspace_cost_alerts.find(
            {"workspace_id": ws_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"alerts": alerts}

    @api_router.put("/workspaces/{ws_id}/cost-alerts/acknowledge")
    async def acknowledge_alerts(ws_id: str, request: Request):
        """Acknowledge all unread cost alerts."""
        user = await get_current_user(request)
        result = await db.workspace_cost_alerts.update_many(
            {"workspace_id": ws_id, "acknowledged": False},
            {"$set": {"acknowledged": True, "acknowledged_at": now_iso(), "acknowledged_by": user["user_id"]}}
        )
        return {"acknowledged": result.modified_count}

    @api_router.put("/workspaces/{ws_id}/budget/thresholds")
    async def update_alert_thresholds(ws_id: str, request: Request):
        """Update budget alert thresholds."""
        user = await get_current_user(request)
        body = await request.json()
        thresholds = body.get("thresholds", [50, 80, 90, 100])
        await db.workspace_budgets.update_one(
            {"workspace_id": ws_id},
            {"$set": {"alert_thresholds": thresholds}},
            upsert=True
        )
        return {"thresholds": thresholds}
