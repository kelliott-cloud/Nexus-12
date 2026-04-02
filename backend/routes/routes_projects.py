"""Projects module - workspace-level project management with tasks and artifacts"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request


# ============ Models ============

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    linked_channels: List[str] = []

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    linked_channels: Optional[List[str]] = None

class ProjectTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    item_type: str = "task"  # task, story, bug, epic, subtask
    assignee_type: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string
    parent_task_id: Optional[str] = None  # For subtasks
    labels: List[str] = []
    story_points: Optional[int] = None

class ProjectTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    item_type: Optional[str] = None
    assignee_type: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None
    labels: Optional[List[str]] = None
    story_points: Optional[int] = None

class BulkTaskUpdate(BaseModel):
    task_ids: List[str]
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_type: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None

class BulkTaskDelete(BaseModel):
    task_ids: List[str]


VALID_STATUSES = ["active", "on_hold", "completed", "archived"]
VALID_TASK_STATUSES = ["todo", "in_progress", "review", "done"]
VALID_PRIORITIES = ["low", "medium", "high", "critical"]
VALID_ITEM_TYPES = ["task", "story", "bug", "epic", "subtask"]


from nexus_utils import safe_regex

def register_project_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Projects CRUD ============

    @api_router.get("/workspaces/{workspace_id}/projects")
    async def list_projects(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        projects = await db.projects.find(
            {"workspace_id": workspace_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)

        if projects:
            # Batch count tasks for all projects in one aggregation
            project_ids = [p["project_id"] for p in projects]
            pipeline = [
                {"$match": {"project_id": {"$in": project_ids}}},
                {"$group": {
                    "_id": "$project_id",
                    "task_count": {"$sum": 1},
                    "tasks_done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}}
                }}
            ]
            counts = {c["_id"]: c async for c in db.project_tasks.aggregate(pipeline)}
            for proj in projects:
                c = counts.get(proj["project_id"], {})
                proj["task_count"] = c.get("task_count", 0)
                proj["tasks_done"] = c.get("tasks_done", 0)
                proj["progress"] = round(proj["tasks_done"] / proj["task_count"] * 100) if proj["task_count"] > 0 else 0
        return projects

    @api_router.post("/workspaces/{workspace_id}/projects")
    async def create_project(workspace_id: str, data: ProjectCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        
        # Dedup check — block duplicate project creation
        from dedup_engine import check_duplicate_project
        dup = await check_duplicate_project(db, workspace_id, data.name.strip(), data.description.strip())
        if dup and dup.get("is_duplicate"):
            raise HTTPException(409, f"Duplicate project detected: '{dup['existing_name']}' (ID: {dup['existing_id']}, similarity: {dup['similarity']:.0%}). Use the existing project instead.")
        
        now = datetime.now(timezone.utc).isoformat()
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        project = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "name": data.name.strip(),
            "description": data.description.strip(),
            "status": "active",
            "linked_channels": data.linked_channels,
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.projects.insert_one(project)
        result = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        if not result:
            raise HTTPException(500, "Created but could not retrieve")
        result["task_count"] = 0
        result["tasks_done"] = 0
        return result

    @api_router.get("/projects/{project_id}")
    async def get_project(project_id: str, request: Request):
        await get_current_user(request)
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        if not project:
            raise HTTPException(404, "Project not found")
        total = await db.project_tasks.count_documents({"project_id": project_id})
        done = await db.project_tasks.count_documents({"project_id": project_id, "status": "done"})
        project["task_count"] = total
        project["tasks_done"] = done
        project["progress"] = round(done / total * 100) if total > 0 else 0
        return project

    @api_router.put("/projects/{project_id}")
    async def update_project(project_id: str, data: ProjectUpdate, request: Request):
        await get_current_user(request)
        project = await db.projects.find_one({"project_id": project_id})
        if not project:
            raise HTTPException(404, "Project not found")

        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.name is not None:
            updates["name"] = data.name.strip()
        if data.description is not None:
            updates["description"] = data.description.strip()
        if data.status is not None:
            if data.status not in VALID_STATUSES:
                raise HTTPException(400, f"Invalid status. Use: {', '.join(VALID_STATUSES)}")
            updates["status"] = data.status
        if data.linked_channels is not None:
            updates["linked_channels"] = data.linked_channels

        await db.projects.update_one({"project_id": project_id}, {"$set": updates})
        result = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        total = await db.project_tasks.count_documents({"project_id": project_id})
        done = await db.project_tasks.count_documents({"project_id": project_id, "status": "done"})
        result["task_count"] = total
        result["tasks_done"] = done
        return result

    @api_router.delete("/projects/{project_id}")
    async def delete_project(project_id: str, request: Request):
        await get_current_user(request)
        project = await db.projects.find_one({"project_id": project_id})
        if not project:
            raise HTTPException(404, "Project not found")
        await db.project_tasks.delete_many({"project_id": project_id})
        await db.projects.delete_one({"project_id": project_id})
        return {"message": "Project deleted"}

    # ============ Project Tasks CRUD ============

    @api_router.get("/projects/{project_id}/tasks")
    async def list_project_tasks(project_id: str, request: Request):
        await get_current_user(request)
        tasks = await db.project_tasks.find(
            {"project_id": project_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        
        # Add subtask progress to each task
        task_ids = [t["task_id"] for t in tasks]
        if task_ids:
            sub_pipeline = [
                {"$match": {"parent_task_id": {"$in": task_ids}}},
                {"$group": {
                    "_id": "$parent_task_id",
                    "subtask_count": {"$sum": 1},
                    "subtasks_done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}}
                }}
            ]
            sub_counts = {c["_id"]: c async for c in db.project_tasks.aggregate(sub_pipeline)}
            for t in tasks:
                sc = sub_counts.get(t["task_id"], {})
                t["subtask_total"] = sc.get("subtask_count", 0)
                t["subtasks_done"] = sc.get("subtasks_done", 0)
                t["progress"] = round(sc.get("subtasks_done", 0) / sc.get("subtask_count", 1) * 100) if sc.get("subtask_count", 0) > 0 else (100 if t.get("status") == "done" else 0)
        
        return tasks

    @api_router.post("/projects/{project_id}/tasks")
    async def create_project_task(project_id: str, data: ProjectTaskCreate, request: Request):
        user = await get_current_user(request)
        project = await db.projects.find_one({"project_id": project_id})
        if not project:
            raise HTTPException(404, "Project not found")

        # Dedup check — block duplicate task creation
        from dedup_engine import check_duplicate_task
        dup = await check_duplicate_task(db, project_id, data.title.strip(), data.description.strip())
        if dup and dup.get("is_duplicate"):
            raise HTTPException(409, f"Duplicate task detected: '{dup['existing_name']}' (similarity: {dup['similarity']:.0%}). Use the existing task instead.")

        if data.status not in VALID_TASK_STATUSES:
            raise HTTPException(400, f"Invalid status. Use: {', '.join(VALID_TASK_STATUSES)}")
        if data.priority not in VALID_PRIORITIES:
            raise HTTPException(400, f"Invalid priority. Use: {', '.join(VALID_PRIORITIES)}")

        now = datetime.now(timezone.utc).isoformat()
        task_id = f"ptask_{uuid.uuid4().hex[:12]}"
        item_type = data.item_type if data.item_type in VALID_ITEM_TYPES else "task"
        task = {
            "task_id": task_id,
            "project_id": project_id,
            "workspace_id": project["workspace_id"],
            "title": data.title.strip(),
            "description": data.description.strip(),
            "status": data.status,
            "priority": data.priority,
            "item_type": item_type,
            "assignee_type": data.assignee_type,
            "assignee_id": data.assignee_id,
            "assignee_name": data.assignee_name,
            "due_date": data.due_date,
            "parent_task_id": data.parent_task_id,
            "labels": data.labels,
            "story_points": data.story_points,
            "subtask_count": 0,
            "comment_count": 0,
            "attachment_count": 0,
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.project_tasks.insert_one(task)

        # If subtask, increment parent's subtask count
        if data.parent_task_id:
            await db.project_tasks.update_one({"task_id": data.parent_task_id}, {"$inc": {"subtask_count": 1}})

        # Log activity
        await db.task_activity.insert_one({
            "activity_id": f"ta_{uuid.uuid4().hex[:8]}",
            "task_id": task_id, "project_id": project_id,
            "action": "created", "actor_id": user["user_id"], "actor_name": user.get("name", ""),
            "details": {"item_type": item_type, "priority": data.priority},
            "timestamp": now,
        })

        return await db.project_tasks.find_one({"task_id": task_id}, {"_id": 0})

    @api_router.put("/projects/{project_id}/tasks/{task_id}")
    async def update_project_task(project_id: str, task_id: str, data: ProjectTaskUpdate, request: Request):
        user = await get_current_user(request)
        task = await db.project_tasks.find_one({"task_id": task_id, "project_id": project_id})
        if not task:
            raise HTTPException(404, "Task not found")

        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        changes = []
        if data.title is not None:
            updates["title"] = data.title.strip()
            if task.get("title") != data.title.strip():
                changes.append("title changed")
        if data.description is not None:
            updates["description"] = data.description.strip()
        if data.status is not None:
            if data.status not in VALID_TASK_STATUSES:
                raise HTTPException(400, f"Invalid status. Use: {', '.join(VALID_TASK_STATUSES)}")
            if task.get("status") != data.status:
                changes.append(f"status: {task.get('status')} → {data.status}")
            updates["status"] = data.status
        if data.priority is not None:
            if data.priority not in VALID_PRIORITIES:
                raise HTTPException(400, f"Invalid priority. Use: {', '.join(VALID_PRIORITIES)}")
            if task.get("priority") != data.priority:
                changes.append(f"priority: {task.get('priority')} → {data.priority}")
            updates["priority"] = data.priority
        if data.item_type is not None:
            updates["item_type"] = data.item_type
        if data.due_date is not None:
            updates["due_date"] = data.due_date
            changes.append(f"due date set: {data.due_date}")
        if data.labels is not None:
            updates["labels"] = data.labels
        if data.story_points is not None:
            updates["story_points"] = data.story_points
        if data.assignee_type is not None:
            updates["assignee_type"] = data.assignee_type
        if data.assignee_id is not None:
            updates["assignee_id"] = data.assignee_id
        if data.assignee_name is not None:
            updates["assignee_name"] = data.assignee_name

        await db.project_tasks.update_one({"task_id": task_id}, {"$set": updates})

        # Log activity
        if changes:
            await db.task_activity.insert_one({
                "activity_id": f"ta_{uuid.uuid4().hex[:8]}",
                "task_id": task_id, "project_id": project_id,
                "action": "updated", "actor_id": user["user_id"], "actor_name": user.get("name", ""),
                "details": {"changes": changes},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return await db.project_tasks.find_one({"task_id": task_id}, {"_id": 0})

    @api_router.delete("/projects/{project_id}/tasks/{task_id}")
    async def delete_project_task(project_id: str, task_id: str, request: Request):
        await get_current_user(request)
        result = await db.project_tasks.delete_one({"task_id": task_id, "project_id": project_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Task not found")
        return {"message": "Task deleted"}

    # ============ Bulk Task Operations ============

    @api_router.post("/projects/{project_id}/tasks/bulk-update")
    async def bulk_update_tasks(project_id: str, data: BulkTaskUpdate, request: Request):
        """Update multiple tasks at once (status, priority, assignee)"""
        await get_current_user(request)
        if not data.task_ids:
            raise HTTPException(400, "No task IDs provided")
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.status is not None:
            if data.status not in VALID_TASK_STATUSES:
                raise HTTPException(400, f"Invalid status. Use: {', '.join(VALID_TASK_STATUSES)}")
            updates["status"] = data.status
        if data.priority is not None:
            if data.priority not in VALID_PRIORITIES:
                raise HTTPException(400, f"Invalid priority. Use: {', '.join(VALID_PRIORITIES)}")
            updates["priority"] = data.priority
        if data.assignee_type is not None:
            updates["assignee_type"] = data.assignee_type
        if data.assignee_id is not None:
            updates["assignee_id"] = data.assignee_id
        if data.assignee_name is not None:
            updates["assignee_name"] = data.assignee_name
        result = await db.project_tasks.update_many(
            {"task_id": {"$in": data.task_ids}, "project_id": project_id},
            {"$set": updates}
        )
        return {"updated": result.modified_count}

    @api_router.post("/projects/{project_id}/tasks/bulk-delete")
    async def bulk_delete_tasks(project_id: str, data: BulkTaskDelete, request: Request):
        """Delete multiple tasks at once"""
        await get_current_user(request)
        if not data.task_ids:
            raise HTTPException(400, "No task IDs provided")
        result = await db.project_tasks.delete_many(
            {"task_id": {"$in": data.task_ids}, "project_id": project_id}
        )
        return {"deleted": result.deleted_count}

    # ============ Enhanced Search & Filter ============

    @api_router.get("/workspaces/{workspace_id}/tasks/search")
    async def search_workspace_tasks(
        workspace_id: str, request: Request,
        q: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[str] = None,
        project_id: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        limit: int = 50, offset: int = 0,
    ):
        """Search and filter tasks across all projects in a workspace"""
        await get_current_user(request)
        query = {"workspace_id": workspace_id}
        if q:
            query["$or"] = [
                {"title": {"$regex": safe_regex(q), "$options": "i"}},
                {"description": {"$regex": safe_regex(q), "$options": "i"}},
            ]
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if assignee_id:
            query["assignee_id"] = assignee_id
        if project_id:
            query["project_id"] = project_id

        sort_dir = -1 if sort_order == "desc" else 1
        valid_sorts = ["updated_at", "created_at", "priority", "status", "title"]
        if sort_by not in valid_sorts:
            sort_by = "updated_at"

        tasks = await db.project_tasks.find(query, {"_id": 0}).sort(sort_by, sort_dir).skip(offset).limit(limit).to_list(limit)
        total = await db.project_tasks.count_documents(query)

        # Enrich with project names
        if tasks:
            pids = list({t["project_id"] for t in tasks})
            projects = await db.projects.find({"project_id": {"$in": pids}}, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)
            pmap = {p["project_id"]: p["name"] for p in projects}
            for t in tasks:
                t["project_name"] = pmap.get(t["project_id"], "Unknown")

        return {"tasks": tasks, "total": total}

    @api_router.get("/workspaces/{workspace_id}/assignees")
    async def get_workspace_assignees(workspace_id: str, request: Request):
        """Get all unique assignees in a workspace for filter dropdowns"""
        await _authed_user(request, workspace_id)
        pipeline = [
            {"$match": {"workspace_id": workspace_id, "assignee_id": {"$ne": None}}},
            {"$group": {"_id": {"id": "$assignee_id", "name": "$assignee_name", "type": "$assignee_type"}}},
        ]
        results = []
        async for doc in db.project_tasks.aggregate(pipeline):
            g = doc["_id"]
            if g["id"]:
                results.append({"assignee_id": g["id"], "assignee_name": g["name"] or g["id"], "assignee_type": g["type"] or "unknown"})
        return results

    # ============ Helpers ============

    @api_router.get("/channels/{channel_id}/projects")
    async def get_channel_projects(channel_id: str, request: Request):
        """Get all projects linked to a specific channel"""
        await get_current_user(request)
        projects = await db.projects.find(
            {"linked_channels": channel_id},
            {"_id": 0}
        ).to_list(50)
        if projects:
            project_ids = [p["project_id"] for p in projects]
            pipeline = [
                {"$match": {"project_id": {"$in": project_ids}}},
                {"$group": {
                    "_id": "$project_id",
                    "task_count": {"$sum": 1},
                    "tasks_done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}}
                }}
            ]
            counts = {c["_id"]: c async for c in db.project_tasks.aggregate(pipeline)}
            for proj in projects:
                c = counts.get(proj["project_id"], {})
                proj["task_count"] = c.get("task_count", 0)
                proj["tasks_done"] = c.get("tasks_done", 0)
        return projects


    # ============ Task Comments ============

    @api_router.post("/tasks/{task_id}/comments")
    async def add_task_comment(task_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        content = body.get("content", "").strip()
        if not content:
            raise HTTPException(400, "Comment content required")
        comment_id = f"tc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        comment = {
            "comment_id": comment_id, "task_id": task_id,
            "content": content, "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "created_at": now,
        }
        await db.task_comments.insert_one(comment)
        await db.project_tasks.update_one({"task_id": task_id}, {"$inc": {"comment_count": 1}})
        return {k: v for k, v in comment.items() if k != "_id"}

    @api_router.get("/tasks/{task_id}/comments")
    async def list_task_comments(task_id: str, request: Request):
        await get_current_user(request)
        comments = await db.task_comments.find({"task_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
        return comments

    @api_router.delete("/task-comments/{comment_id}")
    async def delete_task_comment(comment_id: str, request: Request):
        await get_current_user(request)
        comment = await db.task_comments.find_one({"comment_id": comment_id})
        if not comment:
            raise HTTPException(404, "Comment not found")
        await db.task_comments.delete_one({"comment_id": comment_id})
        await db.project_tasks.update_one({"task_id": comment["task_id"]}, {"$inc": {"comment_count": -1}})
        return {"message": "Deleted"}

    # ============ Task Attachments ============

    @api_router.post("/tasks/{task_id}/attachments")
    async def add_task_attachment(task_id: str, request: Request):
        user = await get_current_user(request)
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file provided")
        import base64
        content = await file.read()
        att_id = f"tatt_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        attachment = {
            "attachment_id": att_id, "task_id": task_id,
            "filename": file.filename or "attachment",
            "mime_type": file.content_type or "application/octet-stream",
            "size": len(content),
            "data": base64.b64encode(content).decode("utf-8"),
            "uploaded_by": user["user_id"],
            "uploaded_at": now,
        }
        await db.task_attachments.insert_one(attachment)
        await db.project_tasks.update_one({"task_id": task_id}, {"$inc": {"attachment_count": 1}})
        return {k: v for k, v in attachment.items() if k not in ("_id", "data")}

    @api_router.get("/tasks/{task_id}/attachments")
    async def list_task_attachments(task_id: str, request: Request):
        await get_current_user(request)
        atts = await db.task_attachments.find({"task_id": task_id}, {"_id": 0, "data": 0}).to_list(50)
        return atts

    @api_router.get("/task-attachments/{attachment_id}")
    async def get_task_attachment(attachment_id: str, request: Request):
        await get_current_user(request)
        att = await db.task_attachments.find_one({"attachment_id": attachment_id}, {"_id": 0})
        if not att:
            raise HTTPException(404, "Attachment not found")
        return att

    @api_router.delete("/task-attachments/{attachment_id}")
    async def delete_task_attachment(attachment_id: str, request: Request):
        await get_current_user(request)
        att = await db.task_attachments.find_one({"attachment_id": attachment_id})
        if not att:
            raise HTTPException(404, "Attachment not found")
        await db.task_attachments.delete_one({"attachment_id": attachment_id})
        await db.project_tasks.update_one({"task_id": att["task_id"]}, {"$inc": {"attachment_count": -1}})
        return {"message": "Deleted"}

    # ============ Subtasks ============

    @api_router.get("/tasks/{task_id}/subtasks")
    async def list_subtasks(task_id: str, request: Request):
        await get_current_user(request)
        subtasks = await db.project_tasks.find({"parent_task_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(50)
        return subtasks

    # ============ Task Activity Log ============

    @api_router.get("/tasks/{task_id}/activity")
    async def get_task_activity(task_id: str, request: Request):
        await get_current_user(request)
        activity = await db.task_activity.find({"task_id": task_id}, {"_id": 0}).sort("timestamp", -1).to_list(50)
        return activity

    # ============ My Tasks (All tasks assigned to current user) ============

    @api_router.get("/my-tasks")
    async def get_my_tasks(request: Request, status: Optional[str] = None, priority: Optional[str] = None, sort_by: str = "due_date"):
        user = await get_current_user(request)
        query = {"assignee_id": user["user_id"]}
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        sort_field = "due_date" if sort_by == "due_date" else "updated_at" if sort_by == "updated" else "priority"
        sort_dir = 1 if sort_by == "due_date" else -1
        tasks = await db.project_tasks.find(query, {"_id": 0}).sort(sort_field, sort_dir).to_list(100)
        # Enrich with project names
        if tasks:
            pids = list({t["project_id"] for t in tasks})
            projects = await db.projects.find({"project_id": {"$in": pids}}, {"_id": 0, "project_id": 1, "name": 1, "workspace_id": 1}).to_list(50)
            pmap = {p["project_id"]: p for p in projects}
            for t in tasks:
                proj = pmap.get(t["project_id"], {})
                t["project_name"] = proj.get("name", "Unknown")
                t["workspace_id"] = proj.get("workspace_id", t.get("workspace_id", ""))
        return {"tasks": tasks, "total": len(tasks)}

    # ============ Item Types Config ============

    @api_router.get("/project-config")
    async def get_project_config(request: Request):
        await get_current_user(request)
        return {
            "item_types": [
                {"key": "task", "name": "Task", "color": "blue", "description": "A unit of work"},
                {"key": "story", "name": "Story", "color": "green", "description": "User story or feature"},
                {"key": "bug", "name": "Bug", "color": "red", "description": "Defect to fix"},
                {"key": "epic", "name": "Epic", "color": "purple", "description": "Large feature composed of stories/tasks"},
                {"key": "subtask", "name": "Subtask", "color": "gray", "description": "Sub-item of a parent task"},
            ],
            "statuses": VALID_TASK_STATUSES,
            "priorities": VALID_PRIORITIES,
        }


    # ============ Milestones ============

    @api_router.get("/projects/{project_id}/milestones")
    async def list_milestones(project_id: str, request: Request):
        await get_current_user(request)
        milestones = await db.milestones.find(
            {"project_id": project_id}, {"_id": 0}
        ).sort("due_date", 1).to_list(100)
        # Add progress for each milestone
        for m in milestones:
            linked = await db.task_relationships.count_documents(
                {"milestone_id": m["milestone_id"]}
            )
            done = 0
            if linked > 0:
                task_ids = [r["task_id"] async for r in db.task_relationships.find(
                    {"milestone_id": m["milestone_id"]}, {"_id": 0, "task_id": 1}
                )]
                if task_ids:
                    done = await db.project_tasks.count_documents(
                        {"task_id": {"$in": task_ids}, "status": "done"}
                    )
            m["linked_tasks"] = linked
            m["done_tasks"] = done
            m["progress"] = round((done / linked * 100) if linked > 0 else 0)
        return {"milestones": milestones}

    @api_router.post("/projects/{project_id}/milestones")
    async def create_milestone(project_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        name = body.get("name", "").strip()
        if not name:
            raise HTTPException(400, "Milestone name required")
        
        # Dedup check
        from dedup_engine import check_duplicate_milestone
        dup = await check_duplicate_milestone(db, project_id, name)
        if dup and dup.get("is_duplicate"):
            raise HTTPException(409, f"Duplicate milestone: '{dup['existing_name']}' (similarity: {dup['similarity']:.0%})")
        
        now = datetime.now(timezone.utc).isoformat()
        milestone_id = f"ms_{uuid.uuid4().hex[:12]}"
        milestone = {
            "milestone_id": milestone_id,
            "project_id": project_id,
            "name": name,
            "description": body.get("description", ""),
            "due_date": body.get("due_date"),
            "status": body.get("status", "open"),  # open, in_progress, completed
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.milestones.insert_one(milestone)
        return {k: v for k, v in milestone.items() if k != "_id"}

    @api_router.put("/projects/{project_id}/milestones/{milestone_id}")
    async def update_milestone(project_id: str, milestone_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for key in ["name", "description", "due_date", "status"]:
            if key in body:
                updates[key] = body[key]
        await db.milestones.update_one(
            {"milestone_id": milestone_id, "project_id": project_id},
            {"$set": updates}
        )
        result = await db.milestones.find_one(
            {"milestone_id": milestone_id}, {"_id": 0}
        )
        if not result:
            raise HTTPException(404, "Milestone not found")
        return result

    @api_router.delete("/projects/{project_id}/milestones/{milestone_id}")
    async def delete_milestone(project_id: str, milestone_id: str, request: Request):
        await get_current_user(request)
        await db.milestones.delete_one({"milestone_id": milestone_id, "project_id": project_id})
        await db.task_relationships.delete_many({"milestone_id": milestone_id})
        return {"deleted": True}

    # ============ Task Relationships (parent-child, blocks, depends_on, milestone) ============

    @api_router.get("/tasks/{task_id}/relationships")
    async def get_task_relationships(task_id: str, request: Request):
        await get_current_user(request)
        rels = await db.task_relationships.find(
            {"$or": [{"task_id": task_id}, {"target_task_id": task_id}]},
            {"_id": 0}
        ).to_list(100)
        # Enrich with task titles
        all_ids = set()
        for r in rels:
            all_ids.add(r.get("task_id", ""))
            all_ids.add(r.get("target_task_id", ""))
        all_ids.discard("")
        all_ids.discard(task_id)
        task_names = {}
        if all_ids:
            tasks = await db.project_tasks.find(
                {"task_id": {"$in": list(all_ids)}},
                {"_id": 0, "task_id": 1, "title": 1, "status": 1}
            ).to_list(100)
            task_names = {t["task_id"]: t for t in tasks}
        # Also check workspace tasks
        ws_tasks = await db.tasks.find(
            {"task_id": {"$in": list(all_ids)}},
            {"_id": 0, "task_id": 1, "title": 1, "status": 1}
        ).to_list(100)
        for t in ws_tasks:
            task_names[t["task_id"]] = t
        # Categorize
        parents = []
        children = []
        blocks = []
        blocked_by = []
        depends_on = []
        dependents = []
        milestone_links = []
        for r in rels:
            rel_type = r.get("relationship_type", "")
            info = {**r}
            other_id = r["target_task_id"] if r["task_id"] == task_id else r["task_id"]
            info["other_task"] = task_names.get(other_id, {"task_id": other_id, "title": "Unknown"})
            if rel_type == "parent" and r["task_id"] == task_id:
                children.append(info)
            elif rel_type == "parent" and r["target_task_id"] == task_id:
                parents.append(info)
            elif rel_type == "blocks" and r["task_id"] == task_id:
                blocks.append(info)
            elif rel_type == "blocks" and r["target_task_id"] == task_id:
                blocked_by.append(info)
            elif rel_type == "depends_on" and r["task_id"] == task_id:
                depends_on.append(info)
            elif rel_type == "depends_on" and r["target_task_id"] == task_id:
                dependents.append(info)
            elif rel_type == "milestone":
                milestone_links.append(info)
        return {
            "parents": parents, "children": children,
            "blocks": blocks, "blocked_by": blocked_by,
            "depends_on": depends_on, "dependents": dependents,
            "milestone_links": milestone_links,
        }

    @api_router.post("/tasks/{task_id}/relationships")
    async def create_task_relationship(task_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        rel_type = body.get("type", "")  # parent, blocks, depends_on, milestone
        target_id = body.get("target_id", "")  # target task_id or milestone_id
        if not rel_type or not target_id:
            raise HTTPException(400, "type and target_id required")
        if rel_type not in ("parent", "blocks", "depends_on", "milestone", "relates_to"):
            raise HTTPException(400, "type must be: parent, blocks, depends_on, milestone, relates_to")
        # Prevent self-reference
        if target_id == task_id:
            raise HTTPException(400, "Cannot link a task to itself")
        # Check for duplicate
        existing = await db.task_relationships.find_one({
            "task_id": task_id, "target_task_id": target_id, "relationship_type": rel_type
        })
        if existing:
            raise HTTPException(409, "Relationship already exists")
        now = datetime.now(timezone.utc).isoformat()
        rel_id = f"trel_{uuid.uuid4().hex[:12]}"
        rel = {
            "relationship_id": rel_id,
            "task_id": task_id,
            "target_task_id": target_id if rel_type != "milestone" else "",
            "milestone_id": target_id if rel_type == "milestone" else "",
            "relationship_type": rel_type,
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.task_relationships.insert_one(rel)
        return {k: v for k, v in rel.items() if k != "_id"}

    @api_router.delete("/relationships/{rel_id}")
    async def delete_relationship(rel_id: str, request: Request):
        await get_current_user(request)
        result = await db.task_relationships.delete_one({"relationship_id": rel_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Relationship not found")
        return {"deleted": True}

    # ============ Task Detail (single task with all enrichments) ============

    @api_router.get("/tasks/{task_id}/detail")
    async def get_task_detail(task_id: str, request: Request):
        await get_current_user(request)
        # Check project_tasks first, then workspace tasks
        task = await db.project_tasks.find_one({"task_id": task_id}, {"_id": 0})
        source = "project"
        if not task:
            task = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
            source = "workspace"
        if not task:
            raise HTTPException(404, "Task not found")
        # Get relationships
        rels = await db.task_relationships.find(
            {"$or": [{"task_id": task_id}, {"target_task_id": task_id}]},
            {"_id": 0}
        ).to_list(50)
        # Get milestone if linked
        milestone = None
        ms_rels = [r for r in rels if r.get("relationship_type") == "milestone"]
        if ms_rels:
            ms_id = ms_rels[0].get("milestone_id", "")
            if ms_id:
                milestone = await db.milestones.find_one({"milestone_id": ms_id}, {"_id": 0})
        # Get activity
        activity = await db.task_activity.find(
            {"task_id": task_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        # Get subtasks if any
        subtasks = []
        if source == "project":
            subtasks = await db.project_tasks.find(
                {"parent_task_id": task_id}, {"_id": 0, "task_id": 1, "title": 1, "status": 1, "priority": 1}
            ).to_list(50)
        # Enrich related task titles
        related_ids = set()
        for r in rels:
            if r.get("target_task_id"):
                related_ids.add(r["target_task_id"])
            if r.get("task_id") and r["task_id"] != task_id:
                related_ids.add(r["task_id"])
        related_tasks = {}
        if related_ids:
            pt = await db.project_tasks.find(
                {"task_id": {"$in": list(related_ids)}},
                {"_id": 0, "task_id": 1, "title": 1, "status": 1}
            ).to_list(50)
            for t in pt:
                related_tasks[t["task_id"]] = t
            wt = await db.tasks.find(
                {"task_id": {"$in": list(related_ids)}},
                {"_id": 0, "task_id": 1, "title": 1, "status": 1}
            ).to_list(50)
            for t in wt:
                related_tasks[t["task_id"]] = t
        return {
            "task": task,
            "source": source,
            "relationships": rels,
            "related_tasks": related_tasks,
            "milestone": milestone,
            "activity": activity,
            "subtasks": subtasks,
        }


    # ============ Project Templates ============

    PROJECT_TEMPLATES = [
        {
            "template_id": "tpl_web_app",
            "name": "Web Application",
            "description": "Full-stack web app with frontend, backend, and deployment",
            "milestones": [
                {"name": "Planning & Design", "offset_days": 14},
                {"name": "MVP Development", "offset_days": 42},
                {"name": "Testing & QA", "offset_days": 56},
                {"name": "Launch", "offset_days": 70},
            ],
            "tasks": [
                {"title": "Define requirements", "priority": "high", "milestone_idx": 0},
                {"title": "Design database schema", "priority": "high", "milestone_idx": 0},
                {"title": "Create wireframes", "priority": "medium", "milestone_idx": 0},
                {"title": "Setup project scaffolding", "priority": "high", "milestone_idx": 1},
                {"title": "Implement authentication", "priority": "critical", "milestone_idx": 1},
                {"title": "Build API endpoints", "priority": "high", "milestone_idx": 1},
                {"title": "Develop frontend UI", "priority": "high", "milestone_idx": 1},
                {"title": "Write unit tests", "priority": "medium", "milestone_idx": 2},
                {"title": "Integration testing", "priority": "high", "milestone_idx": 2},
                {"title": "Performance optimization", "priority": "medium", "milestone_idx": 2},
                {"title": "Deploy to production", "priority": "critical", "milestone_idx": 3},
                {"title": "Monitor and iterate", "priority": "medium", "milestone_idx": 3},
            ],
        },
        {
            "template_id": "tpl_ai_agent",
            "name": "AI Agent Project",
            "description": "Build and deploy an AI agent with training and evaluation",
            "milestones": [
                {"name": "Research & Planning", "offset_days": 7},
                {"name": "Agent Development", "offset_days": 28},
                {"name": "Evaluation & Testing", "offset_days": 42},
                {"name": "Deployment", "offset_days": 56},
            ],
            "tasks": [
                {"title": "Define agent capabilities", "priority": "high", "milestone_idx": 0},
                {"title": "Research existing solutions", "priority": "medium", "milestone_idx": 0},
                {"title": "Design agent architecture", "priority": "high", "milestone_idx": 0},
                {"title": "Implement core agent logic", "priority": "critical", "milestone_idx": 1},
                {"title": "Build tool integrations", "priority": "high", "milestone_idx": 1},
                {"title": "Create prompt templates", "priority": "medium", "milestone_idx": 1},
                {"title": "Setup evaluation framework", "priority": "high", "milestone_idx": 2},
                {"title": "Run benchmark tests", "priority": "high", "milestone_idx": 2},
                {"title": "Iterate on performance", "priority": "medium", "milestone_idx": 2},
                {"title": "Deploy agent to production", "priority": "critical", "milestone_idx": 3},
                {"title": "Setup monitoring", "priority": "high", "milestone_idx": 3},
            ],
        },
        {
            "template_id": "tpl_sprint",
            "name": "Sprint Planning",
            "description": "Two-week sprint with standard ceremonies",
            "milestones": [
                {"name": "Sprint Start", "offset_days": 0},
                {"name": "Mid-Sprint Check", "offset_days": 7},
                {"name": "Sprint Review", "offset_days": 14},
            ],
            "tasks": [
                {"title": "Sprint planning meeting", "priority": "high", "milestone_idx": 0},
                {"title": "Backlog grooming", "priority": "medium", "milestone_idx": 0},
                {"title": "Daily standups", "priority": "low", "milestone_idx": 1},
                {"title": "Code reviews", "priority": "medium", "milestone_idx": 1},
                {"title": "Sprint demo", "priority": "high", "milestone_idx": 2},
                {"title": "Retrospective", "priority": "medium", "milestone_idx": 2},
            ],
        },
    ]

    @api_router.get("/project-templates")
    async def get_project_templates(request: Request):
        await get_current_user(request)
        return {"templates": [{"template_id": t["template_id"], "name": t["name"], "description": t["description"],
                               "milestone_count": len(t["milestones"]), "task_count": len(t["tasks"])} for t in PROJECT_TEMPLATES]}

    @api_router.post("/workspaces/{workspace_id}/projects/from-template")
    async def create_project_from_template(workspace_id: str, request: Request):
        """Create a project with pre-built milestones and tasks from a template"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        template_id = body.get("template_id", "")
        project_name = body.get("name", "")
        template = next((t for t in PROJECT_TEMPLATES if t["template_id"] == template_id), None)
        if not template:
            raise HTTPException(404, "Template not found")
        if not project_name:
            project_name = template["name"]
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        # Create project
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        await db.projects.insert_one({
            "project_id": project_id, "workspace_id": workspace_id,
            "name": project_name, "description": template["description"],
            "status": "active", "linked_channels": [],
            "created_by": user["user_id"], "created_at": now_str, "updated_at": now_str,
        })
        # Create milestones
        milestone_ids = []
        for ms in template["milestones"]:
            ms_id = f"ms_{uuid.uuid4().hex[:12]}"
            due = (now + timedelta(days=ms["offset_days"])).strftime("%Y-%m-%d")
            await db.milestones.insert_one({
                "milestone_id": ms_id, "project_id": project_id,
                "name": ms["name"], "description": "", "due_date": due,
                "status": "open", "created_by": user["user_id"],
                "created_at": now_str, "updated_at": now_str,
            })
            milestone_ids.append(ms_id)
        # Create tasks and link to milestones
        for task_def in template["tasks"]:
            task_id = f"ptask_{uuid.uuid4().hex[:12]}"
            await db.project_tasks.insert_one({
                "task_id": task_id, "project_id": project_id, "workspace_id": workspace_id,
                "title": task_def["title"], "description": "", "status": "todo",
                "priority": task_def["priority"], "item_type": "task",
                "assignee_type": None, "assignee_id": None, "assignee_name": None,
                "due_date": None, "parent_task_id": None, "labels": [],
                "story_points": None, "subtask_count": 0, "comment_count": 0,
                "attachment_count": 0, "created_by": user["user_id"],
                "created_at": now_str, "updated_at": now_str,
            })
            # Link to milestone
            ms_idx = task_def.get("milestone_idx", 0)
            if ms_idx < len(milestone_ids):
                await db.task_relationships.insert_one({
                    "relationship_id": f"trel_{uuid.uuid4().hex[:12]}",
                    "task_id": task_id, "target_task_id": "",
                    "milestone_id": milestone_ids[ms_idx],
                    "relationship_type": "milestone",
                    "created_by": user["user_id"], "created_at": now_str,
                })
        result = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        return {**result, "template_applied": template_id, "milestones_created": len(milestone_ids), "tasks_created": len(template["tasks"])}

    # ============ Code Repo Analytics ============

    @api_router.get("/workspaces/{workspace_id}/code-repo/analytics")
    async def get_repo_analytics(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        file_count = await db.repo_files.count_documents({"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "is_folder": False})
        folder_count = await db.repo_files.count_documents({"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "is_folder": True})
        commit_count = await db.repo_commits.count_documents({"workspace_id": workspace_id})
        branch_count = await db.repo_branches.count_documents({"workspace_id": workspace_id})
        review_count = await db.repo_reviews.count_documents({"workspace_id": workspace_id})
        # Language breakdown
        pipeline = [
            {"$match": {"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "is_folder": False}},
            {"$group": {"_id": "$language", "count": {"$sum": 1}, "total_size": {"$sum": "$size"}}},
            {"$sort": {"count": -1}},
        ]
        lang_stats = [{"language": d["_id"], "count": d["count"], "size": d.get("total_size", 0)} async for d in db.repo_files.aggregate(pipeline)]
        # Recent commits
        recent_commits = await db.repo_commits.find(
            {"workspace_id": workspace_id},
            {"_id": 0, "commit_id": 1, "file_path": 1, "action": 1, "author_name": 1, "message": 1, "created_at": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        # Top contributors
        contrib_pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {"_id": "$author_name", "commits": {"$sum": 1}}},
            {"$sort": {"commits": -1}}, {"$limit": 10},
        ]
        contributors = [{"name": d["_id"], "commits": d["commits"]} async for d in db.repo_commits.aggregate(contrib_pipeline)]
        return {
            "file_count": file_count, "folder_count": folder_count,
            "commit_count": commit_count, "branch_count": branch_count,
            "review_count": review_count,
            "language_stats": lang_stats,
            "recent_commits": recent_commits,
            "contributors": contributors,
        }

    # ============ Milestone Deadline Notifications ============

    @api_router.get("/workspaces/{workspace_id}/milestone-alerts")
    async def get_milestone_alerts(workspace_id: str, request: Request):
        """Get milestones approaching deadline in the next 7 days"""
        await _authed_user(request, workspace_id)
        projects = await db.projects.find(
            {"workspace_id": workspace_id}, {"_id": 0, "project_id": 1, "name": 1}
        ).to_list(100)
        project_ids = [p["project_id"] for p in projects]
        project_map = {p["project_id"]: p["name"] for p in projects}
        if not project_ids:
            return {"alerts": []}
        now = datetime.now(timezone.utc)
        week_later = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")
        milestones = await db.milestones.find(
            {"project_id": {"$in": project_ids}, "status": {"$ne": "completed"},
             "due_date": {"$lte": week_later}},
            {"_id": 0}
        ).sort("due_date", 1).to_list(50)
        alerts = []
        for m in milestones:
            due = m.get("due_date", "")
            overdue = due < today if due else False
            alerts.append({
                **m,
                "project_name": project_map.get(m["project_id"], ""),
                "overdue": overdue,
                "days_until": max(0, (datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc) - now).days) if due else None,
            })
        return {"alerts": alerts}
