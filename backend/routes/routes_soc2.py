"""SOC 2 Compliance — Audit trail endpoints and documentation.

Provides formal audit logging for SOC 2 Type II requirements:
- Access logs (who accessed what, when)
- Change logs (who modified what)
- Authentication events
- Data export for auditors
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

# SOC 2 Trust Service Criteria mapping
SOC2_CATEGORIES = {
    "CC6.1": "Logical access security",
    "CC6.2": "Credentials and authentication",
    "CC6.3": "Access authorization",
    "CC7.1": "System monitoring",
    "CC7.2": "Anomaly detection",
    "CC8.1": "Change management",
}


async def log_audit_event(db, event_type, user_id, details, ip_address="", soc2_ref=""):
    """Log a SOC 2 compliant audit event."""
    event = {
        "audit_id": f"aud_{uuid.uuid4().hex[:16]}",
        "event_type": event_type,
        "user_id": user_id,
        "details": details,
        "ip_address": ip_address,
        "soc2_reference": soc2_ref,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.audit_trail.insert_one(event)
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


def register_soc2_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.get("/compliance/audit-trail")
    async def get_audit_trail(request: Request, days: int = 30, event_type: str = None,
                               user_id: str = None, limit: int = 200):
        """SOC 2 audit trail — super admin only."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        query = {"timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}}
        if event_type:
            query["event_type"] = event_type
        if user_id:
            query["user_id"] = user_id

        events = await db.audit_trail.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        total = await db.audit_trail.count_documents(query)
        return {"events": events, "total": total, "period_days": days}

    @api_router.get("/compliance/audit-trail/export")
    async def export_audit_trail(request: Request, days: int = 90, format: str = "csv"):
        """Export audit trail for SOC 2 auditors."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        query = {"timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}}
        events = await db.audit_trail.find(query, {"_id": 0}).sort("timestamp", 1).limit(500).to_list(500)

        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            fields = ["audit_id", "timestamp", "event_type", "user_id", "details", "ip_address", "soc2_reference"]
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for e in events:
                writer.writerow({k: str(e.get(k, ""))[:500] for k in fields})
            return Response(content=output.getvalue(), media_type="text/csv",
                          headers={"Content-Disposition": f"attachment; filename=nexus_audit_trail_{days}d.csv"})

        return {"events": events, "total": len(events)}

    @api_router.get("/compliance/soc2-summary")
    async def soc2_summary(request: Request):
        """SOC 2 compliance summary — coverage status."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        now = datetime.now(timezone.utc)
        month_ago = (now - timedelta(days=30)).isoformat()

        total_events = await db.audit_trail.count_documents({"timestamp": {"$gte": month_ago}})
        auth_events = await db.audit_trail.count_documents({"event_type": {"$regex": "auth"}, "timestamp": {"$gte": month_ago}})
        access_events = await db.audit_trail.count_documents({"event_type": {"$regex": "access"}, "timestamp": {"$gte": month_ago}})
        change_events = await db.audit_trail.count_documents({"event_type": {"$regex": "change|create|update|delete"}, "timestamp": {"$gte": month_ago}})

        controls = {
            "CC6.1": {"name": "Logical access security", "status": "implemented", "evidence": "Session-based auth with HTTPOnly cookies, CORS enforcement, rate limiting"},
            "CC6.2": {"name": "Credentials and authentication", "status": "implemented", "evidence": f"Password validation (8+ chars, blocklist), Google OAuth, session expiry. {auth_events} auth events logged."},
            "CC6.3": {"name": "Access authorization", "status": "implemented", "evidence": "RBAC (super_admin, admin, user), workspace-scoped data isolation, per-channel roles (TPM/QA/Security)"},
            "CC7.1": {"name": "System monitoring", "status": "implemented", "evidence": f"Reporting engine with {total_events} events. Health probes, error tracking, agent activity logging."},
            "CC7.2": {"name": "Anomaly detection", "status": "implemented", "evidence": "Provider error rate alerting (>5%), budget threshold alerts (90%+), rate limit monitoring"},
            "CC8.1": {"name": "Change management", "status": "implemented", "evidence": f"Code repo versioning, file lock system, dedup engine, recycle bin. {change_events} change events."},
        }

        return {
            "period": "Last 30 days",
            "total_audit_events": total_events,
            "controls": controls,
            "data_protection": {
                "encryption_at_rest": "MongoDB Atlas encryption",
                "encryption_in_transit": "TLS/HTTPS enforced",
                "pii_handling": "DataGuard sanitization layer",
                "data_retention": "Configurable TTL via background tasks",
            },
            "access_control": {
                "auth_methods": ["Email/Password", "Google OAuth"],
                "session_management": "HTTPOnly cookies, 7-day expiry, invalidation on password reset",
                "mfa_status": "Not yet implemented",
            },
        }

    @api_router.get("/compliance/data-map")
    async def data_map(request: Request):
        """Data inventory — what PII is stored and where."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")

        collections = {
            "users": {"pii_fields": ["email", "name", "picture"], "retention": "Account lifetime", "encryption": "Password bcrypt-hashed"},
            "messages": {"pii_fields": ["sender_name", "content"], "retention": "Workspace lifetime", "encryption": "At rest via MongoDB"},
            "payment_transactions": {"pii_fields": ["email", "user_id"], "retention": "7 years (financial)", "encryption": "Stripe handles card data"},
            "user_sessions": {"pii_fields": ["user_id", "session_token"], "retention": "7 days TTL", "encryption": "Token is opaque"},
            "reporting_events": {"pii_fields": ["user_id"], "retention": "90 days", "encryption": "At rest via MongoDB"},
            "audit_trail": {"pii_fields": ["user_id", "ip_address"], "retention": "1 year minimum", "encryption": "At rest via MongoDB"},
        }

        return {"collections": collections, "total_collections": len(collections)}
