"""Task Sessions - Independent AI task sessions with their own logs"""
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List


class CreateTaskSession(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    assigned_agent: str  # Agent key (claude, chatgpt, etc.) or nexus agent ID
    initial_prompt: str = Field(..., min_length=1, max_length=5000)
    due_date: Optional[str] = None  # ISO datetime string
    scheduled: bool = False  # If true, auto-run at due_date


class TaskMessage(BaseModel):
    content: str = Field(..., min_length=1)


def register_task_session_routes(api_router, db, get_current_user, AI_MODELS):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user
    
    @api_router.get("/workspaces/{workspace_id}/task-sessions")
    async def get_task_sessions(workspace_id: str, request: Request, status: Optional[str] = None):
        """Get all task sessions for a workspace"""
        user = await _authed_user(request, workspace_id)
        
        query = {"workspace_id": workspace_id}
        if status:
            query["status"] = status
        
        sessions = await db.task_sessions.find(
            query, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        
        return sessions
    
    @api_router.post("/workspaces/{workspace_id}/task-sessions")
    async def create_task_session(workspace_id: str, data: CreateTaskSession, request: Request):
        """Create a new task session"""
        user = await _authed_user(request, workspace_id)
        
        # Verify workspace exists
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        # Validate agent
        is_nexus_agent = data.assigned_agent.startswith("nxa_")
        agent_info = None
        
        if is_nexus_agent:
            nexus_agent = await db.nexus_agents.find_one(
                {"agent_id": data.assigned_agent, "workspace_id": workspace_id},
                {"_id": 0}
            )
            if not nexus_agent:
                raise HTTPException(400, "Nexus agent not found")
            agent_info = {
                "agent_id": nexus_agent["agent_id"],
                "name": nexus_agent["name"],
                "color": nexus_agent["color"],
                "avatar": nexus_agent["avatar"],
                "base_model": nexus_agent["base_model"],
                "is_nexus_agent": True,
            }
        else:
            if data.assigned_agent not in AI_MODELS:
                raise HTTPException(400, f"Invalid agent: {data.assigned_agent}")
            model = AI_MODELS[data.assigned_agent]
            agent_info = {
                "agent_id": data.assigned_agent,
                "name": model["name"],
                "color": model["color"],
                "avatar": model["avatar"],
                "base_model": data.assigned_agent,
                "is_nexus_agent": False,
            }
        
        session_id = f"ts_{uuid.uuid4().hex[:12]}"
        
        task_session = {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "created_by": user["user_id"],
            "title": data.title,
            "description": data.description or "",
            "agent": agent_info,
            "status": "queued" if data.scheduled and data.due_date else "active",
            "due_date": data.due_date,
            "scheduled": data.scheduled,
            "completed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message_count": 0,
        }
        
        await db.task_sessions.insert_one(task_session)
        
        # Create initial user message
        initial_message = {
            "message_id": f"tsm_{uuid.uuid4().hex[:12]}",
            "session_id": session_id,
            "sender_type": "human",
            "sender_id": user["user_id"],
            "sender_name": user.get("name", "User"),
            "content": data.initial_prompt,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.task_session_messages.insert_one(initial_message)
        
        # Update message count
        await db.task_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"message_count": 1}}
        )
        
        task_session.pop("_id", None)
        return task_session
    
    @api_router.get("/task-sessions/{session_id}")
    async def get_task_session(session_id: str, request: Request):
        """Get a specific task session"""
        await get_current_user(request)
        
        session = await db.task_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not session:
            raise HTTPException(404, "Task session not found")
        
        return session
    
    @api_router.get("/task-sessions/{session_id}/messages")
    async def get_task_session_messages(session_id: str, request: Request):
        """Get all messages in a task session"""
        await get_current_user(request)
        
        messages = await db.task_session_messages.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(200)
        
        return messages
    
    @api_router.post("/task-sessions/{session_id}/messages")
    async def send_task_message(session_id: str, data: TaskMessage, request: Request):
        """Send a message in a task session"""
        user = await get_current_user(request)
        
        session = await db.task_sessions.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(404, "Task session not found")
        
        if session["status"] != "active":
            raise HTTPException(400, "Task session is not active")
        
        # Create user message
        message = {
            "message_id": f"tsm_{uuid.uuid4().hex[:12]}",
            "session_id": session_id,
            "sender_type": "human",
            "sender_id": user["user_id"],
            "sender_name": user.get("name", "User"),
            "content": data.content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.task_session_messages.insert_one(message)
        
        # Update session
        await db.task_sessions.update_one(
            {"session_id": session_id},
            {
                "$inc": {"message_count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        message.pop("_id", None)
        return message
    
    @api_router.post("/task-sessions/{session_id}/run")
    async def run_task_agent(session_id: str, request: Request):
        """Trigger the AI agent to respond in the task session"""
        user = await get_current_user(request)
        
        session = await db.task_sessions.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(404, "Task session not found")
        
        if session["status"] != "active":
            raise HTTPException(400, "Task session is not active")
        
        # Import here to avoid circular imports
        import asyncio
        from server import run_task_session_agent
        
        asyncio.create_task(run_task_session_agent(
            session_id, 
            user["user_id"], 
            session["workspace_id"]
        ))
        
        return {"status": "started"}
    
    @api_router.put("/task-sessions/{session_id}/status")
    async def update_task_status(session_id: str, request: Request):
        """Toggle task session status (active/paused/completed)"""
        await get_current_user(request)
        
        session = await db.task_sessions.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(404, "Task session not found")
        
        current_status = session["status"]
        if current_status == "active":
            new_status = "paused"
        elif current_status == "paused":
            new_status = "active"
        else:
            new_status = "active"
        
        await db.task_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        updated = await db.task_sessions.find_one({"session_id": session_id}, {"_id": 0})
        return updated
    
    # complete_task_session moved below with enhanced implementation
    
    @api_router.delete("/task-sessions/{session_id}")
    async def delete_task_session(session_id: str, request: Request):
        """Delete a task session and all its messages"""
        await get_current_user(request)
        
        await db.task_session_messages.delete_many({"session_id": session_id})
        result = await db.task_sessions.delete_one({"session_id": session_id})
        
        if result.deleted_count == 0:
            raise HTTPException(404, "Task session not found")
        
        return {"message": "Task session deleted"}


    # Queue endpoint — all scheduled/queued tasks
    @api_router.get("/workspaces/{workspace_id}/task-queue")
    async def get_task_queue(workspace_id: str, request: Request):
        """Get all queued/scheduled task sessions"""
        await _authed_user(request, workspace_id)
        queued = await db.task_sessions.find(
            {"workspace_id": workspace_id, "status": {"$in": ["queued", "active"]}},
            {"_id": 0}
        ).sort("due_date", 1).to_list(100)
        completed = await db.task_sessions.find(
            {"workspace_id": workspace_id, "status": "completed"},
            {"_id": 0}
        ).sort("completed_at", -1).limit(20).to_list(20)
        return {"queued": queued, "completed": completed}

    # Update due date
    @api_router.put("/task-sessions/{session_id}/schedule")
    async def update_task_schedule(session_id: str, request: Request):
        """Update due date/time for a task session"""
        await get_current_user(request)
        body = await request.json()
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if "due_date" in body:
            updates["due_date"] = body["due_date"]
        if "scheduled" in body:
            updates["scheduled"] = body["scheduled"]
            if body["scheduled"] and body.get("due_date"):
                updates["status"] = "queued"
        await db.task_sessions.update_one(
            {"session_id": session_id}, {"$set": updates}
        )
        result = await db.task_sessions.find_one({"session_id": session_id}, {"_id": 0})
        return result

    # Mark task complete + send notification
    @api_router.put("/task-sessions/{session_id}/complete")
    async def complete_task_session(session_id: str, request: Request):
        """Mark task session as completed and notify user"""
        user = await get_current_user(request)
        now = datetime.now(timezone.utc).isoformat()
        session = await db.task_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Task session not found")
        await db.task_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "completed", "completed_at": now, "updated_at": now}}
        )
        # Create notification
        await db.notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": session.get("created_by", user["user_id"]),
            "type": "task_completed",
            "title": f"Task completed: {session.get('title', '')}",
            "message": f"{session.get('agent', {}).get('name', 'AI Agent')} has completed the task '{session.get('title', '')}'",
            "data": {"session_id": session_id, "workspace_id": session.get("workspace_id", "")},
            "read": False,
            "created_at": now,
        })
        result = await db.task_sessions.find_one({"session_id": session_id}, {"_id": 0})
        return result
