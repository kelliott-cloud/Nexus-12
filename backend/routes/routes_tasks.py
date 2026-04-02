import uuid
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import HTTPException, Request
from typing import Optional


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    assigned_to: str = ""
    assigned_type: str = "ai"
    channel_id: str = ""
    due_date: Optional[str] = None
    project_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_type: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None


def register_task_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    @api_router.get("/workspaces/{workspace_id}/tasks")
    async def get_tasks(workspace_id: str, request: Request, status: Optional[str] = None):
        user = await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if status:
            query["status"] = status
        tasks = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
        return tasks

    @api_router.get("/workspaces/{workspace_id}/all-tasks")
    async def get_all_tasks_grouped(workspace_id: str, request: Request):
        """Get all tasks (workspace + project) grouped by project"""
        user = await _authed_user(request, workspace_id)
        
        # Get workspace-level tasks
        ws_tasks = await db.tasks.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        
        # Get all projects in this workspace
        projects = await db.projects.find(
            {"workspace_id": workspace_id}, {"_id": 0, "project_id": 1, "name": 1, "status": 1}
        ).sort("name", 1).to_list(100)
        
        # Get all project tasks
        project_ids = [p["project_id"] for p in projects]
        project_tasks = []
        if project_ids:
            project_tasks = await db.project_tasks.find(
                {"project_id": {"$in": project_ids}},
                {"_id": 0}
            ).sort("created_at", -1).to_list(500)
        
        # Group project tasks by project_id
        project_task_map = {}
        for pt in project_tasks:
            pid = pt.get("project_id", "")
            if pid not in project_task_map:
                project_task_map[pid] = []
            project_task_map[pid].append(pt)
        
        # Build grouped response
        grouped = []
        # Unassigned workspace tasks
        if ws_tasks:
            grouped.append({
                "project_id": None,
                "project_name": "Workspace Tasks",
                "project_status": "active",
                "tasks": ws_tasks,
            })
        
        for p in projects:
            grouped.append({
                "project_id": p["project_id"],
                "project_name": p["name"],
                "project_status": p.get("status", "active"),
                "tasks": project_task_map.get(p["project_id"], []),
            })
        
        return {"groups": grouped, "total_tasks": len(ws_tasks) + len(project_tasks)}

    @api_router.post("/workspaces/{workspace_id}/tasks")
    async def create_task(workspace_id: str, data: TaskCreate, request: Request):
        user = await _authed_user(request, workspace_id)
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = {
            "task_id": task_id,
            "workspace_id": workspace_id,
            "channel_id": data.channel_id,
            "title": data.title,
            "description": data.description,
            "status": data.status,
            "priority": data.priority,
            "assigned_to": data.assigned_to,
            "assigned_type": data.assigned_type,
            "due_date": data.due_date,
            "project_id": data.project_id or "",
            "created_by": user["user_id"],
            "created_by_name": user.get("name", "Unknown"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.tasks.insert_one(task)
        result = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
        return result

    @api_router.post("/tasks/{task_id}/prompt-agent")
    async def prompt_agent_for_task(task_id: str, request: Request):
        """Prompt an AI agent assigned to a task to work on it"""
        user = await get_current_user(request)
        
        # Check workspace tasks first, then project tasks
        task = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
        if not task:
            task = await db.project_tasks.find_one({"task_id": task_id}, {"_id": 0})
        if not task:
            raise HTTPException(404, "Task not found")
        
        agent_key = task.get("assigned_to") or task.get("assignee_id", "")
        agent_name = task.get("assignee_name", agent_key)
        
        if not agent_key:
            raise HTTPException(400, "Task has no agent assigned")
        
        # Find a channel in the workspace to post the prompt
        workspace_id = task.get("workspace_id", "")
        if not workspace_id and task.get("project_id"):
            project = await db.projects.find_one({"project_id": task["project_id"]}, {"_id": 0, "workspace_id": 1})
            workspace_id = project.get("workspace_id", "") if project else ""
        
        channel = None
        if task.get("channel_id"):
            channel = await db.channels.find_one({"channel_id": task["channel_id"]}, {"_id": 0})
        if not channel:
            # Find first channel in workspace that has this agent
            channels = await db.channels.find(
                {"workspace_id": workspace_id, "ai_agents": agent_key},
                {"_id": 0}
            ).to_list(1)
            channel = channels[0] if channels else None
        
        if not channel:
            raise HTTPException(400, "No channel found with this agent. Create a channel with the agent first.")
        
        # Post a task prompt message in the channel
        prompt_content = f"**Task Assignment: {task.get('title', 'Untitled')}**\n\n"
        if task.get("description"):
            prompt_content += f"{task['description']}\n\n"
        prompt_content += f"Priority: {task.get('priority', 'medium')}\n"
        prompt_content += f"Status: {task.get('status', 'todo')}\n\n"
        prompt_content += f"@{agent_key} You have been assigned this task. Please review it and either:\n"
        prompt_content += "1. **Work on it** — start implementing/researching\n"
        prompt_content += "2. **Mark as On Hold** — if you need more information\n"
        prompt_content += "3. **Mark as Won't Do** — if the task is not feasible\n"
        prompt_content += "\nRespond with your plan of action."
        
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        await db.messages.insert_one({
            "message_id": msg_id,
            "channel_id": channel["channel_id"],
            "sender_type": "human",
            "sender_id": user["user_id"],
            "sender_name": user.get("name", "System"),
            "content": prompt_content,
            "mentions": {"mentioned_agents": [agent_key], "mention_everyone": False, "has_mentions": True},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Trigger collaboration so the agent responds
        import asyncio
        from server import run_ai_collaboration, active_collaborations
        if not active_collaborations.get(f"{channel['channel_id']}_running"):
            active_collaborations[f"{channel['channel_id']}_running"] = True
            asyncio.create_task(run_ai_collaboration(channel["channel_id"], user["user_id"]))
        
        return {
            "prompted": True,
            "task_id": task_id,
            "agent": agent_key,
            "channel_id": channel["channel_id"],
            "message_id": msg_id,
        }

    @api_router.put("/tasks/{task_id}")
    async def update_task(task_id: str, data: TaskUpdate, request: Request):
        await get_current_user(request)
        update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        if not update_fields:
            raise HTTPException(400, "No fields to update")
        await db.tasks.update_one({"task_id": task_id}, {"$set": update_fields})
        result = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
        if not result:
            raise HTTPException(404, "Task not found")
        # KG hook: fire on task completion
        if update_fields.get("status") == "completed" and result.get("workspace_id"):
            try:
                from knowledge_graph_hooks import on_task_completed
                import asyncio
                asyncio.create_task(on_task_completed(db, result, result["workspace_id"]))
            except Exception:
                pass
        return result

    @api_router.delete("/tasks/{task_id}")
    async def delete_task(task_id: str, request: Request):
        await get_current_user(request)
        result = await db.tasks.delete_one({"task_id": task_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Task not found")
        return {"message": "Task deleted"}

    @api_router.get("/workspaces/{workspace_id}/reports")
    async def get_reports(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)

        channels = await db.channels.find(
            {"workspace_id": workspace_id}, {"_id": 0, "channel_id": 1}
        ).to_list(100)
        channel_ids = [ch["channel_id"] for ch in channels]

        if not channel_ids:
            return {"agent_stats": {}, "task_stats": {"todo": 0, "in_progress": 0, "done": 0, "total": 0},
                    "total_messages": 0, "total_human_messages": 0, "total_ai_messages": 0,
                    "channels_count": 0, "recent_activity": []}

        messages = await db.messages.find(
            {"channel_id": {"$in": channel_ids}},
            {"_id": 0, "sender_type": 1, "ai_model": 1, "content": 1, "sender_name": 1, "created_at": 1}
        ).sort("created_at", -1).limit(500).to_list(500)

        agent_stats = {}
        for m in messages:
            if m["sender_type"] == "ai":
                agent = m.get("ai_model", "unknown")
                if agent not in agent_stats:
                    agent_stats[agent] = {"messages": 0, "code_blocks": 0, "total_chars": 0}
                agent_stats[agent]["messages"] += 1
                agent_stats[agent]["total_chars"] += len(m.get("content", ""))
                if "```" in m.get("content", ""):
                    agent_stats[agent]["code_blocks"] += m["content"].count("```") // 2

        tasks = await db.tasks.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(500)
        task_stats = {"todo": 0, "in_progress": 0, "done": 0, "total": len(tasks)}
        for t in tasks:
            s = t.get("status", "todo")
            if s in task_stats:
                task_stats[s] += 1

        recent = sorted(messages, key=lambda m: m.get("created_at", ""), reverse=True)[:20]

        return {
            "agent_stats": agent_stats,
            "task_stats": task_stats,
            "total_messages": len(messages),
            "total_human_messages": len([m for m in messages if m["sender_type"] == "human"]),
            "total_ai_messages": len([m for m in messages if m["sender_type"] == "ai"]),
            "channels_count": len(channel_ids),
            "recent_activity": recent
        }
