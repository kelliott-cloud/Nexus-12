"""Strategic Features v2 — Usage billing, scheduled jobs, audit export, tenant API,
agent learning dashboard, activity feed, white-label, agent marketplace."""
import uuid
import csv
import io
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



def register_strategic_features(api_router, db, get_current_user):

    # =============================================
    # 1. USAGE-BASED BILLING ENGINE
    # =============================================

    @api_router.get("/billing/usage/{workspace_id}")
    async def get_workspace_usage(workspace_id: str, request: Request, period: str = "30d"):
        user = await get_current_user(request)
        days = int(period.replace("d", "")) if period.endswith("d") else 30
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Aggregate AI usage from messages
        pipeline = [
            {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": since}, "cost_usd": {"$gt": 0}}},
            {"$group": {
                "_id": {"date": {"$substr": ["$created_at", 0, 10]}, "model": "$model_used"},
                "tokens": {"$sum": {"$add": [{"$ifNull": ["$tokens_used", 0]}, 0]}},
                "cost": {"$sum": "$cost_usd"}, "calls": {"$sum": 1},
            }},
            {"$sort": {"_id.date": 1}},
        ]
        daily = []
        by_model = {}
        async for doc in db.messages.aggregate(pipeline):
            date = doc["_id"]["date"]
            model = doc["_id"]["model"] or "unknown"
            daily.append({"date": date, "model": model, "tokens": doc["tokens"], "cost_usd": round(doc["cost"], 4), "calls": doc["calls"]})
            by_model.setdefault(model, {"tokens": 0, "cost_usd": 0, "calls": 0})
            by_model[model]["tokens"] += doc["tokens"]
            by_model[model]["cost_usd"] = round(by_model[model]["cost_usd"] + doc["cost"], 4)
            by_model[model]["calls"] += doc["calls"]

        total_cost = sum(m["cost_usd"] for m in by_model.values())
        total_tokens = sum(m["tokens"] for m in by_model.values())

        # Check budget limits
        budgets = await db.budget_limits.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(5)
        budget_status = []
        for b in budgets:
            pct = round(total_cost / max(b.get("limit_usd", 1), 0.01) * 100, 1) if b.get("period") == "monthly" else 0
            budget_status.append({"limit_usd": b.get("limit_usd"), "period": b.get("period"), "current_spend": total_cost, "pct_used": pct, "exceeded": total_cost > b.get("limit_usd", 999999)})

        return {
            "workspace_id": workspace_id, "period": period,
            "total_cost_usd": round(total_cost, 4), "total_tokens": total_tokens,
            "by_model": by_model, "daily": daily, "budget_status": budget_status,
        }

    @api_router.get("/billing/usage/invoice/{workspace_id}")
    async def generate_invoice(workspace_id: str, request: Request, month: str = ""):
        user = await get_current_user(request)
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        # Calculate proper month boundaries
        import calendar
        year, mon = int(month.split("-")[0]), int(month.split("-")[1])
        last_day = calendar.monthrange(year, mon)[1]
        start = f"{month}-01T00:00:00"
        end = f"{month}-{last_day}T23:59:59"

        pipeline = [
            {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": start, "$lte": end}, "cost_usd": {"$gt": 0}}},
            {"$group": {"_id": "$model_used", "tokens": {"$sum": {"$ifNull": ["$tokens_used", 0]}}, "cost": {"$sum": "$cost_usd"}, "calls": {"$sum": 1}}},
        ]
        lines = []
        async for doc in db.messages.aggregate(pipeline):
            lines.append({"model": doc["_id"] or "unknown", "calls": doc["calls"], "tokens": doc["tokens"], "cost_usd": round(doc["cost"], 4)})

        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "name": 1, "owner_id": 1})
        return {
            "invoice_id": f"inv_{uuid.uuid4().hex[:10]}", "workspace_id": workspace_id,
            "workspace_name": (ws or {}).get("name", ""), "month": month,
            "line_items": lines, "total_usd": round(sum(l["cost_usd"] for l in lines), 4),
            "generated_at": now_iso(),
        }

    # =============================================
    # 2. SCHEDULED AGENT JOBS
    # =============================================

    @api_router.post("/workspaces/{ws_id}/scheduled-jobs")
    async def create_scheduled_job(ws_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        job_id = f"sjob_{uuid.uuid4().hex[:10]}"
        job = {
            "job_id": job_id, "workspace_id": ws_id,
            "name": body.get("name", "Scheduled Job"),
            "type": body.get("type", "a2a_pipeline"),  # a2a_pipeline, operator, custom
            "target_id": body.get("target_id", ""),  # pipeline_id or template_id
            "payload": body.get("payload", ""),
            "schedule": body.get("schedule", "0 9 * * 1"),  # cron expression
            "schedule_human": body.get("schedule_human", "Every Monday 9 AM"),
            "timezone": body.get("timezone", "UTC"),
            "enabled": True, "last_run_at": None, "next_run_at": None,
            "run_count": 0, "last_status": None,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.scheduled_jobs.insert_one(job)
        job.pop("_id", None)
        return job

    @api_router.get("/workspaces/{ws_id}/scheduled-jobs")
    async def list_scheduled_jobs(ws_id: str, request: Request):
        await get_current_user(request)
        jobs = await db.scheduled_jobs.find({"workspace_id": ws_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"jobs": jobs}

    @api_router.put("/scheduled-jobs/{job_id}")
    async def update_scheduled_job(job_id: str, request: Request):
        user = await get_current_user(request)
        job = await db.scheduled_jobs.find_one({"job_id": job_id}, {"_id": 0, "workspace_id": 1, "created_by": 1})
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("created_by") != user["user_id"] and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Not authorized")
        body = await request.json()
        updates = {}
        for f in ["name", "schedule", "schedule_human", "payload", "enabled", "timezone"]:
            if f in body:
                updates[f] = body[f]
        if updates:
            await db.scheduled_jobs.update_one({"job_id": job_id}, {"$set": updates})
        return await db.scheduled_jobs.find_one({"job_id": job_id}, {"_id": 0}) or {}

    @api_router.delete("/scheduled-jobs/{job_id}")
    async def delete_scheduled_job(job_id: str, request: Request):
        user = await get_current_user(request)
        job = await db.scheduled_jobs.find_one({"job_id": job_id}, {"_id": 0, "created_by": 1})
        if job and job.get("created_by") != user["user_id"] and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Not authorized")
        await db.scheduled_jobs.delete_one({"job_id": job_id})
        return {"deleted": True}

    @api_router.post("/scheduled-jobs/{job_id}/run-now")
    async def run_job_now(job_id: str, request: Request):
        await get_current_user(request)
        job = await db.scheduled_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        # Trigger based on type
        if job["type"] == "a2a_pipeline" and job.get("target_id"):
            from a2a_engine import A2AEngine
            engine = A2AEngine(db)
            run_id = f"a2a_run_{uuid.uuid4().hex[:12]}"
            run = {"run_id": run_id, "pipeline_id": job["target_id"], "workspace_id": job["workspace_id"],
                   "status": "running", "trigger_type": "scheduled", "trigger_payload": job.get("payload", ""),
                   "current_step_id": None, "step_outputs": {}, "total_cost_usd": 0, "total_tokens_in": 0,
                   "total_tokens_out": 0, "total_duration_ms": 0, "started_at": now_iso(), "completed_at": None,
                   "error": None, "created_by": "scheduler", "created_at": now_iso()}
            await db.a2a_runs.insert_one(run)
            import asyncio
            asyncio.create_task(engine.execute_pipeline(run_id))
            await db.scheduled_jobs.update_one({"job_id": job_id}, {"$set": {"last_run_at": now_iso(), "last_status": "triggered"}, "$inc": {"run_count": 1}})
            return {"run_id": run_id, "status": "triggered"}
        return {"status": "unsupported_type"}

    # =============================================
    # 3. COMPLIANCE & AUDIT EXPORT
    # =============================================

    @api_router.get("/admin/audit-export")
    async def export_audit_log(request: Request, format: str = "csv", days: int = 30):
        user = await get_current_user(request)
        if user.get("platform_role") not in ("super_admin", "admin"):
            raise HTTPException(403, "Admin only")
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        logs = await db.audit_log.find({"timestamp": {"$gte": since}}, {"_id": 0}).sort("timestamp", -1).limit(500).to_list(500)
        if not logs:
            logs = await db.reporting_events.find({"created_at": {"$gte": since}}, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)

        if format == "csv":
            output = io.StringIO()
            if logs:
                writer = csv.DictWriter(output, fieldnames=list(logs[0].keys()))
                writer.writeheader()
                for log in logs:
                    writer.writerow({k: str(v)[:500] for k, v in log.items()})
            return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                     headers={"Content-Disposition": f"attachment; filename=nexus_audit_{days}d.csv"})
        else:
            return JSONResponse({"audit_logs": logs, "exported_at": now_iso(), "period_days": days, "count": len(logs)},
                                headers={"Content-Disposition": f"attachment; filename=nexus_audit_{days}d.json"})

    @api_router.get("/admin/compliance-report")
    async def compliance_report(request: Request):
        user = await get_current_user(request)
        if user.get("platform_role") not in ("super_admin", "admin"):
            raise HTTPException(403, "Admin only")
        total_users = await db.users.count_documents({})
        mfa_users = await db.users.count_documents({"mfa_enabled": True})
        total_sessions = await db.user_sessions.count_documents({})
        locked = await db.login_attempts.count_documents({"locked_until": {"$gte": now_iso()}})
        return {
            "report_type": "SOC2_Type2", "generated_at": now_iso(),
            "access_control": {"total_users": total_users, "mfa_enabled": mfa_users, "mfa_coverage": round(mfa_users / max(total_users, 1) * 100, 1),
                               "active_sessions": total_sessions, "locked_accounts": locked,
                               "password_policy": "8+ chars, mixed case, numbers, common password blocklist",
                               "session_expiry": "7 days", "tenant_isolation": "enforced"},
            "data_protection": {"encryption_at_rest": "MongoDB Atlas TDE", "encryption_in_transit": "TLS 1.3",
                                "pii_sanitization": "DataGuard active on all AI calls", "data_retention": "configurable per workspace"},
            "audit_logging": {"enabled": True, "retention_days": 90, "exportable": True, "formats": ["csv", "json"]},
            "ai_governance": {"model_routing": "transparent with logging", "cost_controls": "per-workspace budgets",
                              "content_filtering": "DataGuard PII sanitization", "rate_limiting": "600 req/min per user"},
        }

    # =============================================
    # 4. TENANT API ACCESS
    # =============================================

    @api_router.post("/developer/api-keys")
    async def create_api_key(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        import secrets, hashlib
        raw_key = f"nxapi_{secrets.token_urlsafe(48)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        doc = {
            "key_id": f"apk_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
            "key_hash": key_hash, "key_prefix": key_prefix,
            "label": body.get("label", "API Key"),
            "workspace_id": body.get("workspace_id", ""),
            "permissions": body.get("permissions", ["read", "write", "ai"]),
            "rate_limit": body.get("rate_limit", 60),
            "created_at": now_iso(), "last_used_at": None, "revoked": False,
        }
        await db.developer_api_keys.insert_one(doc)
        doc.pop("_id", None)
        doc["key"] = raw_key  # Only returned once at creation
        doc.pop("key_hash", None)
        return doc

    @api_router.get("/developer/api-keys")
    async def list_api_keys(request: Request):
        user = await get_current_user(request)
        keys = await db.developer_api_keys.find({"user_id": user["user_id"]}, {"_id": 0, "key_hash": 0}).sort("created_at", -1).to_list(20)
        return {"keys": keys}

    @api_router.delete("/developer/api-keys/{key_id}")
    async def revoke_api_key(key_id: str, request: Request):
        await get_current_user(request)
        await db.developer_api_keys.update_one({"key_id": key_id}, {"$set": {"revoked": True}})
        return {"revoked": True}

    @api_router.get("/developer/docs")
    async def api_docs(request: Request):
        return {
            "version": "1.0", "base_url": "/api",
            "authentication": "Bearer nxapi_YOUR_KEY in Authorization header",
            "endpoints": [
                {"method": "GET", "path": "/workspaces", "description": "List workspaces"},
                {"method": "GET", "path": "/workspaces/{id}/channels", "description": "List channels"},
                {"method": "POST", "path": "/channels/{id}/messages", "description": "Send a message"},
                {"method": "GET", "path": "/channels/{id}/messages", "description": "Get messages"},
                {"method": "GET", "path": "/workspaces/{id}/agents", "description": "List agents"},
                {"method": "POST", "path": "/a2a/pipelines/{id}/trigger", "description": "Trigger a pipeline"},
                {"method": "GET", "path": "/billing/usage/{ws_id}", "description": "Get usage data"},
            ],
            "rate_limits": {"free": "60 req/min", "pro": "300 req/min", "enterprise": "1000 req/min"},
        }

    # =============================================
    # 5. AGENT MEMORY & LEARNING DASHBOARD
    # =============================================

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/learning")
    async def agent_learning_dashboard(ws_id: str, agent_id: str, request: Request):
        await get_current_user(request)
        # Knowledge growth over time
        pipeline_growth = [
            {"$match": {"agent_id": agent_id}},
            {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
            {"$group": {"_id": "$date", "chunks_added": {"$sum": 1}, "avg_quality": {"$avg": {"$ifNull": ["$quality_score", 0.5]}}}},
            {"$sort": {"_id": 1}},
        ]
        growth = []
        async for doc in db.agent_knowledge.aggregate(pipeline_growth):
            growth.append({"date": doc["_id"], "chunks": doc["chunks_added"], "avg_quality": round(doc["avg_quality"], 2)})

        total_chunks = await db.agent_knowledge.count_documents({"agent_id": agent_id})
        high_quality = await db.agent_knowledge.count_documents({"agent_id": agent_id, "quality_score": {"$gte": 0.8}})

        # Topic distribution
        pipeline_topics = [
            {"$match": {"agent_id": agent_id}},
            {"$group": {"_id": "$topic", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 15},
        ]
        topics = []
        async for doc in db.agent_knowledge.aggregate(pipeline_topics):
            topics.append({"topic": doc["_id"] or "general", "count": doc["count"]})

        # Conversation learning
        conv_learned = await db.agent_knowledge.count_documents({"agent_id": agent_id, "source.type": "conversation"})

        # Training sessions
        sessions = await db.agent_training_sessions.count_documents({"agent_id": agent_id})

        return {
            "agent_id": agent_id,
            "knowledge": {"total_chunks": total_chunks, "high_quality": high_quality, "quality_rate": round(high_quality / max(total_chunks, 1) * 100, 1), "from_conversations": conv_learned},
            "growth": growth[-30:],
            "topics": topics,
            "training_sessions": sessions,
        }

    # =============================================
    # 6. TEAM ACTIVITY FEED
    # =============================================

    @api_router.get("/workspaces/{ws_id}/activity-feed")
    async def activity_feed(ws_id: str, request: Request, limit: int = 30, since: str = ""):
        await get_current_user(request)
        query = {"workspace_id": ws_id}
        if since:
            query["created_at"] = {"$gt": since}

        # Combine AI messages, orchestration runs, operator sessions
        activities = []

        # Recent AI messages
        msgs = await db.messages.find(
            {**query, "sender_type": "ai"},
            {"_id": 0, "message_id": 1, "agent": 1, "model_used": 1, "channel_id": 1, "content": 1, "created_at": 1, "cost_usd": 1}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        for m in msgs:
            activities.append({"type": "ai_message", "agent": m.get("agent", ""), "model": m.get("model_used", ""),
                               "preview": (m.get("content", ""))[:100], "channel_id": m.get("channel_id", ""),
                               "cost_usd": m.get("cost_usd", 0), "timestamp": m.get("created_at", "")})

        # A2A pipeline runs
        runs = await db.a2a_runs.find(
            {"workspace_id": ws_id}, {"_id": 0, "run_id": 1, "pipeline_id": 1, "status": 1, "started_at": 1, "total_cost_usd": 1}
        ).sort("started_at", -1).limit(10).to_list(10)
        for r in runs:
            activities.append({"type": "pipeline_run", "run_id": r.get("run_id", ""), "pipeline_id": r.get("pipeline_id", ""),
                               "status": r.get("status", ""), "cost_usd": r.get("total_cost_usd", 0), "timestamp": r.get("started_at", "")})

        # Operator sessions
        ops = await db.operator_sessions.find(
            {"workspace_id": ws_id}, {"_id": 0, "session_id": 1, "goal": 1, "status": 1, "created_at": 1, "metrics": 1}
        ).sort("created_at", -1).limit(10).to_list(10)
        for o in ops:
            activities.append({"type": "operator_session", "session_id": o.get("session_id", ""), "goal": (o.get("goal", ""))[:100],
                               "status": o.get("status", ""), "cost_usd": (o.get("metrics") or {}).get("total_cost_usd", 0), "timestamp": o.get("created_at", "")})

        # Sort all by timestamp
        activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"activities": activities[:limit]}

    # =============================================
    # 7. WHITE-LABEL / CUSTOM BRANDING
    # =============================================

    @api_router.get("/orgs/{org_id}/branding")
    async def get_org_branding(org_id: str, request: Request):
        await get_current_user(request)
        branding = await db.org_branding.find_one({"org_id": org_id}, {"_id": 0})
        return branding or {"org_id": org_id, "logo_url": "", "primary_color": "#06b6d4", "app_name": "Nexus Cloud",
                            "favicon_url": "", "custom_domain": "", "hide_powered_by": False, "custom_css": ""}

    @api_router.put("/orgs/{org_id}/branding")
    async def update_org_branding(org_id: str, request: Request):
        user = await get_current_user(request)
        # Check org ownership/admin
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "owner_id": 1})
        if org and org.get("owner_id") != user["user_id"] and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Only org owner or super admin can update branding")
        body = await request.json()
        updates = {}
        for f in ["logo_url", "primary_color", "secondary_color", "app_name", "favicon_url", "custom_domain", "hide_powered_by", "custom_css", "login_background_url", "email_footer"]:
            if f in body:
                val = body[f]
                # Sanitize custom_css — block dangerous patterns
                if f == "custom_css" and isinstance(val, str):
                    import re
                    dangerous = [r"javascript:", r"expression\s*\(", r"url\s*\(\s*['\"]?data:", r"@import", r"behavior\s*:", r"-moz-binding"]
                    for pattern in dangerous:
                        if re.search(pattern, val, re.IGNORECASE):
                            raise HTTPException(400, f"Custom CSS contains blocked pattern: {pattern}")
                    if len(val) > 10000:
                        raise HTTPException(400, "Custom CSS too long (max 10KB)")
                # Sanitize URLs
                if f in ("logo_url", "favicon_url", "login_background_url") and isinstance(val, str) and val:
                    if not val.startswith(("https://", "/", "data:image/")):
                        raise HTTPException(400, f"{f} must be HTTPS URL or relative path")
                updates[f] = val
        updates["org_id"] = org_id
        updates["updated_at"] = now_iso()
        await db.org_branding.update_one({"org_id": org_id}, {"$set": updates}, upsert=True)
        return await db.org_branding.find_one({"org_id": org_id}, {"_id": 0})

    # =============================================
    # 8. AGENT-TO-AGENT MARKETPLACE (ENHANCED)
    # =============================================

    @api_router.post("/marketplace/agents/{agent_id}/publish")
    async def publish_trained_agent(agent_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        agent = await db.nexus_agents.find_one({"agent_id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        # Verify ownership
        if agent.get("created_by") != user["user_id"] and user.get("platform_role") != "super_admin":
            ws = await db.workspaces.find_one({"workspace_id": agent.get("workspace_id")}, {"_id": 0, "owner_id": 1})
            if not ws or ws.get("owner_id") != user["user_id"]:
                raise HTTPException(403, "You don't have permission to publish this agent")

        # Count knowledge chunks
        knowledge_count = await db.agent_knowledge.count_documents({"agent_id": agent_id})
        listing_id = f"mpl_{uuid.uuid4().hex[:12]}"
        listing = {
            "listing_id": listing_id, "agent_id": agent_id,
            "publisher_id": user["user_id"], "publisher_name": user.get("name", ""),
            "name": body.get("name", agent.get("name", "")),
            "description": body.get("description", agent.get("description", "")),
            "category": body.get("category", "general"),
            "tags": body.get("tags", agent.get("skills") or []),
            "price_usd": body.get("price_usd", 0),
            "price_type": body.get("price_type", "one_time"),  # one_time, subscription, free
            "includes_knowledge": body.get("includes_knowledge", True),
            "knowledge_chunks": knowledge_count,
            "base_model": agent.get("base_model", ""),
            "skills": agent.get("skills") or [],
            "demo_available": body.get("demo_available", False),
            "avg_rating": 0, "rating_count": 0, "install_count": 0,
            "status": "active", "created_at": now_iso(),
        }
        await db.agent_marketplace.insert_one(listing)
        listing.pop("_id", None)
        return listing

    @api_router.get("/marketplace/strategic-agents")
    async def browse_marketplace_agents(request: Request, category: str = "", search: str = "", sort: str = "popular", limit: int = 20):
        await get_current_user(request)
        query = {"status": "active"}
        if category:
            query["category"] = category
        if search:
            from nexus_utils import now_iso, safe_regex
            query["$or"] = [{"name": {"$regex": safe_regex(search), "$options": "i"}}, {"description": {"$regex": safe_regex(search), "$options": "i"}}]

        sort_field = "install_count" if sort == "popular" else "avg_rating" if sort == "rating" else "created_at"
        agents = await db.agent_marketplace.find(query, {"_id": 0}).sort(sort_field, -1).limit(limit).to_list(limit)
        return {"agents": agents, "total": len(agents)}

    @api_router.post("/marketplace/agents/{listing_id}/install")
    async def install_marketplace_agent(listing_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        target_ws = body.get("workspace_id", "")
        if not target_ws:
            raise HTTPException(400, "workspace_id required")
        # Verify user has access to target workspace
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, target_ws)

        listing = await db.agent_marketplace.find_one({"listing_id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(404, "Listing not found")

        # Clone agent
        source_agent = await db.nexus_agents.find_one({"agent_id": listing["agent_id"]}, {"_id": 0})
        if not source_agent:
            raise HTTPException(404, "Source agent not found")

        new_agent_id = f"nxa_{uuid.uuid4().hex[:12]}"
        cloned = {**source_agent, "agent_id": new_agent_id, "workspace_id": target_ws,
                  "name": f"{source_agent.get('name', '')} (marketplace)", "installed_from": listing_id,
                  "created_at": now_iso(), "created_by": user["user_id"]}
        cloned.pop("_id", None)
        await db.nexus_agents.insert_one(cloned)

        # Clone knowledge if included
        if listing.get("includes_knowledge"):
            chunks = await db.agent_knowledge.find({"agent_id": listing["agent_id"]}, {"_id": 0}).limit(500).to_list(500)
            for chunk in chunks:
                chunk["chunk_id"] = f"kc_{uuid.uuid4().hex[:12]}"
                chunk["agent_id"] = new_agent_id
                chunk["workspace_id"] = target_ws
                chunk.pop("_id", None)
                await db.agent_knowledge.insert_one(chunk)

        await db.agent_marketplace.update_one({"listing_id": listing_id}, {"$inc": {"install_count": 1}})

        return {"agent_id": new_agent_id, "workspace_id": target_ws, "knowledge_copied": listing.get("includes_knowledge", False)}
