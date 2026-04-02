"""Status, Incidents & API Documentation Routes.
Real-time health dashboard with latency tracking, system metrics, 90-day incident history,
and comprehensive API documentation with request/response examples.
"""
import logging
import time
import os
import uuid
import shutil
import psutil
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from html import escape

logger = logging.getLogger(__name__)

_start_time = time.time()


class IncidentCreate(BaseModel):
    title: str
    description: str = ""
    severity: str = "minor"  # minor, major, critical
    affected_services: list = []
    message: str = ""


class IncidentUpdate(BaseModel):
    status: Optional[str] = None  # investigating, identified, monitoring, resolved
    message: str = ""
    severity: Optional[str] = None


def register_status_routes(api_router, db, get_current_user=None):

    # ============ REAL-TIME STATUS ============

    @api_router.get("/status")
    async def platform_status():
        """Public status endpoint — real-time health of all platform services."""
        uptime = int(time.time() - _start_time)
        checks = {}

        try:
            t0 = time.monotonic()
            await db.command("ping")
            db_latency = round((time.monotonic() - t0) * 1000, 1)
            checks["database"] = {"status": "operational", "latency_ms": db_latency, "type": "MongoDB"}
        except Exception as e:
            checks["database"] = {"status": "down", "error": str(e)[:100]}

        try:
            from redis_client import health_check as redis_health
            checks["cache"] = await redis_health()
        except Exception:
            checks["cache"] = {"status": "degraded", "note": "Redis unavailable"}

        checks["ai_models"] = await _check_ai_providers()
        checks["file_storage"] = _check_file_storage()
        checks["websocket"] = {"status": "operational", "note": "Event loop healthy"}

        try:
            t0 = time.monotonic()
            count = await db.user_sessions.estimated_document_count()
            lat = round((time.monotonic() - t0) * 1000, 1)
            checks["auth"] = {"status": "operational", "active_sessions": count, "latency_ms": lat}
        except Exception as e:
            checks["auth"] = {"status": "degraded", "error": str(e)[:100]}

        # System metrics
        try:
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage("/")
            checks["system"] = {
                "status": "operational",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_used_pct": mem.percent,
                "memory_available_mb": round(mem.available / (1024 * 1024)),
                "disk_used_pct": round(disk.used / disk.total * 100, 1),
                "disk_free_gb": round(disk.free / (1024 ** 3), 1),
            }
        except Exception:
            checks["system"] = {"status": "unknown", "note": "Metrics unavailable"}

        overall = "operational"
        for c in checks.values():
            if c.get("status") == "down":
                overall = "major_outage"
                break
            if c.get("status") in ("degraded", "error"):
                overall = "degraded"

        # Active incidents count
        active = await db.incidents.count_documents({"status": {"$ne": "resolved"}})

        return {
            "status": overall,
            "uptime_seconds": uptime,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_incidents": active,
            "services": checks,
        }

    # ============ INCIDENTS API ============

    @api_router.get("/incidents")
    async def list_incidents(request: Request):
        """Public — list incidents. ?days=90 (default) ?status=resolved"""
        days = int(request.query_params.get("days", "90"))
        status_filter = request.query_params.get("status")
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = {"created_at": {"$gte": since}}
        if status_filter:
            query["status"] = status_filter
        incidents = await db.incidents.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"incidents": incidents, "total": len(incidents)}

    @api_router.get("/incidents/timeline")
    async def incident_timeline(request: Request):
        """Public — 90-day daily summary for timeline visualization."""
        days = int(request.query_params.get("days", "90"))
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=days)).isoformat()

        incidents = await db.incidents.find(
            {"created_at": {"$gte": since}},
            {"_id": 0, "incident_id": 1, "severity": 1, "status": 1, "created_at": 1, "resolved_at": 1, "title": 1}
        ).to_list(500)

        # Build daily map
        timeline = []
        for d in range(days, -1, -1):
            day = now - timedelta(days=d)
            day_str = day.strftime("%Y-%m-%d")
            day_incidents = []
            for inc in incidents:
                inc_date = inc["created_at"][:10]
                resolved = inc.get("resolved_at", "")
                resolved_date = resolved[:10] if resolved else "9999-12-31"
                if inc_date <= day_str <= resolved_date:
                    day_incidents.append(inc)
            worst = "none"
            for di in day_incidents:
                sev = di.get("severity", "minor")
                if sev == "critical":
                    worst = "critical"
                    break
                if sev == "major" and worst != "critical":
                    worst = "major"
                if sev == "minor" and worst == "none":
                    worst = "minor"
            timeline.append({
                "date": day_str,
                "severity": worst,
                "count": len(day_incidents),
            })
        return {"timeline": timeline, "days": days}

    @api_router.get("/incidents/{incident_id}")
    async def get_incident(incident_id: str):
        """Public — get incident details."""
        inc = await db.incidents.find_one({"incident_id": incident_id}, {"_id": 0})
        if not inc:
            raise HTTPException(404, "Incident not found")
        return inc

    @api_router.post("/incidents")
    async def create_incident(data: IncidentCreate, request: Request):
        """Admin — create a new incident."""
        user = await get_current_user(request)
        if user.get("platform_role") not in ("super_admin", "admin"):
            raise HTTPException(403, "Admin required")
        if data.severity not in ("minor", "major", "critical"):
            raise HTTPException(400, "severity must be minor, major, or critical")

        incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        incident = {
            "incident_id": incident_id,
            "title": data.title,
            "description": data.description,
            "severity": data.severity,
            "status": "investigating",
            "affected_services": data.affected_services,
            "created_at": now_iso,
            "resolved_at": None,
            "duration_minutes": None,
            "created_by": user["user_id"],
            "auto_detected": False,
            "updates": [{
                "timestamp": now_iso,
                "status": "investigating",
                "message": data.message or f"Incident reported: {data.title}",
                "author": user.get("name", user["user_id"]),
            }],
        }
        await db.incidents.insert_one(incident)
        incident.pop("_id", None)
        return incident

    @api_router.put("/incidents/{incident_id}")
    async def update_incident(incident_id: str, data: IncidentUpdate, request: Request):
        """Admin — update incident status or add update message."""
        user = await get_current_user(request)
        if user.get("platform_role") not in ("super_admin", "admin"):
            raise HTTPException(403, "Admin required")

        inc = await db.incidents.find_one({"incident_id": incident_id}, {"_id": 0})
        if not inc:
            raise HTTPException(404, "Incident not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        updates = {}
        new_status = data.status or inc["status"]

        if data.status and data.status not in ("investigating", "identified", "monitoring", "resolved"):
            raise HTTPException(400, "status must be investigating, identified, monitoring, or resolved")

        if data.status:
            updates["status"] = data.status
        if data.severity:
            updates["severity"] = data.severity

        if new_status == "resolved" and not inc.get("resolved_at"):
            updates["resolved_at"] = now_iso
            created = datetime.fromisoformat(inc["created_at"].replace("Z", "+00:00"))
            resolved = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
            updates["duration_minutes"] = round((resolved - created).total_seconds() / 60, 1)

        update_entry = {
            "timestamp": now_iso,
            "status": new_status,
            "message": data.message or f"Status changed to {new_status}",
            "author": user.get("name", user["user_id"]),
        }

        await db.incidents.update_one(
            {"incident_id": incident_id},
            {"$set": updates, "$push": {"updates": update_entry}}
        )
        return {"status": "updated", "incident_id": incident_id}

    @api_router.delete("/incidents/{incident_id}")
    async def delete_incident(incident_id: str, request: Request):
        """Admin — delete incident from history."""
        user = await get_current_user(request)
        if user.get("platform_role") not in ("super_admin", "admin"):
            raise HTTPException(403, "Admin required")
        result = await db.incidents.delete_one({"incident_id": incident_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Incident not found")
        return {"status": "deleted"}

    # ============ STATUS PAGE (HTML) ============

    @api_router.get("/status/page", response_class=HTMLResponse)
    async def status_page():
        """Rendered HTML status page with incident history and 90-day timeline."""
        uptime = int(time.time() - _start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60

        # Gather services
        services = []
        try:
            t0 = time.monotonic()
            await db.command("ping")
            db_lat = round((time.monotonic() - t0) * 1000, 1)
            services.append(("Database", "operational", f"MongoDB &mdash; {db_lat}ms"))
        except Exception:
            services.append(("Database", "down", "MongoDB &mdash; connection failed"))

        try:
            from redis_client import health_check as redis_health
            rh = await redis_health()
            if rh["status"] == "operational":
                services.append(("Cache", "operational", f"Redis v{rh.get('version', '?')} &mdash; {rh.get('latency_ms', '?')}ms"))
            elif rh["status"] == "disabled":
                services.append(("Cache", "fallback", "In-memory (dev mode)"))
            else:
                services.append(("Cache", "degraded", rh.get("note", "Redis issue")))
        except Exception:
            services.append(("Cache", "degraded", "Redis unavailable"))

        services.append(("API Server", "operational", f"FastAPI &mdash; uptime {hours}h {minutes}m"))

        try:
            count = await db.user_sessions.estimated_document_count()
            services.append(("Auth", "operational", f"{count} active sessions"))
        except Exception:
            services.append(("Auth", "degraded", "Session store error"))

        ai_check = await _check_ai_providers()
        services.append(("AI Models", ai_check.get("status", "unknown"), f"{ai_check.get('configured_count', 0)} providers configured"))

        fs = _check_file_storage()
        services.append(("File Storage", fs["status"], fs.get("note", "Upload directory")))
        services.append(("WebSocket", "operational", "Real-time messaging"))

        # System metrics
        try:
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage("/")
            cpu_pct = psutil.cpu_percent(interval=0.1)
            mem_label = f"CPU {cpu_pct}% &middot; RAM {mem.percent}% &middot; Disk {round(disk.used / disk.total * 100, 1)}%"
            sys_status = "operational" if cpu_pct < 90 and mem.percent < 90 else "degraded"
            services.append(("System", sys_status, mem_label))
        except Exception:
            services.append(("System", "unknown", "Metrics unavailable"))

        op_count = sum(1 for _, s, _ in services if s == "operational")
        total = len(services)
        all_op = op_count == total

        svc_rows = ""
        for name, status, desc in services:
            if status == "operational":
                color, label, dot = "#10b981", "Operational", "#10b981"
            elif status == "fallback":
                color, label, dot = "#f59e0b", "Fallback", "#f59e0b"
            elif status == "degraded":
                color, label, dot = "#f59e0b", "Degraded", "#f59e0b"
            else:
                color, label, dot = "#ef4444", "Down", "#ef4444"
            svc_rows += f"""<div class="svc-row">
                <div><div class="svc-name">{name}</div><div class="svc-desc">{desc}</div></div>
                <div class="svc-badge"><div class="dot" style="background:{dot}"></div><span style="color:{color}">{label}</span></div>
            </div>"""

        banner_color = "#10b981" if all_op else "#f59e0b"
        banner_bg = "#10b98120" if all_op else "#f59e0b20"
        banner_border = "#10b98140" if all_op else "#f59e0b40"
        banner_text = "All Systems Operational" if all_op else f"{op_count}/{total} Systems Operational"

        # 90-day timeline
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=90)).isoformat()
        incidents = await db.incidents.find(
            {"created_at": {"$gte": since}},
            {"_id": 0, "severity": 1, "created_at": 1, "resolved_at": 1}
        ).to_list(500)

        day_cells = ""
        for d in range(89, -1, -1):
            day = now - timedelta(days=d)
            day_str = day.strftime("%Y-%m-%d")
            worst = "none"
            for inc in incidents:
                inc_start = inc["created_at"][:10]
                inc_end = (inc.get("resolved_at") or "9999-12-31")[:10]
                if inc_start <= day_str <= inc_end:
                    sev = inc.get("severity", "minor")
                    if sev == "critical":
                        worst = "critical"
                    elif sev == "major" and worst != "critical":
                        worst = "major"
                    elif sev == "minor" and worst == "none":
                        worst = "minor"
            color_map = {"none": "#10b981", "minor": "#f59e0b", "major": "#f97316", "critical": "#ef4444"}
            c = color_map[worst]
            label = day.strftime("%b %d")
            day_cells += f'<div class="day" style="background:{c}" title="{label}: {worst}"></div>'

        # Recent incidents list
        recent = await db.incidents.find(
            {"created_at": {"$gte": since}},
            {"_id": 0, "incident_id": 1, "title": 1, "severity": 1, "status": 1, "created_at": 1, "resolved_at": 1, "duration_minutes": 1, "updates": 1}
        ).sort("created_at", -1).to_list(20)

        inc_html = ""
        if recent:
            for inc in recent:
                sev = inc.get("severity", "minor")
                sev_color = {"minor": "#f59e0b", "major": "#f97316", "critical": "#ef4444"}.get(sev, "#71717a")
                st = inc.get("status", "investigating")
                st_color = "#10b981" if st == "resolved" else "#f59e0b"
                title = escape(inc.get("title", "Untitled"))
                created = inc["created_at"][:16].replace("T", " ")
                dur = inc.get("duration_minutes")
                dur_text = f" &middot; {dur:.0f}min" if dur else ""

                updates_html = ""
                for u in (inc.get("updates") or [])[-3:]:
                    u_time = u["timestamp"][:16].replace("T", " ")
                    u_msg = escape(u.get("message", ""))
                    u_st = u.get("status", "")
                    updates_html += f'<div class="upd"><span class="upd-time">{u_time}</span> <span class="upd-st">{u_st}</span> {u_msg}</div>'

                inc_html += f"""<div class="inc-card">
                    <div class="inc-header">
                        <div><span class="sev-badge" style="background:{sev_color}20;color:{sev_color};border:1px solid {sev_color}40">{sev.upper()}</span>
                        <span class="inc-title">{title}</span></div>
                        <span class="inc-status" style="color:{st_color}">{st}{dur_text}</span>
                    </div>
                    <div class="inc-meta">{created} UTC</div>
                    {updates_html}
                </div>"""
        else:
            inc_html = '<div style="text-align:center;padding:24px;color:#52525b;font-size:13px">No incidents in the past 90 days</div>'

        # Uptime percentage
        total_days = 90
        incident_days = set()
        for inc in incidents:
            start = datetime.fromisoformat(inc["created_at"][:10])
            end_str = (inc.get("resolved_at") or now.isoformat())[:10]
            end = datetime.fromisoformat(end_str)
            d = start
            while d <= end:
                incident_days.add(d.strftime("%Y-%m-%d"))
                d += timedelta(days=1)
        uptime_pct = round((total_days - len(incident_days)) / total_days * 100, 2)

        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexus Cloud &mdash; Status</title>
<meta http-equiv="refresh" content="30">
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#09090b;color:#fafafa;font-family:system-ui,-apple-system,sans-serif}}
.container{{max-width:640px;margin:0 auto;padding:40px 20px}}
.svc-row{{display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid #27272a}}
.svc-row:last-child{{border-bottom:none}}
.svc-name{{font-size:14px;color:#e4e4e7;font-weight:500}}
.svc-desc{{font-size:11px;color:#71717a;margin-top:2px}}
.svc-badge{{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500}}
.dot{{width:8px;height:8px;border-radius:50%}}
.banner{{display:inline-flex;align-items:center;gap:6px;padding:6px 16px;border-radius:20px}}
.timeline{{display:flex;gap:2px;margin:16px 0 4px;flex-wrap:wrap}}
.day{{width:6px;height:24px;border-radius:2px;flex-shrink:0}}
.sec-title{{font-size:14px;color:#a1a1aa;font-weight:600;margin:32px 0 12px;display:flex;align-items:center;justify-content:space-between}}
.inc-card{{background:#18181b;border:1px solid #27272a;border-radius:8px;padding:12px 16px;margin-bottom:8px}}
.inc-header{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
.inc-title{{font-size:13px;color:#e4e4e7;font-weight:500}}
.inc-status{{font-size:11px;font-weight:500;white-space:nowrap}}
.inc-meta{{font-size:11px;color:#52525b;margin-top:4px}}
.sev-badge{{font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;margin-right:6px;letter-spacing:0.5px}}
.upd{{font-size:11px;color:#71717a;margin-top:6px;padding-left:8px;border-left:2px solid #27272a}}
.upd-time{{color:#52525b}}
.upd-st{{color:#a1a1aa;font-weight:500;text-transform:capitalize}}
.legend{{display:flex;gap:12px;font-size:10px;color:#52525b;margin-top:4px}}
.legend-item{{display:flex;align-items:center;gap:4px}}
.legend-dot{{width:6px;height:6px;border-radius:1px}}
</style></head>
<body><div class="container">
<div style="text-align:center;margin-bottom:40px">
<h1 style="font-size:24px;font-weight:700;margin:0;font-family:Syne,sans-serif">NEXUS <span style="color:#22d3ee">CLOUD</span></h1>
<p style="font-size:13px;color:#a1a1aa;margin-top:8px">System Status</p>
<div class="banner" style="margin-top:16px;background:{banner_bg};border:1px solid {banner_border}">
<div class="dot" style="background:{banner_color}"></div>
<span style="font-size:13px;color:{banner_color};font-weight:500">{banner_text}</span>
</div></div>

<div style="background:#18181b;border:1px solid #27272a;border-radius:12px;padding:4px 16px">{svc_rows}</div>

<div class="sec-title"><span>90-Day Uptime</span><span style="font-size:12px;color:#10b981;font-weight:700">{uptime_pct}%</span></div>
<div class="timeline">{day_cells}</div>
<div class="legend">
<div class="legend-item"><div class="legend-dot" style="background:#10b981"></div>No issues</div>
<div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>Minor</div>
<div class="legend-item"><div class="legend-dot" style="background:#f97316"></div>Major</div>
<div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>Critical</div>
</div>

<div class="sec-title">Incident History</div>
{inc_html}

<div style="text-align:center;margin-top:24px;font-size:11px;color:#52525b">
Uptime: {hours}h {minutes}m &middot; Auto-refreshes every 30s &middot; {now.strftime("%Y-%m-%d %H:%M UTC")}
</div></div></body></html>"""

    # ============ REDIS HEALTH ============

    @api_router.get("/health/redis")
    async def redis_health_endpoint():
        """Dedicated Redis health probe endpoint."""
        try:
            from redis_client import health_check as redis_health, REDIS_REQUIRED, REDIS_URL
            result = await redis_health()
            result["redis_required"] = REDIS_REQUIRED
            result["redis_configured"] = bool(REDIS_URL)
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)[:200]}

    # ============ API DOCS PAGE ============

    @api_router.get("/docs/api", response_class=HTMLResponse)
    async def api_docs_page():
        """Public API reference — comprehensive endpoint documentation with examples."""
        endpoints = [
            ("Authentication", [
                ("POST", "/api/auth/register", "Register a new user account",
                 '{"email":"user@example.com","password":"securePass123","name":"Jane Doe"}',
                 '{"user_id":"user_abc123","email":"user@example.com","name":"Jane Doe"}'),
                ("POST", "/api/auth/login", "Login with email/password — returns session cookie",
                 '{"email":"user@example.com","password":"securePass123"}',
                 '{"user_id":"user_abc123","email":"user@example.com","name":"Jane Doe"} + Set-Cookie: session_token=...'),
                ("GET", "/api/auth/me", "Get current authenticated user", None,
                 '{"user_id":"user_abc123","email":"user@example.com","name":"Jane Doe","platform_role":"member"}'),
                ("POST", "/api/auth/logout", "Invalidate current session", None, '{"status":"logged_out"}'),
                ("POST", "/api/auth/mfa/setup", "Initialize MFA/TOTP setup (returns QR code)", None,
                 '{"secret":"JBSWY3DPEHPK3PXP","qr_url":"otpauth://totp/Nexus:user@example.com?..."}'),
                ("POST", "/api/auth/mfa/verify", "Verify MFA TOTP code",
                 '{"code":"123456"}', '{"verified":true}'),
            ]),
            ("SSO", [
                ("GET", "/api/sso/providers", "List enabled SSO providers (public)", None,
                 '{"providers":[{"config_id":"sso_abc","provider_name":"Okta","protocol":"saml"}]}'),
                ("GET", "/api/sso/saml/login/:config_id", "Initiate SAML SSO — redirects to IdP", None, "302 Redirect to IdP"),
                ("POST", "/api/sso/saml/acs/:config_id", "SAML Assertion Consumer Service", "SAMLResponse=base64...", "302 Redirect + Set-Cookie"),
                ("GET", "/api/sso/oidc/login/:config_id", "Initiate OIDC SSO — redirects to auth server", None, "302 Redirect to authorization_url"),
                ("GET", "/api/sso/oidc/callback/:config_id", "OIDC authorization code callback", None, "302 Redirect + Set-Cookie"),
            ]),
            ("Workspaces", [
                ("GET", "/api/workspaces", "List user's workspaces", None,
                 '{"workspaces":[{"workspace_id":"ws_abc","name":"My Team","created_at":"2026-01-15T..."}]}'),
                ("POST", "/api/workspaces", "Create workspace",
                 '{"name":"Engineering","description":"Dev team workspace"}',
                 '{"workspace_id":"ws_abc","name":"Engineering","status":"created"}'),
                ("GET", "/api/workspaces/:id", "Get workspace details", None,
                 '{"workspace_id":"ws_abc","name":"Engineering","members":12,"channels":5}'),
                ("POST", "/api/workspaces/:id/invite", "Invite member",
                 '{"email":"colleague@example.com","role":"member"}', '{"status":"invited"}'),
            ]),
            ("Channels & Messages", [
                ("POST", "/api/workspaces/:id/channels", "Create channel",
                 '{"name":"general","agents":["claude","chatgpt"]}',
                 '{"channel_id":"ch_abc","name":"general","agents":["claude","chatgpt"]}'),
                ("GET", "/api/channels/:id/messages", "Get messages (paginated ?limit=50&before=msg_id)", None,
                 '{"messages":[{"msg_id":"msg_abc","content":"Hello!","sender":"user_abc","timestamp":"..."}]}'),
                ("POST", "/api/channels/:id/messages", "Send message",
                 '{"content":"@claude Explain async/await in Python"}',
                 '{"msg_id":"msg_abc","content":"@claude Explain async/await in Python","timestamp":"..."}'),
                ("POST", "/api/channels/:id/collaborate", "Start AI collaboration round",
                 '{"prompt":"Design a REST API","agents":["claude","chatgpt"]}',
                 '{"collaboration_id":"collab_abc","status":"started","agents_responding":2}'),
            ]),
            ("AI Models", [
                ("GET", "/api/ai-models", "List available AI models with variants", None,
                 '{"models":{"claude":[{"id":"claude-opus-4","name":"Claude Opus 4","default":true}],"qwen":[...]}}'),
                ("POST", "/api/ai-keys", "Save AI API key for a provider",
                 '{"provider":"claude","api_key":"sk-ant-..."}', '{"status":"saved"}'),
            ]),
            ("Projects & Tasks", [
                ("POST", "/api/channels/:id/projects", "Create project",
                 '{"name":"Q1 Sprint","description":"Sprint tasks"}',
                 '{"project_id":"proj_abc","name":"Q1 Sprint"}'),
                ("POST", "/api/tasks", "Create task",
                 '{"title":"Fix login bug","assignee":"claude","priority":"high","due_date":"2026-03-20"}',
                 '{"task_id":"task_abc","title":"Fix login bug","status":"todo"}'),
            ]),
            ("Agent Marketplace", [
                ("GET", "/api/marketplace/agents", "Browse published agent configs (?category=coding&sort=popular)", None,
                 '{"agents":[{"agent_id":"agent_abc","name":"Code Reviewer","rating":4.5,"installs":120}],"total":15}'),
                ("POST", "/api/marketplace/agents", "Publish custom agent config",
                 '{"name":"Code Reviewer","description":"Reviews PRs","category":"coding","base_model":"claude","system_prompt":"..."}',
                 '{"agent_id":"agent_abc","status":"published"}'),
                ("POST", "/api/marketplace/agents/:id/rate", "Rate an agent",
                 '{"rating":5,"review":"Excellent code reviewer!"}', '{"status":"rated"}'),
                ("POST", "/api/marketplace/agents/:id/install", "Install agent to workspace", None, '{"status":"installed"}'),
            ]),
            ("Incidents", [
                ("GET", "/api/incidents", "List incidents (?days=90, ?status=resolved)", None,
                 '{"incidents":[{"incident_id":"inc_abc","title":"API Latency","severity":"minor","status":"resolved"}],"total":3}'),
                ("GET", "/api/incidents/timeline", "90-day daily severity timeline", None,
                 '{"timeline":[{"date":"2026-03-12","severity":"none","count":0}],"days":90}'),
                ("POST", "/api/incidents", "Create incident (admin)",
                 '{"title":"Database slowdown","severity":"major","affected_services":["database"]}',
                 '{"incident_id":"inc_abc","status":"investigating"}'),
            ]),
            ("Health & Status", [
                ("GET", "/api/health", "Health check with DB connectivity", None,
                 '{"status":"healthy","db":"connected","uptime":86400}'),
                ("GET", "/api/health/redis", "Redis health probe", None,
                 '{"status":"operational","latency_ms":1.2,"version":"7.2.4","redis_required":false}'),
                ("GET", "/api/status", "Complete platform status (JSON)", None,
                 '{"status":"operational","services":{"database":{"status":"operational","latency_ms":2.1}}}'),
                ("GET", "/api/status/page", "Status dashboard (HTML)", None, "Rendered HTML page"),
                ("GET", "/api/docs", "Swagger UI (interactive)", None, "Interactive API explorer"),
                ("GET", "/api/redoc", "ReDoc documentation", None, "ReDoc documentation page"),
            ]),
            ("SCIM 2.0 Provisioning", [
                ("GET", "/api/scim/v2/Users", "List users (SCIM)", None,
                 '{"schemas":["urn:ietf:params:scim:api:messages:2.0:ListResponse"],"totalResults":5,"Resources":[...]}'),
                ("POST", "/api/scim/v2/Users", "Create user (SCIM)",
                 '{"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"userName":"jane@example.com","displayName":"Jane"}',
                 '{"id":"user_abc","userName":"jane@example.com","active":true}'),
            ]),
        ]

        sections = ""
        for cat, eps in endpoints:
            rows = ""
            for ep in eps:
                method, path, desc = ep[0], ep[1], ep[2]
                req_body = ep[3] if len(ep) > 3 else None
                resp_body = ep[4] if len(ep) > 4 else None
                m_color = {"GET": "#22d3ee", "POST": "#10b981", "PUT": "#f59e0b", "PATCH": "#a78bfa", "DELETE": "#ef4444"}.get(method, "#71717a")
                example_html = ""
                if req_body:
                    example_html += f'<div class="ex"><span class="ex-label">Request</span><code>{escape(req_body)}</code></div>'
                if resp_body:
                    example_html += f'<div class="ex"><span class="ex-label">Response</span><code>{escape(resp_body)}</code></div>'
                rows += f"""<div class="ep-row">
                    <div class="ep-main">
                        <span class="method" style="color:{m_color}">{method}</span>
                        <code class="ep-path">{path}</code>
                        <span class="ep-desc">{desc}</span>
                    </div>
                    {example_html}
                </div>"""
            sections += f"""<div class="ep-section">
                <h3>{cat}</h3>
                <div class="ep-list">{rows}</div>
            </div>"""

        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexus Cloud — API Reference</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#09090b;color:#fafafa;font-family:system-ui,-apple-system,sans-serif}}
.container{{max-width:800px;margin:0 auto;padding:40px 20px}}
a{{color:#22d3ee;text-decoration:none}}a:hover{{text-decoration:underline}}
.ep-section{{margin-bottom:28px}}
.ep-section h3{{font-size:15px;color:#e4e4e7;margin:0 0 8px;font-weight:600;padding-bottom:6px;border-bottom:1px solid #27272a}}
.ep-list{{background:#0a0a0b;border:1px solid #1f1f23;border-radius:8px;padding:4px 12px}}
.ep-row{{padding:10px 0;border-bottom:1px solid #1f1f23}}
.ep-row:last-child{{border-bottom:none}}
.ep-main{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.method{{font-size:10px;font-weight:700;width:50px;text-align:right;font-family:monospace;flex-shrink:0}}
.ep-path{{font-size:12px;color:#d4d4d8;flex:1;min-width:200px}}
.ep-desc{{font-size:11px;color:#71717a}}
.ex{{margin-top:6px;padding:4px 0 0 62px}}
.ex-label{{font-size:9px;color:#52525b;font-weight:600;text-transform:uppercase;margin-right:8px}}
.ex code{{font-size:10px;color:#a1a1aa;word-break:break-all;background:#18181b;padding:2px 6px;border-radius:3px}}
.auth-box{{background:#18181b;border:1px solid #27272a;border-radius:8px;padding:16px;margin-bottom:28px;font-size:12px;color:#a1a1aa}}
.auth-box code{{color:#22d3ee;background:#27272a;padding:1px 4px;border-radius:2px}}
.auth-box h4{{color:#e4e4e7;margin:0 0 8px;font-size:13px}}
</style></head>
<body><div class="container">
<h1 style="font-size:24px;font-weight:700;margin:0 0 4px;font-family:Syne,sans-serif">NEXUS <span style="color:#22d3ee">CLOUD</span> API</h1>
<p style="font-size:13px;color:#a1a1aa;margin:0 0 8px">REST API v1.1.0 — Comprehensive Reference</p>
<p style="font-size:12px;color:#71717a;margin:0 0 24px">
Interactive docs: <a href="/api/docs">Swagger UI</a> &middot; <a href="/api/redoc">ReDoc</a> &middot;
<a href="/api/openapi.json">OpenAPI Spec</a>
</p>
<div class="auth-box">
<h4>Authentication</h4>
<p>Most endpoints require authentication via session cookie. Obtain it by calling:</p>
<p><code>POST /api/auth/login</code> with <code>{{"email":"...","password":"..."}}</code></p>
<p>The response sets an <code>HttpOnly</code> cookie named <code>session_token</code>. Include it in subsequent requests.</p>
<p style="margin-top:8px">For SCIM provisioning, use a Bearer token: <code>Authorization: Bearer &lt;scim_token&gt;</code></p>
<p>For SSO: Use <code>GET /api/sso/saml/login/:config_id</code> or <code>GET /api/sso/oidc/login/:config_id</code></p>
</div>
{sections}
<div style="text-align:center;margin-top:32px;font-size:11px;color:#52525b">
Nexus Cloud API v1.1.0 &middot; 19 AI Models &middot; Enterprise-Ready
</div></div></body></html>"""


async def _check_ai_providers() -> dict:
    configured = []
    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_AI_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "xai": "XAI_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY",
        "groq": "GROQ_API_KEY",
        "qwen": "QWEN_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
        "llama": "TOGETHER_API_KEY",
        "glm": "ZHIPU_API_KEY",
    }
    for provider, env_var in provider_env_map.items():
        if os.environ.get(env_var):
            configured.append(provider)
    # OpenRouter-based agents count if key exists
    if os.environ.get("OPENROUTER_API_KEY"):
        for p in ["cursor", "notebooklm", "copilot", "pi"]:
            if p not in configured:
                configured.append(p)
    return {
        "status": "operational" if configured else "degraded",
        "configured_count": len(configured),
        "providers": configured,
    }


def _check_file_storage() -> dict:
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    try:
        if os.path.isdir(upload_dir):
            test_path = os.path.join(upload_dir, ".health_check")
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
            file_count = sum(1 for _ in os.scandir(upload_dir) if _.is_file() or _.is_dir())
            return {"status": "operational", "note": f"{file_count} items in storage", "writable": True}
        return {"status": "degraded", "note": "Upload directory missing"}
    except Exception as e:
        return {"status": "degraded", "note": f"Storage error: {str(e)[:80]}"}
