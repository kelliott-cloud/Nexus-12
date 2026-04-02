"""RBAC (Role-Based Access Control) system for Nexus workspaces"""
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from typing import Optional, List
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    WORKSPACE_ADMIN = "workspace_admin"
    USER = "user"
    OBSERVER = "observer"


# Permission definitions
PERMISSIONS = {
    "view_workspace": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER, Role.OBSERVER],
    "view_channels": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER, Role.OBSERVER],
    "view_messages": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER, Role.OBSERVER],
    "send_messages": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER],
    "create_channels": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER],
    "delete_channels": [Role.ADMIN, Role.WORKSPACE_ADMIN],
    "create_tasks": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER],
    "manage_tasks": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER],
    "upload_files": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER],
    "delete_files": [Role.ADMIN, Role.WORKSPACE_ADMIN, Role.USER],
    "invite_members": [Role.ADMIN, Role.WORKSPACE_ADMIN],
    "remove_members": [Role.ADMIN, Role.WORKSPACE_ADMIN],
    "manage_roles": [Role.ADMIN, Role.WORKSPACE_ADMIN],
    "edit_workspace": [Role.ADMIN],
    "delete_workspace": [Role.ADMIN],
    "manage_nexus_agents": [Role.ADMIN, Role.USER],
    "trigger_ai_collaboration": [Role.ADMIN, Role.USER],
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission"""
    allowed_roles = PERMISSIONS.get(permission, [])
    return Role(role) in allowed_roles


async def get_member_role(db, workspace_id: str, user_id: str) -> Optional[str]:
    """Get user's role in a workspace"""
    workspace = await db.workspaces.find_one(
        {"workspace_id": workspace_id},
        {"owner_id": 1, "members": 1}
    )
    if not workspace:
        return None
    
    # Owner is always admin
    if workspace.get("owner_id") == user_id:
        return Role.ADMIN.value
    
    # Check member record
    member = await db.workspace_members.find_one(
        {"workspace_id": workspace_id, "user_id": user_id},
        {"role": 1}
    )
    if member:
        return member.get("role", Role.USER.value)
    
    # Check if user is in legacy members array
    if user_id in workspace.get("members") or []:
        return Role.USER.value
    
    return None


async def check_workspace_permission(db, workspace_id: str, user_id: str, permission: str):
    """Check if user has permission in workspace, raise 403 if not.
    Super admins bypass all workspace permission checks."""
    user = await db.users.find_one({"user_id": user_id}, {"platform_role": 1})
    if user and user.get("platform_role") == "super_admin":
        return Role.ADMIN.value
    role = await get_member_role(db, workspace_id, user_id)
    if role is None:
        raise HTTPException(403, "You are not a member of this workspace")
    if not has_permission(role, permission):
        raise HTTPException(403, f"Permission denied: {permission} requires higher role")
    return role


class InviteMember(BaseModel):
    email: str = Field(..., description="Email of user to invite")
    role: str = Field(default="user", description="Role to assign: admin, user, or observer")


class UpdateMemberRole(BaseModel):
    role: str = Field(..., description="New role: admin, user, or observer")


class CreateInviteLink(BaseModel):
    role: str = Field(default="user", description="Role for invitees: user or observer")
    max_uses: Optional[int] = Field(None, description="Max number of uses (null = unlimited)")
    expires_hours: Optional[int] = Field(24, description="Hours until expiry (null = never)")


def register_rbac_routes(api_router, db, get_current_user):
    
    @api_router.get("/workspaces/{workspace_id}/members")
    async def get_workspace_members(workspace_id: str, request: Request):
        """Get all members of a workspace with their roles"""
        user = await get_current_user(request)
        
        # Check view permission
        await check_workspace_permission(db, workspace_id, user["user_id"], "view_workspace")
        
        workspace = await db.workspaces.find_one(
            {"workspace_id": workspace_id},
            {"owner_id": 1, "members": 1, "_id": 0}
        )
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        # Get all member records
        member_records = await db.workspace_members.find(
            {"workspace_id": workspace_id},
            {"_id": 0}
        ).to_list(100)
        
        member_map = {m["user_id"]: m for m in member_records}
        
        # Build complete member list
        all_user_ids = set(workspace.get("members") or [])
        all_user_ids.add(workspace["owner_id"])
        for m in member_records:
            all_user_ids.add(m["user_id"])
        
        # Fetch user details
        users = await db.users.find(
            {"user_id": {"$in": list(all_user_ids)}},
            {"_id": 0, "user_id": 1, "name": 1, "email": 1, "picture": 1}
        ).to_list(100)
        
        user_map = {u["user_id"]: u for u in users}
        
        members = []
        for uid in all_user_ids:
            user_info = user_map.get(uid, {"user_id": uid, "name": "Unknown", "email": ""})
            
            if uid == workspace["owner_id"]:
                role = Role.ADMIN.value
                is_owner = True
            elif uid in member_map:
                role = member_map[uid].get("role", Role.USER.value)
                is_owner = False
            else:
                role = Role.USER.value
                is_owner = False
            
            members.append({
                "user_id": uid,
                "name": user_info.get("name", "Unknown"),
                "email": user_info.get("email", ""),
                "picture": user_info.get("picture", ""),
                "role": role,
                "is_owner": is_owner,
                "joined_at": member_map.get(uid, {}).get("joined_at")
            })
        
        return {"members": members, "count": len(members)}
    
    @api_router.post("/workspaces/{workspace_id}/members/invite")
    async def invite_member(workspace_id: str, data: InviteMember, request: Request):
        """Invite a user to workspace by email"""
        user = await get_current_user(request)
        
        # Check invite permission
        await check_workspace_permission(db, workspace_id, user["user_id"], "invite_members")
        
        # Validate role
        if data.role not in [r.value for r in Role]:
            raise HTTPException(400, "Invalid role. Choose from: admin, user, observer")
        
        # Find user by email
        invitee = await db.users.find_one({"email": data.email}, {"_id": 0, "user_id": 1})
        
        if not invitee:
            # Create pending invitation for non-existing user
            invite_id = f"inv_{uuid.uuid4().hex[:12]}"
            invitation = {
                "invite_id": invite_id,
                "workspace_id": workspace_id,
                "email": data.email,
                "role": data.role,
                "invited_by": user["user_id"],
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.workspace_invitations.insert_one(invitation)
            
            return {
                "status": "pending",
                "message": f"Invitation sent to {data.email}. They'll be added when they sign up.",
                "invite_id": invite_id
            }
        
        # Check if already a member
        existing = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": invitee["user_id"]
        })
        if existing:
            raise HTTPException(400, "User is already a member of this workspace")
        
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if workspace and workspace.get("owner_id") == invitee["user_id"]:
            raise HTTPException(400, "User is already the owner of this workspace")
        
        # Add as member
        member_record = {
            "workspace_id": workspace_id,
            "user_id": invitee["user_id"],
            "role": data.role,
            "invited_by": user["user_id"],
            "joined_at": datetime.now(timezone.utc).isoformat()
        }
        await db.workspace_members.insert_one(member_record)
        
        # Also add to legacy members array for backward compatibility
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$addToSet": {"members": invitee["user_id"]}}
        )
        
        return {
            "status": "added",
            "message": f"User added to workspace as {data.role}",
            "user_id": invitee["user_id"]
        }
    
    @api_router.post("/workspaces/{workspace_id}/invite-link")
    async def create_invite_link(workspace_id: str, data: CreateInviteLink, request: Request):
        """Create a shareable invite link for workspace"""
        user = await get_current_user(request)
        
        # Check invite permission
        await check_workspace_permission(db, workspace_id, user["user_id"], "invite_members")
        
        # Validate role (can't create admin invite links)
        if data.role not in ["user", "observer"]:
            raise HTTPException(400, "Invite links can only be for 'user' or 'observer' roles")
        
        link_code = uuid.uuid4().hex[:16]
        
        expires_at = None
        if data.expires_hours:
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=data.expires_hours)).isoformat()
        
        invite_link = {
            "link_code": link_code,
            "workspace_id": workspace_id,
            "role": data.role,
            "created_by": user["user_id"],
            "max_uses": data.max_uses,
            "uses": 0,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.invite_links.insert_one(invite_link)
        
        return {
            "link_code": link_code,
            "role": data.role,
            "max_uses": data.max_uses,
            "expires_at": expires_at
        }
    
    @api_router.post("/invites/{link_code}/join")
    async def join_via_invite_link(link_code: str, request: Request):
        """Join a workspace using an invite link"""
        user = await get_current_user(request)
        
        # Find invite link
        invite = await db.invite_links.find_one({"link_code": link_code})
        if not invite:
            raise HTTPException(404, "Invalid invite link")
        
        # Check expiry
        if invite.get("expires_at"):
            expires = datetime.fromisoformat(invite["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                raise HTTPException(400, "Invite link has expired")
        
        # Check max uses
        if invite.get("max_uses") and invite.get("uses", 0) >= invite["max_uses"]:
            raise HTTPException(400, "Invite link has reached maximum uses")
        
        workspace_id = invite["workspace_id"]
        
        # Check if already a member
        existing = await db.workspace_members.find_one({
            "workspace_id": workspace_id,
            "user_id": user["user_id"]
        })
        if existing:
            raise HTTPException(400, "You are already a member of this workspace")
        
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if workspace and workspace.get("owner_id") == user["user_id"]:
            raise HTTPException(400, "You are already the owner of this workspace")
        
        # Add as member
        member_record = {
            "workspace_id": workspace_id,
            "user_id": user["user_id"],
            "role": invite["role"],
            "invited_via": "link",
            "link_code": link_code,
            "joined_at": datetime.now(timezone.utc).isoformat()
        }
        await db.workspace_members.insert_one(member_record)
        
        # Update legacy members array
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$addToSet": {"members": user["user_id"]}}
        )
        
        # Increment uses
        await db.invite_links.update_one(
            {"link_code": link_code},
            {"$inc": {"uses": 1}}
        )
        
        return {
            "status": "joined",
            "workspace_id": workspace_id,
            "role": invite["role"]
        }
    
    @api_router.get("/invites/{link_code}")
    async def get_invite_info(link_code: str, request: Request):
        """Get info about an invite link (for preview before joining)"""
        user = await get_current_user(request)
        
        invite = await db.invite_links.find_one({"link_code": link_code}, {"_id": 0})
        if not invite:
            raise HTTPException(404, "Invalid invite link")
        
        workspace = await db.workspaces.find_one(
            {"workspace_id": invite["workspace_id"]},
            {"_id": 0, "name": 1, "description": 1}
        )
        
        # Check if already a member
        is_member = await db.workspace_members.find_one({
            "workspace_id": invite["workspace_id"],
            "user_id": user["user_id"]
        }) is not None
        
        owner = await db.workspaces.find_one({"workspace_id": invite["workspace_id"]})
        if owner and owner.get("owner_id") == user["user_id"]:
            is_member = True
        
        return {
            "workspace_name": workspace.get("name") if workspace else "Unknown",
            "workspace_description": workspace.get("description") if workspace else "",
            "role": invite["role"],
            "is_member": is_member,
            "expired": invite.get("expires_at") and datetime.fromisoformat(invite["expires_at"]).replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
        }
    
    @api_router.put("/workspaces/{workspace_id}/members/{member_user_id}/role")
    async def update_member_role(workspace_id: str, member_user_id: str, data: UpdateMemberRole, request: Request):
        """Update a member's role"""
        user = await get_current_user(request)
        
        # Check manage roles permission
        await check_workspace_permission(db, workspace_id, user["user_id"], "manage_roles")
        
        # Validate role
        if data.role not in [r.value for r in Role]:
            raise HTTPException(400, "Invalid role. Choose from: admin, user, observer")
        
        # Can't change owner's role
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if workspace and workspace.get("owner_id") == member_user_id:
            raise HTTPException(400, "Cannot change the owner's role")
        
        # Update or create member record
        await db.workspace_members.update_one(
            {"workspace_id": workspace_id, "user_id": member_user_id},
            {"$set": {"role": data.role, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        return {"status": "updated", "role": data.role}
    
    @api_router.delete("/workspaces/{workspace_id}/members/{member_user_id}")
    async def remove_member(workspace_id: str, member_user_id: str, request: Request):
        """Remove a member from workspace"""
        user = await get_current_user(request)
        
        # Check remove permission
        await check_workspace_permission(db, workspace_id, user["user_id"], "remove_members")
        
        # Can't remove owner
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if workspace and workspace.get("owner_id") == member_user_id:
            raise HTTPException(400, "Cannot remove the workspace owner")
        
        # Remove member record
        await db.workspace_members.delete_one({
            "workspace_id": workspace_id,
            "user_id": member_user_id
        })
        
        # Remove from legacy members array
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$pull": {"members": member_user_id}}
        )
        
        return {"status": "removed"}
    
    @api_router.post("/workspaces/{workspace_id}/leave")
    async def leave_workspace(workspace_id: str, request: Request):
        """Leave a workspace (non-owners only)"""
        user = await get_current_user(request)
        
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        
        if workspace.get("owner_id") == user["user_id"]:
            raise HTTPException(400, "Owner cannot leave. Transfer ownership or delete workspace.")
        
        # Remove member record
        await db.workspace_members.delete_one({
            "workspace_id": workspace_id,
            "user_id": user["user_id"]
        })
        
        # Remove from legacy members array
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$pull": {"members": user["user_id"]}}
        )
        
        return {"status": "left"}
    
    @api_router.get("/workspaces/{workspace_id}/my-role")
    async def get_my_role(workspace_id: str, request: Request):
        """Get current user's role in workspace"""
        user = await get_current_user(request)
        
        role = await get_member_role(db, workspace_id, user["user_id"])
        if not role:
            raise HTTPException(403, "You are not a member of this workspace")
        
        return {
            "role": role,
            "permissions": [p for p, roles in PERMISSIONS.items() if Role(role) in roles]
        }
    
    # Export helper for use in other routes
    return check_workspace_permission, get_member_role, has_permission
