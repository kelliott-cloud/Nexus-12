"""PLM Phases 2-5 — Sprints, Dependencies, Milestones, Portfolios, Time Tracking, Automation, Custom Fields"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)


# ============ Models ============

class SprintCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = ""
    start_date: str = ""
    end_date: str = ""

class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None  # planning, active, completed

class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1)
    target_date: str = ""
    description: str = ""

class DependencyCreate(BaseModel):
    blocked_task_id: str
    blocking_task_id: str
    dependency_type: str = "finish_to_start"  # finish_to_start, start_to_start, finish_to_finish

class ProgramCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""

class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""

class TimeEntryCreate(BaseModel):
    task_id: str
    hours: float = Field(..., gt=0, le=24)
    description: str = ""
    date: str = ""

class AutomationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1)
    trigger_event: str  # task.status_changed, task.assigned, task.due_soon, task.overdue
    conditions: dict = {}  # {field: value} to match
    actions: List[dict] = []  # [{type: "set_field", field: "priority", value: "high"}]
    enabled: bool = True

class CustomFieldCreate(BaseModel):
    name: str = Field(..., min_length=1)
    field_type: str = "text"  # text, number, date, dropdown, checkbox, url
    options: List[str] = []  # For dropdown type
    required: bool = False
    default_value: Optional[str] = None



def register_plm_advanced_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ======================================================
    # PHASE 2 — Sprints, Dependencies, Milestones
    # ======================================================

    # ============ Sprints ============

    @api_router.post("/projects/{project_id}/sprints")
    async def create_sprint(project_id: str, data: SprintCreate, request: Request):
        user = await get_current_user(request)
        sprint_id = f"spr_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        sprint = {
            "sprint_id": sprint_id, "project_id": project_id,
            "name": data.name, "goal": data.goal,
            "start_date": data.start_date, "end_date": data.end_date,
            "status": "planning",  # planning, active, completed
            "velocity": 0, "completed_points": 0,
            "created_by": user["user_id"], "created_at": now,
        }
        await db.sprints.insert_one(sprint)
        return {k: v for k, v in sprint.items() if k != "_id"}

    @api_router.get("/projects/{project_id}/sprints")
    async def list_sprints(project_id: str, request: Request):
        await get_current_user(request)
        sprints = await db.sprints.find({"project_id": project_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        for s in sprints:
            s["task_count"] = await db.project_tasks.count_documents({"sprint_id": s["sprint_id"]})
            s["tasks_done"] = await db.project_tasks.count_documents({"sprint_id": s["sprint_id"], "status": "done"})
            pipeline = [{"$match": {"sprint_id": s["sprint_id"]}}, {"$group": {"_id": None, "total_points": {"$sum": {"$ifNull": ["$story_points", 0]}}}}]
            pts = await db.project_tasks.aggregate(pipeline).to_list(1)
            s["total_points"] = pts[0]["total_points"] if pts else 0
        return {"sprints": sprints}

    @api_router.put("/sprints/{sprint_id}")
    async def update_sprint(sprint_id: str, data: SprintUpdate, request: Request):
        await get_current_user(request)
        updates = {}
        if data.name is not None: updates["name"] = data.name
        if data.goal is not None: updates["goal"] = data.goal
        if data.start_date is not None: updates["start_date"] = data.start_date
        if data.end_date is not None: updates["end_date"] = data.end_date
        if data.status is not None:
            updates["status"] = data.status
            if data.status == "completed":
                done_pts = await db.project_tasks.aggregate([
                    {"$match": {"sprint_id": sprint_id, "status": "done"}},
                    {"$group": {"_id": None, "pts": {"$sum": {"$ifNull": ["$story_points", 0]}}}}
                ]).to_list(1)
                updates["completed_points"] = done_pts[0]["pts"] if done_pts else 0
                updates["velocity"] = updates["completed_points"]
        if updates:
            await db.sprints.update_one({"sprint_id": sprint_id}, {"$set": updates})
        return await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})

    @api_router.post("/sprints/{sprint_id}/tasks")
    async def assign_tasks_to_sprint(sprint_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        task_ids = body.get("task_ids") or []
        result = await db.project_tasks.update_many(
            {"task_id": {"$in": task_ids}}, {"$set": {"sprint_id": sprint_id}}
        )
        return {"assigned": result.modified_count}

    @api_router.get("/sprints/{sprint_id}/board")
    async def get_sprint_board(sprint_id: str, request: Request):
        await get_current_user(request)
        tasks = await db.project_tasks.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(100)
        board = {"todo": [], "in_progress": [], "review": [], "done": []}
        for t in tasks:
            board.get(t.get("status", "todo"), board["todo"]).append(t)
        sprint = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
        return {"sprint": sprint, "board": board}

    @api_router.get("/sprints/{sprint_id}/burndown")
    async def get_burndown(sprint_id: str, request: Request):
        await get_current_user(request)
        sprint = await db.sprints.find_one({"sprint_id": sprint_id}, {"_id": 0})
        if not sprint:
            raise HTTPException(404, "Sprint not found")
        tasks = await db.project_tasks.find({"sprint_id": sprint_id}, {"_id": 0, "story_points": 1, "status": 1, "updated_at": 1}).to_list(100)
        total_points = sum((t.get("story_points") or 0) for t in tasks)
        done_points = sum((t.get("story_points") or 0) for t in tasks if t.get("status") == "done")
        return {"sprint_id": sprint_id, "total_points": total_points, "done_points": done_points, "remaining_points": total_points - done_points, "tasks_total": len(tasks), "tasks_done": sum(1 for t in tasks if t.get("status") == "done")}

    @api_router.delete("/sprints/{sprint_id}")
    async def delete_sprint(sprint_id: str, request: Request):
        await get_current_user(request)
        await db.project_tasks.update_many({"sprint_id": sprint_id}, {"$unset": {"sprint_id": ""}})
        await db.sprints.delete_one({"sprint_id": sprint_id})
        return {"message": "Sprint deleted"}

    # ============ Dependencies ============

    @api_router.post("/tasks/dependencies")
    async def create_dependency(data: DependencyCreate, request: Request):
        await get_current_user(request)
        if data.blocked_task_id == data.blocking_task_id:
            raise HTTPException(400, "A task cannot depend on itself")
        existing = await db.task_dependencies.find_one({"blocked_task_id": data.blocked_task_id, "blocking_task_id": data.blocking_task_id})
        if existing:
            raise HTTPException(400, "Dependency already exists")
        dep_id = f"dep_{uuid.uuid4().hex[:12]}"
        dep = {
            "dependency_id": dep_id, "blocked_task_id": data.blocked_task_id,
            "blocking_task_id": data.blocking_task_id,
            "dependency_type": data.dependency_type, "created_at": now_iso(),
        }
        await db.task_dependencies.insert_one(dep)
        return {k: v for k, v in dep.items() if k != "_id"}

    @api_router.get("/tasks/{task_id}/dependencies")
    async def get_task_dependencies(task_id: str, request: Request):
        await get_current_user(request)
        blocks = await db.task_dependencies.find({"blocking_task_id": task_id}, {"_id": 0}).to_list(20)
        blocked_by = await db.task_dependencies.find({"blocked_task_id": task_id}, {"_id": 0}).to_list(20)
        return {"blocks": blocks, "blocked_by": blocked_by}

    @api_router.delete("/dependencies/{dep_id}")
    async def delete_dependency(dep_id: str, request: Request):
        await get_current_user(request)
        await db.task_dependencies.delete_one({"dependency_id": dep_id})
        return {"message": "Dependency removed"}

    # Milestones handled by routes_projects.py

    @api_router.put("/milestones/{ms_id}")
    async def update_milestone(ms_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {}
        for key in ["name", "description", "target_date", "status"]:
            if key in body: updates[key] = body[key]
        if updates:
            await db.milestones.update_one({"milestone_id": ms_id}, {"$set": updates})
        return await db.milestones.find_one({"milestone_id": ms_id}, {"_id": 0})

    @api_router.delete("/milestones/{ms_id}")
    async def delete_milestone(ms_id: str, request: Request):
        await get_current_user(request)
        await db.milestones.delete_one({"milestone_id": ms_id})
        return {"message": "Deleted"}

    # ============ Gantt Data ============

    @api_router.get("/projects/{project_id}/gantt")
    async def get_gantt_data(project_id: str, request: Request):
        await get_current_user(request)
        tasks = await db.project_tasks.find({"project_id": project_id, "due_date": {"$ne": None}}, {"_id": 0}).sort("due_date", 1).to_list(200)
        milestones = await db.milestones.find({"project_id": project_id}, {"_id": 0}).to_list(20)
        deps = []
        if tasks:
            tids = [t["task_id"] for t in tasks]
            deps = await db.task_dependencies.find({"blocked_task_id": {"$in": tids}}, {"_id": 0}).to_list(100)
        return {"tasks": tasks, "milestones": milestones, "dependencies": deps}

    @api_router.get("/workspaces/{workspace_id}/portfolio")
    async def get_workspace_portfolio(workspace_id: str, request: Request):
        """Get all projects rolled up into a portfolio view with aggregated Gantt data."""
        await _authed_user(request, workspace_id)
        projects = await db.projects.find(
            {"workspace_id": workspace_id, "is_deleted": {"$ne": True}},
            {"_id": 0}
        ).to_list(50)
        
        portfolio = []
        all_tasks = []
        all_milestones = []
        all_deps = []
        
        for proj in projects:
            pid = proj["project_id"]
            tasks = await db.project_tasks.find(
                {"project_id": pid, "is_deleted": {"$ne": True}},
                {"_id": 0}
            ).sort("due_date", 1).to_list(200)
            milestones = await db.milestones.find({"project_id": pid}, {"_id": 0}).to_list(20)
            
            done = sum(1 for t in tasks if t.get("status") == "done")
            portfolio.append({
                "project_id": pid,
                "name": proj.get("name", ""),
                "status": proj.get("status", "active"),
                "task_count": len(tasks),
                "tasks_done": done,
                "progress": round(done / max(len(tasks), 1) * 100),
                "milestone_count": len(milestones),
            })
            
            # Add project name to each task for the Gantt
            for t in tasks:
                t["project_name"] = proj.get("name", "")
                all_tasks.append(t)
            all_milestones.extend(milestones)
            
            # Get dependencies
            tids = [t["task_id"] for t in tasks]
            if tids:
                deps = await db.task_dependencies.find({"blocked_task_id": {"$in": tids}}, {"_id": 0}).to_list(100)
                all_deps.extend(deps)
        
        return {
            "projects": portfolio,
            "total_projects": len(portfolio),
            "total_tasks": len(all_tasks),
            "total_milestones": len(all_milestones),
            "gantt": {
                "tasks": all_tasks,
                "milestones": all_milestones,
                "dependencies": all_deps,
            },
        }

    # ======================================================
    # PHASE 3 — Portfolio & Program Management
    # ======================================================

    @api_router.post("/workspaces/{workspace_id}/programs")
    async def create_program(workspace_id: str, data: ProgramCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        prog_id = f"prog_{uuid.uuid4().hex[:12]}"
        program = {
            "program_id": prog_id, "workspace_id": workspace_id,
            "name": data.name, "description": data.description,
            "project_ids": [], "status": "active",
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.programs.insert_one(program)
        return {k: v for k, v in program.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/programs")
    async def list_programs(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        programs = await db.programs.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(20)
        for p in programs:
            p["project_count"] = len(p.get("project_ids") or [])
        return {"programs": programs}

    @api_router.post("/programs/{program_id}/projects")
    async def add_project_to_program(program_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        project_id = body.get("project_id")
        await db.programs.update_one({"program_id": program_id}, {"$addToSet": {"project_ids": project_id}})
        return await db.programs.find_one({"program_id": program_id}, {"_id": 0})

    @api_router.delete("/programs/{program_id}")
    async def delete_program(program_id: str, request: Request):
        await get_current_user(request)
        await db.programs.delete_one({"program_id": program_id})
        return {"message": "Deleted"}

    # Portfolios
    @api_router.post("/portfolios")
    async def create_portfolio(data: PortfolioCreate, request: Request):
        user = await get_current_user(request)
        pf_id = f"pf_{uuid.uuid4().hex[:12]}"
        portfolio = {
            "portfolio_id": pf_id, "name": data.name, "description": data.description,
            "program_ids": [], "status": "active",
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.portfolios.insert_one(portfolio)
        return {k: v for k, v in portfolio.items() if k != "_id"}

    @api_router.get("/portfolios")
    async def list_portfolios(request: Request):
        await get_current_user(request)
        items = await db.portfolios.find({}, {"_id": 0}).to_list(20)
        return {"portfolios": items}

    @api_router.post("/portfolios/{portfolio_id}/programs")
    async def add_program_to_portfolio(portfolio_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        await db.portfolios.update_one({"portfolio_id": portfolio_id}, {"$addToSet": {"program_ids": body.get("program_id")}})
        return await db.portfolios.find_one({"portfolio_id": portfolio_id}, {"_id": 0})

    @api_router.get("/portfolios/{portfolio_id}/health")
    async def get_portfolio_health(portfolio_id: str, request: Request):
        await get_current_user(request)
        pf = await db.portfolios.find_one({"portfolio_id": portfolio_id}, {"_id": 0})
        if not pf:
            raise HTTPException(404, "Portfolio not found")
        programs = await db.programs.find({"program_id": {"$in": pf.get("program_ids") or []}}, {"_id": 0}).to_list(20)
        all_project_ids = []
        for p in programs:
            all_project_ids.extend(p.get("project_ids") or [])
        total_tasks = await db.project_tasks.count_documents({"project_id": {"$in": all_project_ids}}) if all_project_ids else 0
        done_tasks = await db.project_tasks.count_documents({"project_id": {"$in": all_project_ids}, "status": "done"}) if all_project_ids else 0
        overdue = await db.project_tasks.count_documents({"project_id": {"$in": all_project_ids}, "due_date": {"$lt": now_iso()[:10]}, "status": {"$ne": "done"}}) if all_project_ids else 0
        return {
            "portfolio": pf["name"], "programs": len(programs), "projects": len(all_project_ids),
            "total_tasks": total_tasks, "done_tasks": done_tasks, "overdue_tasks": overdue,
            "completion_rate": round(done_tasks / max(total_tasks, 1) * 100, 1),
            "health": "green" if overdue == 0 else "yellow" if overdue < 5 else "red",
        }

    # ======================================================
    # PHASE 4 — Time Tracking & Automation
    # ======================================================

    @api_router.post("/time-entries")
    async def log_time(data: TimeEntryCreate, request: Request):
        user = await get_current_user(request)
        entry_id = f"te_{uuid.uuid4().hex[:12]}"
        entry = {
            "entry_id": entry_id, "task_id": data.task_id,
            "user_id": user["user_id"], "user_name": user.get("name", ""),
            "hours": data.hours, "description": data.description,
            "date": data.date or now_iso()[:10],
            "created_at": now_iso(),
        }
        await db.time_entries.insert_one(entry)
        return {k: v for k, v in entry.items() if k != "_id"}

    @api_router.get("/tasks/{task_id}/time-entries")
    async def get_task_time(task_id: str, request: Request):
        await get_current_user(request)
        entries = await db.time_entries.find({"task_id": task_id}, {"_id": 0}).sort("date", -1).to_list(50)
        total = sum(e.get("hours", 0) for e in entries)
        return {"entries": entries, "total_hours": round(total, 2)}

    @api_router.get("/my-timesheet")
    async def get_my_timesheet(request: Request, start_date: str = "", end_date: str = ""):
        user = await get_current_user(request)
        query = {"user_id": user["user_id"]}
        if start_date:
            query["date"] = {"$gte": start_date}
        if end_date:
            query.setdefault("date", {})["$lte"] = end_date
        entries = await db.time_entries.find(query, {"_id": 0}).sort("date", -1).to_list(200)
        total = sum(e.get("hours", 0) for e in entries)
        by_day = {}
        for e in entries:
            d = e.get("date", "")
            by_day[d] = by_day.get(d, 0) + e.get("hours", 0)
        return {"entries": entries, "total_hours": round(total, 2), "by_day": by_day}

    @api_router.delete("/time-entries/{entry_id}")
    async def delete_time_entry(entry_id: str, request: Request):
        await get_current_user(request)
        await db.time_entries.delete_one({"entry_id": entry_id})
        return {"message": "Deleted"}

    # ============ Automation Rules ============

    @api_router.post("/projects/{project_id}/automations")
    async def create_automation(project_id: str, data: AutomationRuleCreate, request: Request):
        user = await get_current_user(request)
        rule_id = f"auto_{uuid.uuid4().hex[:12]}"
        rule = {
            "rule_id": rule_id, "project_id": project_id,
            "name": data.name, "trigger_event": data.trigger_event,
            "conditions": data.conditions, "actions": data.actions,
            "enabled": data.enabled, "execution_count": 0,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.automation_rules.insert_one(rule)
        return {k: v for k, v in rule.items() if k != "_id"}

    @api_router.get("/projects/{project_id}/automations")
    async def list_automations(project_id: str, request: Request):
        await get_current_user(request)
        rules = await db.automation_rules.find({"project_id": project_id}, {"_id": 0}).to_list(20)
        return {"automations": rules}

    @api_router.put("/automations/{rule_id}")
    async def update_automation(rule_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {}
        for k in ["name", "trigger_event", "conditions", "actions", "enabled"]:
            if k in body: updates[k] = body[k]
        if updates:
            await db.automation_rules.update_one({"rule_id": rule_id}, {"$set": updates})
        return await db.automation_rules.find_one({"rule_id": rule_id}, {"_id": 0})

    @api_router.delete("/automations/{rule_id}")
    async def delete_automation(rule_id: str, request: Request):
        await get_current_user(request)
        await db.automation_rules.delete_one({"rule_id": rule_id})
        return {"message": "Deleted"}

    @api_router.get("/automations/triggers")
    async def get_automation_triggers(request: Request):
        await get_current_user(request)
        return {"triggers": [
            {"key": "task.status_changed", "name": "Task Status Changed", "fields": ["old_status", "new_status"]},
            {"key": "task.assigned", "name": "Task Assigned", "fields": ["assignee_id"]},
            {"key": "task.due_soon", "name": "Task Due Soon (24h)", "fields": ["due_date"]},
            {"key": "task.overdue", "name": "Task Overdue", "fields": ["due_date"]},
            {"key": "task.created", "name": "Task Created", "fields": ["item_type", "priority"]},
            {"key": "sprint.completed", "name": "Sprint Completed", "fields": ["sprint_id"]},
            {"key": "milestone.reached", "name": "Milestone Reached", "fields": ["milestone_id"]},
        ], "actions": [
            {"key": "set_field", "name": "Set Field Value", "params": ["field", "value"]},
            {"key": "assign_to", "name": "Assign To User", "params": ["user_id"]},
            {"key": "add_label", "name": "Add Label", "params": ["label"]},
            {"key": "send_notification", "name": "Send Notification", "params": ["message"]},
            {"key": "move_to_sprint", "name": "Move to Sprint", "params": ["sprint_id"]},
            {"key": "change_priority", "name": "Change Priority", "params": ["priority"]},
        ]}

    # ============ Recurring Tasks ============

    @api_router.post("/projects/{project_id}/recurring-tasks")
    async def create_recurring_task(project_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        rec_id = f"rec_{uuid.uuid4().hex[:12]}"
        recurring = {
            "recurring_id": rec_id, "project_id": project_id,
            "template": body.get("template") or {},  # task fields to copy
            "interval_days": body.get("interval_days", 7),
            "next_creation": body.get("start_date", now_iso()[:10]),
            "enabled": True, "created_count": 0,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.recurring_tasks.insert_one(recurring)
        return {k: v for k, v in recurring.items() if k != "_id"}

    @api_router.get("/projects/{project_id}/recurring-tasks")
    async def list_recurring_tasks(project_id: str, request: Request):
        await get_current_user(request)
        items = await db.recurring_tasks.find({"project_id": project_id}, {"_id": 0}).to_list(20)
        return {"recurring_tasks": items}

    # ======================================================
    # PHASE 5 — Custom Fields & API
    # ======================================================

    @api_router.post("/projects/{project_id}/custom-fields")
    async def create_custom_field(project_id: str, data: CustomFieldCreate, request: Request):
        user = await get_current_user(request)
        valid_types = ["text", "number", "date", "dropdown", "checkbox", "url"]
        if data.field_type not in valid_types:
            raise HTTPException(400, f"Invalid type. Use: {valid_types}")
        field_id = f"cf_{uuid.uuid4().hex[:12]}"
        field = {
            "field_id": field_id, "project_id": project_id,
            "name": data.name, "field_type": data.field_type,
            "options": data.options if data.field_type == "dropdown" else [],
            "required": data.required, "default_value": data.default_value,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.custom_fields.insert_one(field)
        return {k: v for k, v in field.items() if k != "_id"}

    @api_router.get("/projects/{project_id}/custom-fields")
    async def list_custom_fields(project_id: str, request: Request):
        await get_current_user(request)
        fields = await db.custom_fields.find({"project_id": project_id}, {"_id": 0}).to_list(30)
        return {"fields": fields}

    @api_router.delete("/custom-fields/{field_id}")
    async def delete_custom_field(field_id: str, request: Request):
        await get_current_user(request)
        await db.custom_fields.delete_one({"field_id": field_id})
        return {"message": "Deleted"}

    @api_router.post("/tasks/{task_id}/custom-values")
    async def set_custom_field_value(task_id: str, request: Request):
        """Set a custom field value on a task"""
        await get_current_user(request)
        body = await request.json()
        field_id = body.get("field_id")
        value = body.get("value")
        await db.project_tasks.update_one(
            {"task_id": task_id},
            {"$set": {f"custom_fields.{field_id}": value, "updated_at": now_iso()}}
        )
        return {"task_id": task_id, "field_id": field_id, "value": value}

    @api_router.get("/tasks/{task_id}/custom-values")
    async def get_custom_field_values(task_id: str, request: Request):
        await get_current_user(request)
        task = await db.project_tasks.find_one({"task_id": task_id}, {"_id": 0, "custom_fields": 1})
        return task.get("custom_fields") or {} if task else {}

    # ============ Custom Field Templates ============

    @api_router.post("/projects/{project_id}/field-templates")
    async def save_field_template(project_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        tpl_id = f"cft_{uuid.uuid4().hex[:12]}"
        fields = await db.custom_fields.find({"project_id": project_id}, {"_id": 0}).to_list(30)
        template = {
            "template_id": tpl_id, "name": body.get("name", "Default"),
            "project_id": project_id, "fields": fields, "created_at": now_iso(),
        }
        await db.field_templates.insert_one(template)
        return {k: v for k, v in template.items() if k != "_id"}

    @api_router.get("/field-templates")
    async def list_field_templates(request: Request):
        await get_current_user(request)
        items = await db.field_templates.find({}, {"_id": 0}).to_list(20)
        return {"templates": items}

    @api_router.post("/projects/{project_id}/apply-template")
    async def apply_field_template(project_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        tpl = await db.field_templates.find_one({"template_id": body.get("template_id")}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")
        for field in tpl.get("fields") or []:
            field["field_id"] = f"cf_{uuid.uuid4().hex[:12]}"
            field["project_id"] = project_id
            field["created_at"] = now_iso()
            await db.custom_fields.insert_one(field)
        return {"applied": len(tpl.get("fields") or [])}

    # ============ PLM Config ============

    @api_router.get("/plm-config")
    async def get_plm_config(request: Request):
        await get_current_user(request)
        return {
            "sprint_statuses": ["planning", "active", "completed"],
            "dependency_types": ["finish_to_start", "start_to_start", "finish_to_finish", "start_to_finish"],
            "milestone_statuses": ["pending", "in_progress", "reached", "missed"],
            "custom_field_types": ["text", "number", "date", "dropdown", "checkbox", "url"],
            "portfolio_health_levels": ["green", "yellow", "red"],
        }
