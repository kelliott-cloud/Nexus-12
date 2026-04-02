"""Notification system for AI agent completion and other events"""
import uuid
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List


class NotificationType:
    AI_RESPONSE = "ai_response"
    TASK_COMPLETED = "task_completed"
    MEMBER_JOINED = "member_joined"
    FILE_UPLOADED = "file_uploaded"
    INVITATION = "invitation"


def register_notification_routes(api_router, db, get_current_user):
    
    @api_router.get("/notifications")
    async def get_notifications(
        request: Request,
        unread_only: bool = False,
        limit: int = 50
    ):
        """Get user's notifications"""
        user = await get_current_user(request)
        
        query = {"user_id": user["user_id"]}
        if unread_only:
            query["read"] = False
        
        notifications = await db.notifications.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        unread_count = await db.notifications.count_documents({
            "user_id": user["user_id"],
            "read": False
        })
        
        return {
            "notifications": notifications,
            "unread_count": unread_count
        }
    
    @api_router.put("/notifications/{notification_id}/read")
    async def mark_notification_read(notification_id: str, request: Request):
        """Mark a notification as read"""
        user = await get_current_user(request)
        
        result = await db.notifications.update_one(
            {"notification_id": notification_id, "user_id": user["user_id"]},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "Notification not found")
        
        return {"status": "read"}
    
    @api_router.put("/notifications/read-all")
    async def mark_all_notifications_read(request: Request):
        """Mark all notifications as read"""
        user = await get_current_user(request)
        
        result = await db.notifications.update_many(
            {"user_id": user["user_id"], "read": False},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {"status": "updated", "count": result.modified_count}
    
    @api_router.delete("/notifications/{notification_id}")
    async def delete_notification(notification_id: str, request: Request):
        """Delete a notification"""
        user = await get_current_user(request)
        
        result = await db.notifications.delete_one({
            "notification_id": notification_id,
            "user_id": user["user_id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(404, "Notification not found")
        
        return {"status": "deleted"}
    
    @api_router.delete("/notifications")
    async def clear_notifications(request: Request, older_than_days: int = 30):
        """Clear old notifications"""
        user = await get_current_user(request)
        
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        
        result = await db.notifications.delete_many({
            "user_id": user["user_id"],
            "created_at": {"$lt": cutoff}
        })
        
        return {"status": "cleared", "count": result.deleted_count}
    
    @api_router.get("/notifications/settings")
    async def get_notification_settings(request: Request):
        """Get user's notification preferences"""
        user = await get_current_user(request)
        
        settings = await db.notification_settings.find_one(
            {"user_id": user["user_id"]},
            {"_id": 0}
        )
        
        # Return defaults if no settings exist
        if not settings:
            settings = {
                "user_id": user["user_id"],
                "ai_responses": True,
                "task_updates": True,
                "member_activity": True,
                "file_uploads": True,
                "sound_enabled": True,
                "browser_notifications": False
            }
        
        return settings
    
    @api_router.put("/notifications/settings")
    async def update_notification_settings(request: Request):
        """Update notification preferences"""
        user = await get_current_user(request)
        data = await request.json()
        
        allowed_fields = [
            "ai_responses", "task_updates", "member_activity",
            "file_uploads", "sound_enabled", "browser_notifications"
        ]
        
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.notification_settings.update_one(
            {"user_id": user["user_id"]},
            {"$set": updates},
            upsert=True
        )
        
        return {"status": "updated"}


async def create_notification(
    db,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    workspace_id: str = None,
    channel_id: str = None,
    task_session_id: str = None,
    link: str = None,
    metadata: dict = None
):
    """Create a notification for a user"""
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "task_session_id": task_session_id,
        "link": link,
        "metadata": metadata or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification)
    return notification


async def notify_task_session_response(db, session_id: str, agent_name: str):
    """Notify user that AI agent has responded in task session"""
    session = await db.task_sessions.find_one({"session_id": session_id})
    if not session:
        return
    
    workspace = await db.workspaces.find_one({"workspace_id": session["workspace_id"]})
    workspace_name = workspace.get("name", "Workspace") if workspace else "Workspace"
    
    await create_notification(
        db,
        user_id=session["created_by"],
        notification_type=NotificationType.AI_RESPONSE,
        title=f"{agent_name} responded",
        message=f"New response in task: {session['title']}",
        workspace_id=session["workspace_id"],
        task_session_id=session_id,
        link=f"/workspace/{session['workspace_id']}?task={session_id}",
        metadata={
            "agent_name": agent_name,
            "task_title": session["title"],
            "workspace_name": workspace_name
        }
    )


async def notify_channel_response(db, channel_id: str, agent_name: str, user_ids: List[str]):
    """Notify users that AI agent has responded in channel"""
    channel = await db.channels.find_one({"channel_id": channel_id})
    if not channel:
        return
    
    workspace = await db.workspaces.find_one({"workspace_id": channel["workspace_id"]})
    workspace_name = workspace.get("name", "Workspace") if workspace else "Workspace"
    
    for user_id in user_ids:
        await create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.AI_RESPONSE,
            title=f"{agent_name} responded",
            message=f"New response in #{channel['name']}",
            workspace_id=channel["workspace_id"],
            channel_id=channel_id,
            link=f"/workspace/{channel['workspace_id']}?channel={channel_id}",
            metadata={
                "agent_name": agent_name,
                "channel_name": channel["name"],
                "workspace_name": workspace_name
            }
        )


async def notify_member_joined(db, workspace_id: str, new_member_name: str, admin_user_ids: List[str]):
    """Notify admins when a new member joins"""
    workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
    workspace_name = workspace.get("name", "Workspace") if workspace else "Workspace"
    
    for user_id in admin_user_ids:
        await create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.MEMBER_JOINED,
            title="New member joined",
            message=f"{new_member_name} joined {workspace_name}",
            workspace_id=workspace_id,
            link=f"/workspace/{workspace_id}/settings/members",
            metadata={
                "member_name": new_member_name,
                "workspace_name": workspace_name
            }
        )
