"""Super Admin System - Bug tracking, usage logs, and platform administration"""
import uuid
import os
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List

# Super admin email - only this account can access admin features
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "")


class BugReport(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    steps_to_reproduce: Optional[str] = Field(None, max_length=2000)
    expected_behavior: Optional[str] = Field(None, max_length=1000)
    actual_behavior: Optional[str] = Field(None, max_length=1000)
    severity: str = Field(default="medium", description="low, medium, high, critical")
    category: str = Field(default="general", description="ui, backend, ai, performance, other")
    browser: Optional[str] = None
    screenshot_url: Optional[str] = None


class BugUpdate(BaseModel):
    status: Optional[str] = Field(None, description="open, in_progress, resolved, closed, wont_fix")
    priority: Optional[str] = Field(None, description="low, medium, high, critical")
    admin_notes: Optional[str] = None
    assigned_to: Optional[str] = None


class UserRoleUpdate(BaseModel):
    platform_role: str = Field(..., description="super_admin, platform_support, admin, moderator, user")


# Platform roles: super_admin > platform_support > admin > moderator > user
PLATFORM_ROLES = ["super_admin", "platform_support", "admin", "moderator", "user"]
ADMIN_ROLES = ["super_admin", "platform_support", "admin"]  # Full admin access
STAFF_ROLES = ["super_admin", "platform_support", "admin", "moderator"]  # Can view admin panel
SUPPORT_ROLES = ["super_admin", "platform_support"]  # Platform-level support access


async def is_super_admin(db, user_id: str) -> bool:
    """Check if user is super admin — by email OR by DB platform_role (V3: consistent with get_platform_role)"""
    user = await db.users.find_one({"user_id": user_id}, {"email": 1, "platform_role": 1})
    if not user:
        return False
    if user.get("email", "").lower() == SUPER_ADMIN_EMAIL.lower():
        return True
    return user.get("platform_role") == "super_admin"


async def get_platform_role(db, user_id: str) -> str:
    """Get user's platform role. Super admin is determined by email."""
    user = await db.users.find_one({"user_id": user_id}, {"email": 1, "platform_role": 1})
    if not user:
        return "user"
    if user.get("email", "").lower() == SUPER_ADMIN_EMAIL.lower():
        return "super_admin"
    return user.get("platform_role", "user")


async def require_super_admin(db, user_id: str):
    """Require super admin access or raise 403"""
    if not await is_super_admin(db, user_id):
        raise HTTPException(403, "Super admin access required")


async def require_staff(db, user_id: str):
    """Require at least moderator access or raise 403"""
    role = await get_platform_role(db, user_id)
    if role not in STAFF_ROLES:
        raise HTTPException(403, "Staff access required")


async def is_platform_support(db, user_id: str) -> bool:
    """Check if user has platform support role"""
    role = await get_platform_role(db, user_id)
    return role in SUPPORT_ROLES


async def require_platform_support(db, user_id: str):
    """Require platform support or super admin access"""
    role = await get_platform_role(db, user_id)
    if role not in SUPPORT_ROLES:
        raise HTTPException(403, "Platform support access required")


def can_delete(role: str) -> bool:
    """Check if a platform role has delete permissions. Platform Support cannot delete."""
    return role == "super_admin"


def register_admin_routes(api_router, db, get_current_user):
    
    # ============= BUG REPORTS (Public submission) =============
    
    @api_router.post("/bugs")
    async def submit_bug_report(data: BugReport, request: Request):
        """Submit a bug report (authenticated users only)"""
        user = await get_current_user(request)
        
        bug_id = f"bug_{uuid.uuid4().hex[:12]}"
        
        bug = {
            "bug_id": bug_id,
            "title": data.title,
            "description": data.description,
            "steps_to_reproduce": data.steps_to_reproduce,
            "expected_behavior": data.expected_behavior,
            "actual_behavior": data.actual_behavior,
            "severity": data.severity,
            "category": data.category,
            "browser": data.browser,
            "screenshot_url": data.screenshot_url,
            "status": "open",
            "priority": data.severity,  # Initially same as severity
            "submitted_by": user["user_id"],
            "submitter_email": user.get("email", ""),
            "submitter_name": user.get("name", "Anonymous"),
            "admin_notes": None,
            "assigned_to": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.bug_reports.insert_one(bug)
        
        # Log the submission
        await log_platform_event(db, "bug_submitted", user["user_id"], {
            "bug_id": bug_id,
            "title": data.title,
            "severity": data.severity
        })
        
        return {
            "status": "submitted",
            "bug_id": bug_id,
            "message": "Thank you for reporting this bug. Our team will review it shortly."
        }
    
    @api_router.get("/bugs/my-reports")
    async def get_my_bug_reports(request: Request):
        """Get bugs submitted by current user"""
        user = await get_current_user(request)
        
        bugs = await db.bug_reports.find(
            {"submitted_by": user["user_id"]},
            {"_id": 0, "admin_notes": 0}  # Hide admin notes from users
        ).sort("created_at", -1).to_list(50)
        
        return {"bugs": bugs, "count": len(bugs)}
    
    # ============= ADMIN-ONLY BUG MANAGEMENT =============
    
    @api_router.get("/admin/bugs")
    async def get_all_bugs(
        request: Request,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50
    ):
        """Get all bug reports (staff access: super_admin, admin, moderator)"""
        user = await get_current_user(request)
        await require_staff(db, user["user_id"])
        
        query = {}
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if category:
            query["category"] = category
        
        bugs = await db.bug_reports.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        
        # Get counts by status
        stats = {
            "total": await db.bug_reports.count_documents({}),
            "open": await db.bug_reports.count_documents({"status": "open"}),
            "in_progress": await db.bug_reports.count_documents({"status": "in_progress"}),
            "resolved": await db.bug_reports.count_documents({"status": "resolved"}),
            "closed": await db.bug_reports.count_documents({"status": "closed"})
        }
        
        return {"bugs": bugs, "stats": stats}
    
    @api_router.get("/admin/bugs/{bug_id}")
    async def get_bug_detail(bug_id: str, request: Request):
        """Get detailed bug report (staff access)"""
        user = await get_current_user(request)
        await require_staff(db, user["user_id"])
        
        bug = await db.bug_reports.find_one({"bug_id": bug_id}, {"_id": 0})
        if not bug:
            raise HTTPException(404, "Bug report not found")
        
        return bug
    
    @api_router.put("/admin/bugs/{bug_id}")
    async def update_bug(bug_id: str, data: BugUpdate, request: Request):
        """Update bug status/priority (admin and super_admin only)"""
        user = await get_current_user(request)
        role = await get_platform_role(db, user["user_id"])
        if role not in ADMIN_ROLES:
            raise HTTPException(403, "Admin access required to update bugs")
        
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.status:
            if data.status not in ["open", "in_progress", "resolved", "closed", "wont_fix"]:
                raise HTTPException(400, "Invalid status")
            updates["status"] = data.status
        if data.priority:
            if data.priority not in ["low", "medium", "high", "critical"]:
                raise HTTPException(400, "Invalid priority")
            updates["priority"] = data.priority
        if data.admin_notes is not None:
            updates["admin_notes"] = data.admin_notes
        if data.assigned_to is not None:
            updates["assigned_to"] = data.assigned_to
        
        result = await db.bug_reports.update_one(
            {"bug_id": bug_id},
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "Bug report not found")
        
        return {"status": "updated"}
    
    @api_router.delete("/admin/bugs/{bug_id}")
    async def delete_bug(bug_id: str, request: Request):
        """Delete a bug report (super admin only)"""
        user = await get_current_user(request)
        await require_super_admin(db, user["user_id"])
        
        result = await db.bug_reports.delete_one({"bug_id": bug_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Bug report not found")
        
        return {"status": "deleted"}
    
    # ============= USAGE LOGS & ANALYTICS =============
    
    @api_router.get("/admin/logs")
    async def get_platform_logs(
        request: Request,
        event_type: Optional[str] = None,
        days: int = 7,
        limit: int = 100
    ):
        """Get platform usage logs (staff access)"""
        user = await get_current_user(request)
        await require_staff(db, user["user_id"])
        
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {"timestamp": {"$gte": cutoff}}
        if event_type:
            query["event_type"] = event_type
        
        logs = await db.platform_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).to_list(limit)
        
        return {"logs": logs, "count": len(logs)}
    
    @api_router.get("/admin/stats")
    async def get_platform_stats(request: Request):
        """Get platform-wide statistics (staff access)"""
        user = await get_current_user(request)
        await require_staff(db, user["user_id"])
        
        # User stats
        total_users = await db.users.count_documents({})
        users_today = await db.users.count_documents({
            "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()}
        })
        users_week = await db.users.count_documents({
            "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}
        })
        
        # Workspace stats
        total_workspaces = await db.workspaces.count_documents({})
        active_workspaces = await db.workspaces.count_documents({"disabled": {"$ne": True}})
        
        # Channel stats
        total_channels = await db.channels.count_documents({})
        
        # Message stats
        total_messages = await db.messages.count_documents({})
        messages_today = await db.messages.count_documents({
            "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()}
        })
        
        # AI collaboration stats
        ai_messages = await db.messages.count_documents({"sender_type": "ai"})
        human_messages = await db.messages.count_documents({"sender_type": "human"})
        ai_messages_today = await db.messages.count_documents({
            "sender_type": "ai",
            "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()}
        })
        
        # Task session stats
        total_tasks = await db.task_sessions.count_documents({})
        active_tasks = await db.task_sessions.count_documents({"status": "active"})
        
        # Project stats
        total_projects = await db.projects.count_documents({})
        total_project_tasks = await db.project_tasks.count_documents({})
        done_project_tasks = await db.project_tasks.count_documents({"status": "done"})
        
        # Wiki stats
        total_wiki_pages = await db.wiki_pages.count_documents({"is_deleted": {"$ne": True}})
        
        # Code repo stats
        total_repo_files = await db.repo_files.count_documents({"is_deleted": {"$ne": True}})
        total_commits = await db.repo_commits.count_documents({})
        
        # Org stats
        total_orgs = await db.orgs.count_documents({})
        
        # Bug report stats
        open_bugs = await db.bug_reports.count_documents({"status": "open"})
        total_bugs = await db.bug_reports.count_documents({})
        
        # File stats
        total_files = await db.files.count_documents({})
        
        # Top workspaces by message count
        top_ws_pipeline = [
            {"$group": {"_id": "$channel_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        top_channels = [c async for c in db.messages.aggregate(top_ws_pipeline)]
        top_workspaces = []
        for tc in top_channels[:5]:
            ch = await db.channels.find_one({"channel_id": tc["_id"]}, {"_id": 0, "workspace_id": 1, "name": 1})
            if ch:
                ws = await db.workspaces.find_one({"workspace_id": ch.get("workspace_id", "")}, {"_id": 0, "name": 1, "workspace_id": 1})
                if ws:
                    top_workspaces.append({"workspace_id": ws["workspace_id"], "name": ws["name"], "message_count": tc["count"]})
        
        # Agent usage breakdown
        agent_pipeline = [
            {"$match": {"sender_type": "ai"}},
            {"$group": {"_id": "$ai_model", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        agent_usage = [{"agent": a["_id"], "messages": a["count"]} async for a in db.messages.aggregate(agent_pipeline)]
        
        return {
            "users": {
                "total": total_users,
                "today": users_today,
                "this_week": users_week
            },
            "workspaces": {
                "total": total_workspaces,
                "active": active_workspaces
            },
            "channels": {
                "total": total_channels
            },
            "messages": {
                "total": total_messages,
                "today": messages_today,
                "ai": ai_messages,
                "human": human_messages
            },
            "collaborations": {
                "total": ai_messages,
                "today": ai_messages_today,
            },
            "projects": {
                "total": total_projects,
                "tasks": total_project_tasks,
                "tasks_done": done_project_tasks,
            },
            "wiki": {
                "pages": total_wiki_pages,
            },
            "code_repo": {
                "files": total_repo_files,
                "commits": total_commits,
            },
            "orgs": {
                "total": total_orgs,
            },
            "tasks": {
                "total": total_tasks,
                "active": active_tasks
            },
            "bugs": {
                "total": total_bugs,
                "open": open_bugs
            },
            "files": {
                "total": total_files
            },
            "top_workspaces": top_workspaces,
            "agent_usage": agent_usage,
        }

    @api_router.get("/admin/startup-diagnostics")
    async def get_startup_diagnostics(request: Request):
        """Staff-only startup diagnostics for route health, startup probes, and registration issues."""
        user = await get_current_user(request)
        await require_staff(db, user["user_id"])

        diagnostics = {"timestamp": datetime.now(timezone.utc).isoformat()}

        try:
            await db.command("ping")
            diagnostics["database"] = {"status": "ok"}
        except Exception as exc:
            diagnostics["database"] = {"status": "error", "message": str(exc)[:200]}

        try:
            from redis_client import health_check as redis_health
            diagnostics["redis"] = await redis_health()
        except Exception as exc:
            diagnostics["redis"] = {"status": "error", "message": str(exc)[:200]}

        route_map = {}
        duplicates = []
        media_route_count = 0
        for route in request.app.routes:
            path = getattr(route, "path", "")
            methods = sorted(list(getattr(route, "methods", []) or []))
            if path.startswith("/api/workspaces/") and "/media" in path:
                media_route_count += 1
            for method in methods:
                key = f"{method}:{path}"
                route_map[key] = route_map.get(key, 0) + 1
        for key, count in route_map.items():
            if count > 1:
                duplicates.append({"route": key, "count": count})

        diagnostics["routes"] = {
            "total": len(route_map),
            "duplicates": duplicates,
            "media_route_count": media_route_count,
            "workspace_tools_endpoint": any(getattr(route, "path", "") == "/api/workspaces/{workspace_id}/tools" for route in request.app.routes),
        }

        try:
            from pathlib import Path
            routes_init = Path(__file__).resolve().parent / "__init__.py"
            text = routes_init.read_text()
            diagnostics["registration"] = {
                "routes_media_wildcard_present": "from routes.routes_media import *" in text,
            }
        except Exception as exc:
            diagnostics["registration"] = {"status": "error", "message": str(exc)[:200]}

        diagnostics["startup_probe"] = {
            "ready": diagnostics.get("database", {}).get("status") == "ok" and diagnostics.get("redis", {}).get("status") in {"operational", "disabled", "ok"},
        }

        return diagnostics

    @api_router.get("/admin/system-health")
    async def get_system_health(request: Request):
        """Staff-only database and system health dashboard data."""
        import time
        import psutil
        import shutil

        user = await get_current_user(request)
        await require_staff(db, user["user_id"])

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {},
            "system": {},
            "query_probes": [],
            "collections": [],
            "index_overview": [],
        }

        try:
            t0 = time.monotonic()
            db_stats = await db.command("dbStats")
            ping_ms = round((time.monotonic() - t0) * 1000, 2)
            summary["database"] = {
                "status": "ok",
                "ping_ms": ping_ms,
                "collections": db_stats.get("collections", 0),
                "objects": db_stats.get("objects", 0),
                "data_size_mb": round((db_stats.get("dataSize", 0) or 0) / (1024 * 1024), 2),
                "storage_size_mb": round((db_stats.get("storageSize", 0) or 0) / (1024 * 1024), 2),
                "index_size_mb": round((db_stats.get("indexSize", 0) or 0) / (1024 * 1024), 2),
            }
        except Exception as exc:
            summary["database"] = {"status": "error", "message": str(exc)[:200]}

        try:
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage("/")
            summary["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_used_pct": mem.percent,
                "memory_available_mb": round(mem.available / (1024 * 1024)),
                "disk_used_pct": round(disk.used / disk.total * 100, 1),
                "disk_free_gb": round(disk.free / (1024 ** 3), 1),
            }
        except Exception as exc:
            summary["system"] = {"status": "error", "message": str(exc)[:200]}

        probe_specs = [
            ("users_lookup", lambda: db.users.find_one({}, {"_id": 0, "user_id": 1})),
            ("workspaces_count", lambda: db.workspaces.count_documents({})),
            ("messages_recent", lambda: db.messages.find({}, {"_id": 0, "message_id": 1}).sort("created_at", -1).to_list(5)),
            ("repo_files_count", lambda: db.repo_files.count_documents({"is_deleted": {"$ne": True}})),
        ]
        for name, fn in probe_specs:
            try:
                t0 = time.monotonic()
                await fn()
                latency_ms = round((time.monotonic() - t0) * 1000, 2)
                summary["query_probes"].append({
                    "name": name,
                    "latency_ms": latency_ms,
                    "status": "healthy" if latency_ms < 120 else "warning" if latency_ms < 400 else "slow",
                })
            except Exception as exc:
                summary["query_probes"].append({"name": name, "status": "error", "message": str(exc)[:200]})

        collection_names = [
            "users", "workspaces", "channels", "messages", "repo_files", "repo_commits",
            "organizations", "media_items", "publish_jobs", "cloud_connections",
            "managed_key_usage_events", "managed_key_budget_alerts",
        ]
        for coll_name in collection_names:
            try:
                stats = await db.command({"collStats": coll_name})
                summary["collections"].append({
                    "name": coll_name,
                    "count": stats.get("count", 0),
                    "size_mb": round((stats.get("size", 0) or 0) / (1024 * 1024), 3),
                    "storage_mb": round((stats.get("storageSize", 0) or 0) / (1024 * 1024), 3),
                    "avg_obj_kb": round((stats.get("avgObjSize", 0) or 0) / 1024, 3),
                    "indexes": stats.get("nindexes", 0),
                    "index_size_mb": round((stats.get("totalIndexSize", 0) or 0) / (1024 * 1024), 3),
                })
            except Exception:
                continue

        summary["collections"] = sorted(summary["collections"], key=lambda item: item.get("storage_mb", 0), reverse=True)
        summary["index_overview"] = [
            {
                "name": item["name"],
                "indexes": item.get("indexes", 0),
                "index_size_mb": item.get("index_size_mb", 0),
                "coverage": "strong" if item.get("indexes", 0) >= 3 else "moderate" if item.get("indexes", 0) >= 1 else "weak",
            }
            for item in summary["collections"][:10]
        ]

        return summary
    
    @api_router.get("/admin/users")
    async def get_all_users(
        request: Request,
        limit: int = 100,
        skip: int = 0
    ):
        """Get all users (staff access: super_admin, admin, moderator)"""
        user = await get_current_user(request)
        await require_staff(db, user["user_id"])
        
        users = await db.users.find(
            {},
            {"_id": 0, "user_id": 1, "email": 1, "name": 1, "picture": 1, 
             "auth_provider": 1, "auth_type": 1, "plan": 1, "platform_role": 1, "created_at": 1}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        # Annotate super admin
        for u in users:
            if u.get("email", "").lower() == SUPER_ADMIN_EMAIL.lower():
                u["platform_role"] = "super_admin"
            elif not u.get("platform_role"):
                u["platform_role"] = "user"
        
        total = await db.users.count_documents({})
        
        return {"users": users, "total": total}
    
    @api_router.get("/admin/users/{user_id}")
    async def get_user_detail(user_id: str, request: Request):
        """Get detailed user info (super admin only)"""
        user = await get_current_user(request)
        await require_super_admin(db, user["user_id"])
        
        target_user = await db.users.find_one(
            {"user_id": user_id},
            {"_id": 0, "ai_keys": 0}  # Don't expose API keys
        )
        if not target_user:
            raise HTTPException(404, "User not found")
        
        # Get user's workspaces
        workspaces = await db.workspaces.find(
            {"owner_id": user_id},
            {"_id": 0, "workspace_id": 1, "name": 1, "created_at": 1}
        ).to_list(50)
        
        # Get user's message count
        message_count = await db.messages.count_documents({"sender_id": user_id})
        
        return {
            "user": target_user,
            "workspaces": workspaces,
            "message_count": message_count
        }
    
    @api_router.get("/admin/check")
    async def check_admin_status(request: Request):
        """Check if current user is super admin, platform support, or staff"""
        user = await get_current_user(request)
        role = await get_platform_role(db, user["user_id"])
        
        return {
            "is_super_admin": role == "super_admin",
            "is_platform_support": role in SUPPORT_ROLES,
            "is_staff": role in STAFF_ROLES,
            "can_delete": can_delete(role),
            "platform_role": role,
            "email": user.get("email", "")
        }
    
    # ============= PLATFORM ROLE MANAGEMENT =============
    
    @api_router.put("/admin/users/{user_id}/role")
    async def update_user_role(user_id: str, data: UserRoleUpdate, request: Request):
        """Update a user's platform role (super admin only)"""
        user = await get_current_user(request)
        await require_super_admin(db, user["user_id"])
        
        if data.platform_role not in PLATFORM_ROLES:
            raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(PLATFORM_ROLES)}")
        
        # Don't allow changing super admin's own role
        target = await db.users.find_one({"user_id": user_id}, {"email": 1})
        if not target:
            raise HTTPException(404, "User not found")
        if target.get("email", "").lower() == SUPER_ADMIN_EMAIL.lower():
            raise HTTPException(400, "Cannot change super admin role")
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"platform_role": data.platform_role}}
        )
        
        await log_platform_event(db, "role_changed", user["user_id"], {
            "target_user_id": user_id,
            "new_role": data.platform_role
        })
        
        return {"status": "updated", "user_id": user_id, "platform_role": data.platform_role}
    
    @api_router.get("/admin/platform-roles")
    async def get_platform_roles(request: Request):
        """Get available platform roles with permissions"""
        await get_current_user(request)
        return {"roles": [
            {"key": "super_admin", "name": "Super Admin", "description": "Full platform access including delete", "can_delete": True, "admin_access": True, "support_access": True},
            {"key": "platform_support", "name": "Platform Support", "description": "Full access except delete — view, edit, manage all resources", "can_delete": False, "admin_access": True, "support_access": True},
            {"key": "admin", "name": "Admin", "description": "Admin panel access, manage users and settings", "can_delete": True, "admin_access": True, "support_access": False},
            {"key": "moderator", "name": "Moderator", "description": "Can view admin panel, moderate content", "can_delete": False, "admin_access": False, "support_access": False},
            {"key": "user", "name": "User", "description": "Standard user access", "can_delete": False, "admin_access": False, "support_access": False},
        ]}


    @api_router.delete("/admin/users/{user_id}")
    async def delete_user(user_id: str, request: Request):
        """Super admin: Delete a user account and all their data"""
        user = await get_current_user(request)
        await require_super_admin(db, user["user_id"])
        target = await db.users.find_one({"user_id": user_id})
        if not target:
            raise HTTPException(404, "User not found")
        target_role = await get_platform_role(db, user_id)
        if target_role == "super_admin":
            raise HTTPException(403, "Cannot delete a super admin")
        # Delete user data
        await db.users.delete_one({"user_id": user_id})
        await db.user_sessions.delete_many({"user_id": user_id})
        await db.notifications.delete_many({"user_id": user_id})
        await db.org_memberships.delete_many({"user_id": user_id})
        await log_platform_event(db, "user_deleted", user["user_id"], {"deleted_user": user_id, "email": target.get("email", "")})
        return {"message": f"User {target.get('email', user_id)} deleted"}

    @api_router.delete("/admin/organizations/{org_id}")
    async def delete_organization(org_id: str, request: Request):
        """Super admin: Delete an organization and ALL its data (V2: correct ordering + full cleanup)"""
        user = await get_current_user(request)
        await require_super_admin(db, user["user_id"])
        org = await db.organizations.find_one({"org_id": org_id})
        if not org:
            raise HTTPException(404, "Organization not found")
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        for wsid in ws_ids:
            # V2: Collect channel_ids BEFORE deleting channels
            ch_ids = [ch["channel_id"] async for ch in db.channels.find({"workspace_id": wsid}, {"channel_id": 1, "_id": 0})]
            if ch_ids:
                await db.messages.delete_many({"channel_id": {"$in": ch_ids}})
            await db.channels.delete_many({"workspace_id": wsid})
            # V2: Delete ALL workspace-scoped collections
            for coll in ['projects', 'project_tasks', 'workflows', 'artifacts',
                         'nexus_agents', 'workspace_memory', 'workspace_members',
                         'tasks', 'wiki_pages', 'wiki_versions',
                         'repo_files', 'repo_commits', 'drive_files',
                         'webhooks', 'a2a_pipelines', 'a2a_runs',
                         'deployments', 'deployment_runs', 'notifications',
                         'operator_sessions', 'consensus_sessions',
                         'work_queue', 'tpm_queue', 'managed_key_usage']:
                await getattr(db, coll).delete_many({"workspace_id": wsid})
        await db.workspaces.delete_many({"org_id": org_id})
        await db.org_memberships.delete_many({"org_id": org_id})
        await db.organizations.delete_one({"org_id": org_id})
        await log_platform_event(db, "org_deleted", user["user_id"], {"org_id": org_id, "name": org.get("name", "")})
        return {"message": f"Organization '{org.get('name', org_id)}' and all data deleted"}

    @api_router.put("/admin/users/{user_id}/plan")
    async def set_user_plan(user_id: str, request: Request):
        """Super admin: Manually set a user's billing plan"""
        user = await get_current_user(request)
        await require_super_admin(db, user["user_id"])
        body = await request.json()
        new_plan = body.get("plan", "free")
        valid_plans = ["free", "starter", "pro", "team", "enterprise"]
        if new_plan not in valid_plans:
            raise HTTPException(400, f"Invalid plan. Use: {valid_plans}")
        old_plan = (await db.users.find_one({"user_id": user_id}, {"plan": 1}) or {}).get("plan", "free")
        await db.users.update_one({"user_id": user_id}, {"$set": {"plan": new_plan}})
        await db.plan_changes.insert_one({
            "change_id": f"pc_{uuid.uuid4().hex[:12]}", "user_id": user_id,
            "old_plan": old_plan, "new_plan": new_plan,
            "change_type": "admin_override", "status": "active",
            "changed_by": user["user_id"],
            "changed_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"user_id": user_id, "old_plan": old_plan, "new_plan": new_plan}

    # --- Duplicate Overrides Admin ---
    @api_router.get("/admin/duplicate-overrides")
    async def get_duplicate_overrides(request: Request, workspace_id: str = None, entity_type: str = None, limit: int = 50):
        """View duplicate override audit log"""
        user = await get_current_user(request)
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        query = {}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if entity_type:
            query["entity_type"] = entity_type
        overrides = await db.duplicate_overrides.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        total = await db.duplicate_overrides.count_documents(query)
        return {"overrides": overrides, "total": total}

    @api_router.get("/admin/duplicate-overrides/stats")
    async def get_duplicate_stats(request: Request):
        """Get duplicate override stats"""
        user = await get_current_user(request)
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Admin access required")
        total = await db.duplicate_overrides.count_documents({})
        by_type = {}
        for et in ["project", "task", "milestone", "artifact", "repo_file"]:
            by_type[et] = await db.duplicate_overrides.count_documents({"entity_type": et})
        return {"total": total, "by_type": by_type}

    # --- Custom Google OAuth Configuration (Super Admin) ---
    @api_router.get("/admin/oauth-config")
    async def get_oauth_config(request: Request):
        """Get custom Google OAuth configuration."""
        user = await get_current_user(request)
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        settings = await db.platform_settings.find_one({"key": "google_oauth"}, {"_id": 0})
        if not settings:
            return {"configured": False}
        return {"configured": bool(settings.get("client_id")), "client_id": settings.get("client_id", "")[:8] + "..." if settings.get("client_id") else "", "redirect_uri": settings.get("redirect_uri", "")}

    @api_router.put("/admin/oauth-config")
    async def set_oauth_config(request: Request):
        """Configure custom Google OAuth (replaces Emergent bridge when set)."""
        user = await get_current_user(request)
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        body = await request.json()
        client_id = body.get("client_id", "").strip()
        client_secret = body.get("client_secret", "").strip()
        redirect_uri = body.get("redirect_uri", "").strip()
        if not client_id or not client_secret:
            raise HTTPException(400, "Both client_id and client_secret are required")
        await db.platform_settings.update_one(
            {"key": "google_oauth"},
            {"$set": {"key": "google_oauth", "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "configured_by": user["user_id"], "configured_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"configured": True}

    @api_router.delete("/admin/oauth-config")
    async def remove_oauth_config(request: Request):
        """Remove custom OAuth config (reverts to Emergent bridge)."""
        user = await get_current_user(request)
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        await db.platform_settings.delete_one({"key": "google_oauth"})
        return {"configured": False, "message": "Reverted to Emergent Google Auth bridge"}

    return is_super_admin


async def log_platform_event(db, event_type: str, user_id: str = None, data: dict = None):
    """Log a platform event for admin review"""
    log_entry = {
        "log_id": f"log_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "user_id": user_id,
        "data": data or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.platform_logs.insert_one(log_entry)
