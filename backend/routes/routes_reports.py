"""Gantt Charts, Planners, and Reports — workspace + org level"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



def register_reports_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    
    # Helper function to check org membership (replaces import from routes_orgs)
    async def require_org_member(org_id: str, user_id: str) -> str:
        """Verify user is a member of the organization"""
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user_id},
            {"_id": 0, "org_role": 1}
        )
        if not membership:
            raise HTTPException(403, "Not a member of this organization")
        return membership.get("org_role", "member")

    # ======================================================
    # GANTT CHART DATA
    # ======================================================

    @api_router.get("/workspaces/{workspace_id}/gantt")
    async def get_workspace_gantt(workspace_id: str, request: Request, project_id: Optional[str] = None):
        """Gantt chart data for a workspace (optionally filtered by project)"""
        await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id, "due_date": {"$ne": None}}
        if project_id:
            query["project_id"] = project_id

        tasks = await db.project_tasks.find(query, {"_id": 0}).sort("due_date", 1).to_list(500)

        # Enrich with project names
        if tasks:
            pids = list({t["project_id"] for t in tasks})
            projects = await db.projects.find({"project_id": {"$in": pids}}, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)
            pmap = {p["project_id"]: p["name"] for p in projects}
            for t in tasks:
                t["project_name"] = pmap.get(t["project_id"], "Unknown")

        # Get dependencies
        if tasks:
            tids = [t["task_id"] for t in tasks]
            deps = await db.task_dependencies.find(
                {"$or": [{"blocked_task_id": {"$in": tids}}, {"blocking_task_id": {"$in": tids}}]}, {"_id": 0}
            ).to_list(200)
        else:
            deps = []

        # Get milestones
        # Milestones are per-project, get all for matching projects
        if project_id:
            milestones = await db.milestones.find({"project_id": project_id}, {"_id": 0}).to_list(20)
        else:
            pids_all = [p["project_id"] async for p in db.projects.find({"workspace_id": workspace_id}, {"project_id": 1, "_id": 0})]
            milestones = await db.milestones.find({"project_id": {"$in": pids_all}}, {"_id": 0}).to_list(50) if pids_all else []

        # Build Gantt items
        gantt_items = []
        for t in tasks:
            created = t.get("created_at", "")[:10]
            due = t.get("due_date", "")[:10]
            gantt_items.append({
                "id": t["task_id"], "type": "task",
                "title": t["title"], "project": t.get("project_name", ""),
                "project_id": t["project_id"],
                "start": created, "end": due,
                "status": t.get("status", "todo"),
                "priority": t.get("priority", "medium"),
                "item_type": t.get("item_type", "task"),
                "assignee": t.get("assignee_name"),
                "progress": 100 if t.get("status") == "done" else 50 if t.get("status") in ("in_progress", "review") else 0,
                "dependencies": [],
            })

        # Map dependencies to Gantt items
        dep_map = {}
        for d in deps:
            dep_map.setdefault(d["blocked_task_id"], []).append(d["blocking_task_id"])
        for item in gantt_items:
            item["dependencies"] = dep_map.get(item["id"], [])

        # Add milestones
        for ms in milestones:
            gantt_items.append({
                "id": ms["milestone_id"], "type": "milestone",
                "title": ms["name"], "project": "",
                "start": ms.get("target_date", "")[:10],
                "end": ms.get("target_date", "")[:10],
                "status": ms.get("status", "pending"),
                "priority": "high", "item_type": "milestone",
                "progress": 100 if ms.get("status") == "reached" else 0,
                "dependencies": [],
            })

        gantt_items.sort(key=lambda x: x.get("start", ""))
        return {"items": gantt_items, "total_tasks": len(tasks), "total_milestones": len(milestones), "total_dependencies": len(deps)}

    @api_router.get("/orgs/{org_id}/gantt")
    async def get_org_gantt(org_id: str, request: Request):
        """Org-level Gantt — all tasks across all workspaces"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])

        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {"items": [], "total_tasks": 0}

        tasks = await db.project_tasks.find(
            {"workspace_id": {"$in": ws_ids}, "due_date": {"$ne": None}}, {"_id": 0}
        ).sort("due_date", 1).to_list(500)

        # Enrich
        if tasks:
            pids = list({t["project_id"] for t in tasks})
            projects = await db.projects.find({"project_id": {"$in": pids}}, {"_id": 0, "project_id": 1, "name": 1, "workspace_id": 1}).to_list(100)
            pmap = {p["project_id"]: p for p in projects}
            ws_map = {}
            async for ws in db.workspaces.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}):
                ws_map[ws["workspace_id"]] = ws["name"]
            for t in tasks:
                proj = pmap.get(t["project_id"], {})
                t["project_name"] = proj.get("name", "Unknown")
                t["workspace_name"] = ws_map.get(t.get("workspace_id") or proj.get("workspace_id", ""), "Unknown")

        gantt_items = [{
            "id": t["task_id"], "type": "task", "title": t["title"],
            "project": t.get("project_name", ""), "workspace": t.get("workspace_name", ""),
            "start": t.get("created_at", "")[:10], "end": t.get("due_date", "")[:10],
            "status": t.get("status", "todo"), "priority": t.get("priority", "medium"),
            "assignee": t.get("assignee_name"), "item_type": t.get("item_type", "task"),
            "progress": 100 if t.get("status") == "done" else 50 if t.get("status") in ("in_progress", "review") else 0,
        } for t in tasks]

        return {"items": gantt_items, "total_tasks": len(tasks)}

    # ======================================================
    # PLANNER / CALENDAR VIEW
    # ======================================================

    @api_router.get("/workspaces/{workspace_id}/planner")
    async def get_workspace_planner(workspace_id: str, request: Request, start: str = "", end: str = "", assignee_id: Optional[str] = None, project_id: Optional[str] = None):
        """Calendar/planner view — tasks by due date from both project_tasks and tasks collections"""
        await _authed_user(request, workspace_id)

        date_filter = {"$ne": None}
        if start:
            date_filter = {"$gte": start}
        if end:
            date_filter.setdefault("$lte", end) if isinstance(date_filter, dict) else None
            if isinstance(date_filter, dict) and "$gte" in date_filter:
                date_filter["$lte"] = end
            elif start == "":
                date_filter = {"$ne": None, "$lte": end}

        # Query project_tasks
        pt_query = {"workspace_id": workspace_id, "due_date": date_filter}
        if assignee_id:
            pt_query["assignee_id"] = assignee_id
        if project_id:
            pt_query["project_id"] = project_id
        project_tasks = await db.project_tasks.find(pt_query, {"_id": 0}).sort("due_date", 1).to_list(200)

        # Also query workspace-level tasks with due_date
        ws_query = {"workspace_id": workspace_id, "due_date": date_filter}
        if assignee_id:
            ws_query["assigned_to"] = assignee_id
        workspace_tasks = await db.tasks.find(ws_query, {"_id": 0}).sort("due_date", 1).to_list(200)

        # Normalize workspace tasks to match project_tasks shape
        for t in workspace_tasks:
            t.setdefault("assignee_name", t.get("assigned_to", ""))
            t.setdefault("assignee_id", t.get("assigned_to", ""))
            t.setdefault("source", "workspace")

        for t in project_tasks:
            t.setdefault("source", "project")

        all_tasks = project_tasks + workspace_tasks
        all_tasks.sort(key=lambda t: t.get("due_date", ""))

        # Group by date
        by_date = {}
        for t in all_tasks:
            d = t.get("due_date", "")[:10]
            by_date.setdefault(d, []).append(t)

        # Overdue check
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        overdue = [t for t in all_tasks if t.get("due_date", "")[:10] < today and t.get("status") not in ("done", "completed")]

        return {"tasks": all_tasks, "by_date": by_date, "overdue": overdue, "total": len(all_tasks)}

    @api_router.get("/orgs/{org_id}/planner")
    async def get_org_planner(org_id: str, request: Request, start: str = "", end: str = ""):
        """Org-level planner — all tasks across workspaces"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])

        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        query = {"workspace_id": {"$in": ws_ids}, "due_date": {"$ne": None}}
        if start:
            query["due_date"] = {"$gte": start}
        if end:
            query.setdefault("due_date", {})["$lte"] = end

        tasks = await db.project_tasks.find(query, {"_id": 0}).sort("due_date", 1).to_list(500)
        by_date = {}
        for t in tasks:
            d = t.get("due_date", "")[:10]
            by_date.setdefault(d, []).append(t)
        return {"tasks": tasks, "by_date": by_date, "total": len(tasks)}

    # ======================================================
    # PROJECT & TASK REPORTS
    # ======================================================

    @api_router.get("/workspaces/{workspace_id}/reports/summary")
    async def get_workspace_report_summary(workspace_id: str, request: Request):
        """Comprehensive workspace project & task report"""
        await _authed_user(request, workspace_id)

        projects = await db.projects.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(50)
        pids = [p["project_id"] for p in projects]
        all_tasks = await db.project_tasks.find({"project_id": {"$in": pids}}, {"_id": 0}).to_list(500) if pids else []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Status distribution
        status_dist = {}
        for t in all_tasks:
            s = t.get("status", "todo")
            status_dist[s] = status_dist.get(s, 0) + 1

        # Priority breakdown
        priority_dist = {}
        for t in all_tasks:
            p = t.get("priority", "medium")
            priority_dist[p] = priority_dist.get(p, 0) + 1

        # Item type breakdown
        type_dist = {}
        for t in all_tasks:
            it = t.get("item_type", "task")
            type_dist[it] = type_dist.get(it, 0) + 1

        # Overdue
        overdue = [t for t in all_tasks if t.get("due_date") and t["due_date"][:10] < today and t.get("status") != "done"]

        # Assignee workload
        workload = {}
        for t in all_tasks:
            a = t.get("assignee_name") or "Unassigned"
            workload.setdefault(a, {"total": 0, "done": 0, "in_progress": 0})
            workload[a]["total"] += 1
            if t.get("status") == "done":
                workload[a]["done"] += 1
            elif t.get("status") in ("in_progress", "review"):
                workload[a]["in_progress"] += 1

        # Completion rate
        total = len(all_tasks)
        done = sum(1 for t in all_tasks if t.get("status") == "done")
        completion_rate = round(done / max(total, 1) * 100, 1)

        # Per-project summary
        project_summaries = []
        for proj in projects:
            ptasks = [t for t in all_tasks if t["project_id"] == proj["project_id"]]
            p_done = sum(1 for t in ptasks if t.get("status") == "done")
            p_overdue = sum(1 for t in ptasks if t.get("due_date") and t["due_date"][:10] < today and t.get("status") != "done")
            project_summaries.append({
                "project_id": proj["project_id"], "name": proj["name"],
                "total_tasks": len(ptasks), "done": p_done,
                "completion_rate": round(p_done / max(len(ptasks), 1) * 100, 1),
                "overdue": p_overdue, "status": proj.get("status", "active"),
            })

        # Time logged
        time_pipeline = [
            {"$match": {"task_id": {"$in": [t["task_id"] for t in all_tasks]}}},
            {"$group": {"_id": None, "total_hours": {"$sum": "$hours"}}}
        ] if all_tasks else []
        time_result = await db.time_entries.aggregate(time_pipeline).to_list(1) if time_pipeline else []
        total_hours = time_result[0]["total_hours"] if time_result else 0

        return {
            "summary": {
                "total_projects": len(projects), "total_tasks": total,
                "tasks_done": done, "completion_rate": completion_rate,
                "overdue_count": len(overdue), "total_hours_logged": round(total_hours, 1),
            },
            "status_distribution": status_dist,
            "priority_distribution": priority_dist,
            "type_distribution": type_dist,
            "assignee_workload": workload,
            "project_summaries": project_summaries,
            "overdue_tasks": [{"task_id": t["task_id"], "title": t["title"], "due_date": t["due_date"], "project_id": t["project_id"]} for t in overdue[:20]],
        }

    @api_router.get("/orgs/{org_id}/reports/summary")
    async def get_org_report_summary(org_id: str, request: Request):
        """Org-level cross-workspace report"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])

        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {
                "summary": {
                    "total_workspaces": 0, "total_projects": 0, "total_tasks": 0,
                    "tasks_done": 0, "completion_rate": 0.0, "overdue_count": 0
                },
                "workspace_summaries": [],
                "team_utilization": {}
            }

        ws_map = {}
        async for ws in db.workspaces.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}):
            ws_map[ws["workspace_id"]] = ws["name"]

        projects = await db.projects.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0}).to_list(200)
        pids = [p["project_id"] for p in projects]
        all_tasks = await db.project_tasks.find({"project_id": {"$in": pids}}, {"_id": 0}).to_list(500) if pids else []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        total = len(all_tasks)
        done = sum(1 for t in all_tasks if t.get("status") == "done")
        overdue = sum(1 for t in all_tasks if t.get("due_date") and t["due_date"][:10] < today and t.get("status") != "done")

        # Per-workspace breakdown
        ws_summaries = []
        for wsid, wsname in ws_map.items():
            ws_projects = [p for p in projects if p.get("workspace_id") == wsid]
            ws_pids = [p["project_id"] for p in ws_projects]
            ws_tasks = [t for t in all_tasks if t.get("project_id") in ws_pids]
            ws_done = sum(1 for t in ws_tasks if t.get("status") == "done")
            ws_summaries.append({
                "workspace_id": wsid, "workspace_name": wsname,
                "projects": len(ws_projects), "tasks": len(ws_tasks),
                "done": ws_done, "completion_rate": round(ws_done / max(len(ws_tasks), 1) * 100, 1),
            })

        # Team utilization
        workload = {}
        for t in all_tasks:
            a = t.get("assignee_name") or "Unassigned"
            workload.setdefault(a, {"total": 0, "done": 0})
            workload[a]["total"] += 1
            if t.get("status") == "done":
                workload[a]["done"] += 1

        return {
            "summary": {
                "total_workspaces": len(ws_ids), "total_projects": len(projects),
                "total_tasks": total, "tasks_done": done,
                "completion_rate": round(done / max(total, 1) * 100, 1),
                "overdue_count": overdue,
            },
            "workspace_summaries": ws_summaries,
            "team_utilization": workload,
        }

    @api_router.get("/workspaces/{workspace_id}/reports/velocity")
    async def get_velocity_report(workspace_id: str, request: Request):
        """Sprint velocity report across completed sprints"""
        await _authed_user(request, workspace_id)
        pids = [p["project_id"] async for p in db.projects.find({"workspace_id": workspace_id}, {"project_id": 1, "_id": 0})]
        sprints = await db.sprints.find({"project_id": {"$in": pids}, "status": "completed"}, {"_id": 0}).sort("created_at", 1).to_list(20) if pids else []
        velocity_data = [{"sprint": s["name"], "velocity": s.get("velocity", 0), "completed_points": s.get("completed_points", 0)} for s in sprints]
        avg_velocity = round(sum(v["velocity"] for v in velocity_data) / max(len(velocity_data), 1), 1) if velocity_data else 0
        return {"sprints": velocity_data, "average_velocity": avg_velocity}
