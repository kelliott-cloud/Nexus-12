"""Organization / Multi-Tenant routes for Nexus platform"""
import uuid
import re
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, Response


# ============ Models ============

class OrgCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=50)
    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_email: str
    admin_password: str = Field(..., min_length=6)

class OrgUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None

class OrgInvite(BaseModel):
    email: str
    org_role: str = "member"

class OrgRoleUpdate(BaseModel):
    org_role: str

class OrgPlanUpdate(BaseModel):
    plan: str

# Org roles
ORG_ROLES = ["org_owner", "org_admin", "org_member", "org_viewer"]
ORG_ADMIN_ROLES = ["org_owner", "org_admin"]

SLUG_PATTERN = re.compile(r'^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$')
RESERVED_SLUGS = {"admin", "api", "auth", "dashboard", "settings", "billing", "download", "my-bugs", "org", "nexus", "app", "www"}


from nexus_utils import safe_regex

def register_org_routes(api_router, db, get_current_user):

    async def get_org_role(org_id: str, user_id: str) -> Optional[str]:
        """Get user's role within an organization"""
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user_id},
            {"_id": 0, "org_role": 1}
        )
        return membership.get("org_role") if membership else None

    async def require_org_member(org_id: str, user_id: str) -> str:
        role = await get_org_role(org_id, user_id)
        if not role:
            raise HTTPException(403, "Not a member of this organization")
        return role

    async def require_org_admin(org_id: str, user_id: str) -> str:
        role = await get_org_role(org_id, user_id)
        if role not in ORG_ADMIN_ROLES:
            raise HTTPException(403, "Organization admin access required")
        return role

    # ============ Public: Org Info ============

    @api_router.get("/orgs/by-slug/{slug}")
    async def get_org_by_slug(slug: str):
        """Public endpoint to get org info for login page"""
        org = await db.organizations.find_one(
            {"slug": slug.lower()},
            {"_id": 0, "org_id": 1, "name": 1, "slug": 1, "logo_url": 1, "plan": 1, "nexus_ai_enabled": 1}
        )
        if not org:
            raise HTTPException(404, "Organization not found")
        member_count = await db.org_memberships.count_documents({"org_id": org["org_id"]})
        org["member_count"] = member_count
        return org

    # ============ Org Registration ============

    @api_router.post("/orgs/register")
    async def register_organization(data: OrgCreate, response: Response):
        """Register a new organization with admin account"""
        slug = data.slug.lower().strip()

        if not SLUG_PATTERN.match(slug):
            raise HTTPException(400, "Slug must be 2-50 chars, lowercase letters, numbers, hyphens only. Must start/end with letter or number.")
        if slug in RESERVED_SLUGS:
            raise HTTPException(400, "This URL is reserved. Please choose a different one.")

        existing = await db.organizations.find_one({"slug": slug})
        if existing:
            raise HTTPException(400, "Organization URL already taken")

        existing_email = await db.users.find_one({"email": data.admin_email.lower()})
        if existing_email:
            raise HTTPException(400, "Email already registered. Log in and create an organization from your dashboard.")

        # Create admin user
        import bcrypt
        password_hash = bcrypt.hashpw(data.admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        user = {
            "user_id": user_id,
            "email": data.admin_email.lower(),
            "name": data.admin_name,
            "password_hash": password_hash,
            "auth_type": "email",
            "auth_provider": "email",
            "plan": "free",
            "platform_role": "user",
            "created_at": now
        }
        await db.users.insert_one(user)

        # Create organization
        org_id = f"org_{uuid.uuid4().hex[:12]}"
        org = {
            "org_id": org_id,
            "name": data.name,
            "slug": slug,
            "logo_url": "",
            "description": "",
            "plan": "free",
            "owner_id": user_id,
            "settings": {},
            "knowledge_graph": {
                "tenant_kg_enabled": False,
                "platform_kg_enabled": False,
                "tenant_kg_consented_by": None,
                "tenant_kg_consented_at": None,
                "platform_kg_consented_by": None,
                "platform_kg_consented_at": None,
                "consent_version": "1.0",
            },
            "created_at": now,
            "updated_at": now
        }
        await db.organizations.insert_one(org)

        # Create membership
        await db.org_memberships.insert_one({
            "membership_id": f"mem_{uuid.uuid4().hex[:12]}",
            "org_id": org_id,
            "user_id": user_id,
            "org_role": "org_owner",
            "joined_at": now
        })

        # Create session
        import secrets
        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)).isoformat(),
            "created_at": now
        })

        response.set_cookie(
            key="session_token", value=session_token,
            httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
        )

        return {
            "org_id": org_id,
            "slug": slug,
            "name": data.name,
            "user_id": user_id,
            "session_token": session_token
        }

    @api_router.post("/orgs/check-slug")
    async def check_slug_availability(data: dict):
        """Check if a slug is available"""
        slug = data.get("slug", "").lower().strip()
        if not SLUG_PATTERN.match(slug):
            return {"available": False, "reason": "Invalid format"}
        if slug in RESERVED_SLUGS:
            return {"available": False, "reason": "Reserved"}
        existing = await db.organizations.find_one({"slug": slug})
        return {"available": existing is None}

    # ============ Org CRUD (authenticated) ============

    @api_router.get("/orgs/my-orgs")
    async def get_my_organizations(request: Request):
        """Get all organizations the current user belongs to"""
        user = await get_current_user(request)
        memberships = await db.org_memberships.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).to_list(50)

        orgs = []
        for m in memberships:
            org = await db.organizations.find_one(
                {"org_id": m["org_id"]},
                {"_id": 0, "org_id": 1, "name": 1, "slug": 1, "logo_url": 1, "plan": 1, "created_at": 1}
            )
            if org:
                member_count = await db.org_memberships.count_documents({"org_id": m["org_id"]})
                org["org_role"] = m["org_role"]
                org["member_count"] = member_count
                orgs.append(org)
        return {"organizations": orgs}

    @api_router.get("/orgs/{org_id}")
    async def get_organization(org_id: str, request: Request):
        """Get organization details (members only)"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0})
        if not org:
            raise HTTPException(404, "Organization not found")
        member_count = await db.org_memberships.count_documents({"org_id": org_id})
        org["member_count"] = member_count
        return org

    @api_router.put("/orgs/{org_id}")
    async def update_organization(org_id: str, data: OrgUpdate, request: Request):
        """Update org settings (admin only)"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if data.name is not None:
            updates["name"] = data.name
        if data.logo_url is not None:
            updates["logo_url"] = data.logo_url
        if data.description is not None:
            updates["description"] = data.description
        await db.organizations.update_one({"org_id": org_id}, {"$set": updates})
        return {"status": "updated"}

    # ============ Org Members ============

    @api_router.get("/orgs/{org_id}/members")
    async def get_org_members(org_id: str, request: Request):
        """Get all members of an organization"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])

        memberships = await db.org_memberships.find(
            {"org_id": org_id}, {"_id": 0}
        ).to_list(500)

        user_ids = [m["user_id"] for m in memberships]
        users = await db.users.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "email": 1, "name": 1, "picture": 1}
        ).to_list(500)
        user_map = {u["user_id"]: u for u in users}

        members = []
        for m in memberships:
            u = user_map.get(m["user_id"])
            if u:
                member = {**u, "org_role": m["org_role"], "joined_at": m.get("joined_at")}
                members.append(member)
        return {"members": members, "total": len(members)}

    @api_router.post("/orgs/{org_id}/members")
    async def invite_org_member(org_id: str, data: OrgInvite, request: Request):
        """Invite a user to the organization"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        if data.org_role not in ["org_admin", "org_member", "org_viewer"]:
            raise HTTPException(400, "Invalid role")

        target = await db.users.find_one({"email": data.email.lower()}, {"_id": 0, "user_id": 1})
        if not target:
            raise HTTPException(404, "User not found. They must register first.")

        existing = await db.org_memberships.find_one({"org_id": org_id, "user_id": target["user_id"]})
        if existing:
            raise HTTPException(400, "User is already a member")

        await db.org_memberships.insert_one({
            "membership_id": f"mem_{uuid.uuid4().hex[:12]}",
            "org_id": org_id,
            "user_id": target["user_id"],
            "org_role": data.org_role,
            "joined_at": datetime.now(timezone.utc).isoformat()
        })
        return {"status": "invited", "user_id": target["user_id"]}

    @api_router.put("/orgs/{org_id}/members/{user_id}/role")
    async def update_member_role(org_id: str, user_id: str, data: OrgRoleUpdate, request: Request):
        """Update a member's org role"""
        user = await get_current_user(request)
        caller_role = await require_org_admin(org_id, user["user_id"])  # noqa: F841

        if data.org_role not in ["org_admin", "org_member", "org_viewer"]:
            raise HTTPException(400, "Invalid role")

        target_membership = await db.org_memberships.find_one({"org_id": org_id, "user_id": user_id})
        if not target_membership:
            raise HTTPException(404, "Member not found")
        if target_membership["org_role"] == "org_owner":
            raise HTTPException(400, "Cannot change org owner's role")

        await db.org_memberships.update_one(
            {"org_id": org_id, "user_id": user_id},
            {"$set": {"org_role": data.org_role}}
        )
        return {"status": "updated", "org_role": data.org_role}

    @api_router.delete("/orgs/{org_id}/members/{user_id}")
    async def remove_org_member(org_id: str, user_id: str, request: Request):
        """Remove a member from the organization"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        target = await db.org_memberships.find_one({"org_id": org_id, "user_id": user_id})
        if not target:
            raise HTTPException(404, "Member not found")
        if target["org_role"] == "org_owner":
            raise HTTPException(400, "Cannot remove org owner")

        await db.org_memberships.delete_one({"org_id": org_id, "user_id": user_id})
        return {"status": "removed"}

    # ============ Org-Scoped Workspaces ============

    @api_router.get("/orgs/{org_id}/workspaces")
    async def get_org_workspaces(org_id: str, request: Request):
        """Get all workspaces in an organization"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])
        workspaces = await db.workspaces.find(
            {"org_id": org_id}, {"_id": 0}
        ).to_list(100)
        return {"workspaces": workspaces}

    @api_router.post("/orgs/{org_id}/workspaces")
    async def create_org_workspace(org_id: str, data: dict, request: Request):
        """Create a workspace within an organization"""
        user = await get_current_user(request)
        role = await require_org_member(org_id, user["user_id"])
        if role == "org_viewer":
            raise HTTPException(403, "Viewers cannot create workspaces")

        workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
        workspace = {
            "workspace_id": workspace_id,
            "name": data.get("name", "Untitled"),
            "description": data.get("description", ""),
            "owner_id": user["user_id"],
            "org_id": org_id,
            "members": [user["user_id"]],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.workspaces.insert_one(workspace)
        return await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})

    # ============ Org Admin Dashboard ============

    @api_router.get("/orgs/{org_id}/admin/stats")
    async def get_org_stats(org_id: str, request: Request):
        """Get org-level statistics"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        member_count = await db.org_memberships.count_documents({"org_id": org_id})
        workspace_count = await db.workspaces.count_documents({"org_id": org_id})

        # Get workspace IDs for org
        ws_ids = [w["workspace_id"] async for w in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        channel_count = await db.channels.count_documents({"workspace_id": {"$in": ws_ids}}) if ws_ids else 0
        message_count = await db.messages.count_documents({"channel_id": {"$regex": "^ch_"}}) if ws_ids else 0

        # Count messages in org channels
        if ws_ids:
            ch_ids = [c["channel_id"] async for c in db.channels.find({"workspace_id": {"$in": ws_ids}}, {"channel_id": 1, "_id": 0})]
            message_count = await db.messages.count_documents({"channel_id": {"$in": ch_ids}}) if ch_ids else 0

        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "plan": 1, "name": 1, "created_at": 1})

        return {
            "members": member_count,
            "workspaces": workspace_count,
            "channels": channel_count,
            "messages": message_count,
            "plan": org.get("plan", "free") if org else "free",
            "org_name": org.get("name", "") if org else ""
        }

    @api_router.get("/orgs/{org_id}/admin/members")
    async def get_org_admin_members(org_id: str, request: Request):
        """Admin view of org members with details"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        memberships = await db.org_memberships.find({"org_id": org_id}, {"_id": 0}).to_list(500)

        user_ids = [m["user_id"] for m in memberships]
        users = await db.users.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "email": 1, "name": 1, "picture": 1, "auth_provider": 1, "auth_type": 1, "created_at": 1}
        ).to_list(500)
        user_map = {u["user_id"]: u for u in users}

        # Batch workspace counts per user
        ws_list = await db.workspaces.find({"org_id": org_id}, {"_id": 0, "owner_id": 1, "members": 1}).to_list(500)
        ws_counts = {}
        for uid in user_ids:
            ws_counts[uid] = sum(1 for w in ws_list if w.get("owner_id") == uid or uid in (w.get("members") or []))

        members = []
        for m in memberships:
            u = user_map.get(m["user_id"])
            if u:
                member = {**u, "org_role": m["org_role"], "joined_at": m.get("joined_at"), "workspace_count": ws_counts.get(m["user_id"], 0)}
                members.append(member)
        return {"members": members, "total": len(members)}

    @api_router.get("/orgs/{org_id}/admin/activity")
    async def get_org_activity(org_id: str, request: Request):
        """Get org activity logs"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        logs = await db.platform_logs.find(
            {"details.org_id": org_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(50).to_list(50)
        return {"logs": logs}

    @api_router.get("/orgs/{org_id}/admin/analytics")
    async def get_org_analytics(org_id: str, request: Request):
        """Get org-level AI usage analytics"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        ws_ids = [w["workspace_id"] async for w in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {"total_messages": 0, "ai_messages": 0, "model_usage": {}, "daily_activity": []}

        ch_ids = [c["channel_id"] async for c in db.channels.find({"workspace_id": {"$in": ws_ids}}, {"channel_id": 1, "_id": 0})]
        if not ch_ids:
            return {"total_messages": 0, "ai_messages": 0, "model_usage": {}, "daily_activity": []}

        total_msgs = await db.messages.count_documents({"channel_id": {"$in": ch_ids}})
        ai_msgs = await db.messages.count_documents({"channel_id": {"$in": ch_ids}, "sender_type": "ai"})

        # Model usage breakdown
        pipeline = [
            {"$match": {"channel_id": {"$in": ch_ids}, "sender_type": "ai"}},
            {"$group": {"_id": "$model", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        model_usage = {}
        async for doc in db.messages.aggregate(pipeline):
            if doc["_id"]:
                model_usage[doc["_id"]] = doc["count"]

        return {
            "total_messages": total_msgs,
            "ai_messages": ai_msgs,
            "human_messages": total_msgs - ai_msgs,
            "model_usage": model_usage,
            "workspaces": len(ws_ids),
            "channels": len(ch_ids)
        }

    # ============ Org Billing ============

    @api_router.get("/orgs/{org_id}/billing")
    async def get_org_billing(org_id: str, request: Request):
        """Get org billing info"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "plan": 1, "name": 1, "org_id": 1})
        if not org:
            raise HTTPException(404, "Organization not found")
        member_count = await db.org_memberships.count_documents({"org_id": org_id})
        return {
            "org_id": org["org_id"],
            "name": org["name"],
            "plan": org.get("plan", "free"),
            "member_count": member_count,
            "plans": {
                "free": {"name": "Free", "price": 0, "max_members": 5, "max_workspaces": 3},
                "pro": {"name": "Pro", "price": 49, "max_members": 25, "max_workspaces": 20},
                "enterprise": {"name": "Enterprise", "price": 199, "max_members": -1, "max_workspaces": -1}
            }
        }

    # ============ Platform Admin: All Organizations ============

    @api_router.get("/admin/organizations")
    async def get_all_organizations(request: Request):
        """Platform admin: Get all organizations"""
        user = await get_current_user(request)
        from routes_admin import require_staff
        await require_staff(db, user["user_id"])

        orgs = await db.organizations.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        for org in orgs:
            org["member_count"] = await db.org_memberships.count_documents({"org_id": org["org_id"]})
            org["workspace_count"] = await db.workspaces.count_documents({"org_id": org["org_id"]})
        total = await db.organizations.count_documents({})
        return {"organizations": orgs, "total": total}

    @api_router.put("/admin/organizations/{org_id}/plan")
    async def update_org_plan(org_id: str, data: OrgPlanUpdate, request: Request):
        """Platform admin: Update an org's plan AND propagate to all org members."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin access required")
        valid_plans = ["free", "starter", "pro", "team", "enterprise"]
        if data.plan not in valid_plans:
            raise HTTPException(400, f"Invalid plan. Must be one of: {', '.join(valid_plans)}")
        
        # Update the org
        await db.organizations.update_one(
            {"org_id": org_id},
            {"$set": {"plan": data.plan, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Propagate plan to org members — T3: only upgrade, never downgrade personal plans
        PLAN_RANK = {"free": 0, "starter": 1, "pro": 2, "team": 3, "enterprise": 4}
        new_rank = PLAN_RANK.get(data.plan, 0)
        lower_plans = [p for p, r in PLAN_RANK.items() if r < new_rank]
        
        members = await db.org_memberships.find({"org_id": org_id}, {"_id": 0, "user_id": 1}).to_list(500)
        member_ids = [m["user_id"] for m in members]
        if member_ids:
            # Only update members whose current plan ranks lower than the new org plan
            result = await db.users.update_many(
                {"user_id": {"$in": member_ids},
                 "$or": [{"plan": {"$exists": False}}, {"plan": {"$in": lower_plans}}]},
                {"$set": {"plan": data.plan, "plan_source": "org", "plan_org_id": org_id}}
            )
            logger.info(f"Org {org_id} plan → {data.plan}: upgraded {result.modified_count} members")
        
        # Also update the org owner (only if upgrading)
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "owner_id": 1})
        if org and org.get("owner_id"):
            owner = await db.users.find_one({"user_id": org["owner_id"]}, {"_id": 0, "plan": 1})
            owner_rank = PLAN_RANK.get((owner.get("plan") or "free") if owner else "free", 0)
            if new_rank > owner_rank:
                await db.users.update_one(
                    {"user_id": org["owner_id"]},
                    {"$set": {"plan": data.plan, "plan_source": "org", "plan_org_id": org_id}}
                )
        
        return {"status": "updated", "plan": data.plan, "members_updated": len(member_ids)}


    @api_router.put("/admin/organizations/{org_id}/nexus-ai")
    async def toggle_org_nexus_ai(org_id: str, request: Request):
        """Super admin: Enable/disable Nexus AI (managed keys) for an organization."""
        user = await get_current_user(request)
        from routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin access required")
        body = await request.json()
        enabled = bool(body.get("enabled", False))
        
        # Update the org setting
        await db.organizations.update_one(
            {"org_id": org_id},
            {"$set": {"nexus_ai_enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # If enabling, also opt-in all org members to platform keys for core 5
        if enabled:
            members = await db.org_memberships.find({"org_id": org_id}, {"_id": 0, "user_id": 1}).to_list(500)
            member_ids = [m["user_id"] for m in members]
            org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "owner_id": 1})
            if org and org.get("owner_id") and org["owner_id"] not in member_ids:
                member_ids.append(org["owner_id"])
            if member_ids:
                # Enable ALL platform providers for all members
                from managed_keys import PLATFORM_KEY_PROVIDERS
                optin_set = {f"managed_keys_optin.{p}": True for p in PLATFORM_KEY_PROVIDERS}
                await db.users.update_many(
                    {"user_id": {"$in": member_ids}},
                    {"$set": optin_set}
                )
                logger.info(f"Nexus AI enabled for org {org_id}: {len(member_ids)} members opted into {len(PLATFORM_KEY_PROVIDERS)} providers")
        else:
            # If disabling, opt-out all members from all providers
            members = await db.org_memberships.find({"org_id": org_id}, {"_id": 0, "user_id": 1}).to_list(500)
            member_ids = [m["user_id"] for m in members]
            if member_ids:
                from managed_keys import PLATFORM_KEY_PROVIDERS
                optout_set = {f"managed_keys_optin.{p}": False for p in PLATFORM_KEY_PROVIDERS}
                await db.users.update_many(
                    {"user_id": {"$in": member_ids}},
                    {"$set": optout_set}
                )
        
        return {"org_id": org_id, "nexus_ai_enabled": enabled}


    # ============ Custom Domain / Login URL ============

    @api_router.put("/orgs/{org_id}/custom-domain")
    async def set_custom_domain(org_id: str, request: Request):
        """Set a custom login domain for an org (e.g., nexus.urtech.org)"""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        body = await request.json()
        domain = body.get("custom_domain", "").strip().lower()
        await db.organizations.update_one(
            {"org_id": org_id},
            {"$set": {"custom_domain": domain, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"custom_domain": domain, "login_url": f"https://{domain}" if domain else f"/org/{(await db.organizations.find_one({'org_id': org_id}, {'slug': 1}))['slug']}"}

    @api_router.get("/orgs/{org_id}/login-config")
    async def get_login_config(org_id: str, request: Request):
        """Get org login URL configuration"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "slug": 1, "custom_domain": 1, "name": 1})
        if not org:
            raise HTTPException(404, "Organization not found")
        domain = org.get("custom_domain", "")
        return {
            "slug": org["slug"],
            "custom_domain": domain,
            "login_url": f"https://{domain}" if domain else None,
            "default_url": f"/org/{org['slug']}",
            "dashboard_url": f"/org/{org['slug']}/dashboard",
        }

    # ============ Org-Level Projects Roll-up ============

    @api_router.get("/orgs/{org_id}/projects")
    async def get_org_projects(org_id: str, request: Request, search: Optional[str] = None, status: Optional[str] = None):
        """Get all projects across all workspaces in the org"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])

        # Get all org workspace IDs
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {"projects": [], "total": 0}

        query = {"workspace_id": {"$in": ws_ids}}
        if search:
            query["$or"] = [{"name": {"$regex": safe_regex(search), "$options": "i"}}, {"description": {"$regex": safe_regex(search), "$options": "i"}}]
        if status:
            query["status"] = status

        projects = await db.projects.find(query, {"_id": 0}).sort("updated_at", -1).to_list(200)

        # Enrich with workspace names and task counts
        ws_map = {}
        async for ws in db.workspaces.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}):
            ws_map[ws["workspace_id"]] = ws["name"]

        if projects:
            pids = [p["project_id"] for p in projects]
            pipeline = [
                {"$match": {"project_id": {"$in": pids}}},
                {"$group": {"_id": "$project_id", "task_count": {"$sum": 1}, "tasks_done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}}}}
            ]
            counts = {c["_id"]: c async for c in db.project_tasks.aggregate(pipeline)}
            for p in projects:
                p["workspace_name"] = ws_map.get(p["workspace_id"], "Unknown")
                c = counts.get(p["project_id"], {})
                p["task_count"] = c.get("task_count", 0)
                p["tasks_done"] = c.get("tasks_done", 0)

        return {"projects": projects, "total": len(projects)}

    # ============ Org-Level Tasks Roll-up ============

    @api_router.get("/orgs/{org_id}/tasks")
    async def get_org_tasks(
        org_id: str, request: Request,
        search: Optional[str] = None, status: Optional[str] = None,
        priority: Optional[str] = None, project_id: Optional[str] = None,
        sort_by: str = "updated_at", sort_order: str = "desc",
        limit: int = 100, offset: int = 0,
    ):
        """Get all tasks across all workspaces/projects in the org"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])

        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {"tasks": [], "total": 0}

        query = {"workspace_id": {"$in": ws_ids}}
        if search:
            query["$or"] = [{"title": {"$regex": safe_regex(search), "$options": "i"}}, {"description": {"$regex": safe_regex(search), "$options": "i"}}]
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if project_id:
            query["project_id"] = project_id

        sort_dir = -1 if sort_order == "desc" else 1
        tasks = await db.project_tasks.find(query, {"_id": 0}).sort(sort_by, sort_dir).skip(offset).limit(limit).to_list(limit)
        total = await db.project_tasks.count_documents(query)

        # Enrich with project and workspace names
        if tasks:
            pids = list({t["project_id"] for t in tasks})
            projects = await db.projects.find({"project_id": {"$in": pids}}, {"_id": 0, "project_id": 1, "name": 1, "workspace_id": 1}).to_list(200)
            pmap = {p["project_id"]: p for p in projects}
            ws_map = {}
            async for ws in db.workspaces.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}):
                ws_map[ws["workspace_id"]] = ws["name"]
            for t in tasks:
                proj = pmap.get(t["project_id"], {})
                t["project_name"] = proj.get("name", "Unknown")
                t["workspace_name"] = ws_map.get(t.get("workspace_id") or proj.get("workspace_id", ""), "Unknown")
                if not t.get("workspace_id"):
                    t["workspace_id"] = proj.get("workspace_id", "")

        return {"tasks": tasks, "total": total}

    # ============ Org-Level Workflows ============

    @api_router.get("/orgs/{org_id}/workflows")
    async def get_org_workflows(org_id: str, request: Request):
        """Get all workflows across all workspaces in the org"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {"workflows": [], "total": 0}
        workflows = await db.workflows.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0}).sort("updated_at", -1).to_list(100)
        ws_map = {}
        async for ws in db.workspaces.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "workspace_id": 1, "name": 1}):
            ws_map[ws["workspace_id"]] = ws["name"]
        for wf in workflows:
            wf["workspace_name"] = ws_map.get(wf.get("workspace_id", ""), "Unknown")
        return {"workflows": workflows, "total": len(workflows)}

    # ============ Org-Level Analytics ============

    @api_router.get("/orgs/{org_id}/analytics/summary")
    async def get_org_analytics_summary(org_id: str, request: Request):
        """Aggregate analytics across all org workspaces"""
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        if not ws_ids:
            return {"total_messages": 0, "total_projects": 0, "total_tasks": 0, "total_workflows": 0, "workspaces": len(ws_ids)}
        total_messages = await db.messages.count_documents({"channel_id": {"$in": [ch["channel_id"] async for ch in db.channels.find({"workspace_id": {"$in": ws_ids}}, {"channel_id": 1, "_id": 0})]}}) if ws_ids else 0
        total_projects = await db.projects.count_documents({"workspace_id": {"$in": ws_ids}})
        total_tasks = await db.project_tasks.count_documents({"workspace_id": {"$in": ws_ids}})
        total_workflows = await db.workflows.count_documents({"workspace_id": {"$in": ws_ids}})
        return {
            "workspaces": len(ws_ids),
            "total_messages": total_messages,
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "total_workflows": total_workflows,
        }

    # ============ Org Admin: Audit Log ============

    @api_router.get("/orgs/{org_id}/admin/audit-log")
    async def get_org_audit_log(org_id: str, request: Request, limit: int = 50, offset: int = 0, action: str = None, user_filter: str = None):
        """Org admin: view aggregated audit log across all org workspaces."""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        query = {"$or": [{"workspace_id": {"$in": ws_ids}}, {"details.org_id": org_id}]} if ws_ids else {"details.org_id": org_id}
        if action:
            query["action"] = action
        if user_filter:
            query["user_id"] = user_filter
        total = await db.audit_log.count_documents(query)
        logs = await db.audit_log.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
        return {"logs": logs, "total": total, "offset": offset, "limit": limit}

    @api_router.get("/orgs/{org_id}/admin/audit-log/actions")
    async def get_org_audit_actions(org_id: str, request: Request):
        """Org admin: list distinct audit actions for filtering."""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        query = {"$or": [{"workspace_id": {"$in": ws_ids}}, {"details.org_id": org_id}]} if ws_ids else {"details.org_id": org_id}
        actions = await db.audit_log.distinct("action", query)
        return {"actions": sorted(actions)}

    @api_router.get("/orgs/{org_id}/admin/budget-audit")
    async def get_org_budget_audit(org_id: str, request: Request, limit: int = 50, offset: int = 0, provider: str = None):
        """Org admin: view budget usage events across all org workspaces."""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        query = {"org_id": org_id}
        if provider:
            query["provider"] = provider
        total = await db.managed_key_usage_events.count_documents(query)
        events = await db.managed_key_usage_events.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
        # Also aggregate total spend
        pipeline = [{"$match": {"org_id": org_id}}, {"$group": {"_id": "$provider", "total_cost": {"$sum": "$cost_usd"}, "total_events": {"$sum": 1}}}]
        spend_by_provider = {}
        async for row in db.managed_key_usage_events.aggregate(pipeline):
            if row["_id"]:
                spend_by_provider[row["_id"]] = {"cost_usd": round(row["total_cost"], 6), "events": row["total_events"]}
        return {"events": events, "total": total, "offset": offset, "limit": limit, "spend_by_provider": spend_by_provider}

    @api_router.get("/orgs/{org_id}/admin/export/csv")
    async def export_org_csv(org_id: str, request: Request, data_type: str = "budget"):
        """Org admin: export org data as CSV."""
        from fastapi.responses import StreamingResponse
        import csv
        import io
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])

        output = io.StringIO()
        writer = csv.writer(output)

        if data_type == "budget":
            writer.writerow(["Provider", "User", "Cost USD", "Usage Type", "Tokens In", "Tokens Out", "Calls", "Timestamp"])
            events = await db.managed_key_usage_events.find({"org_id": org_id}, {"_id": 0}).sort("timestamp", -1).to_list(500)
            for evt in events:
                writer.writerow([evt.get("provider", ""), evt.get("user_id", ""), evt.get("cost_usd", 0), evt.get("usage_type", ""), evt.get("tokens_in", 0), evt.get("tokens_out", 0), evt.get("call_count", 0), evt.get("timestamp", "")])
        elif data_type == "audit":
            writer.writerow(["Action", "User", "Resource Type", "Resource ID", "Workspace", "Timestamp", "Details"])
            ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
            query = {"$or": [{"workspace_id": {"$in": ws_ids}}, {"details.org_id": org_id}]} if ws_ids else {"details.org_id": org_id}
            logs = await db.audit_log.find(query, {"_id": 0}).sort("timestamp", -1).to_list(500)
            for log in logs:
                writer.writerow([log.get("action", ""), log.get("user_id", ""), log.get("resource_type", ""), log.get("resource_id", ""), log.get("workspace_id", ""), log.get("timestamp", ""), str(log.get("details", ""))[:200]])
        elif data_type == "members":
            writer.writerow(["User ID", "Email", "Name", "Role", "Joined At"])
            members = await db.org_memberships.find({"org_id": org_id}, {"_id": 0}).to_list(500)
            for m in members:
                u = await db.users.find_one({"user_id": m.get("user_id")}, {"_id": 0, "email": 1, "name": 1})
                writer.writerow([m.get("user_id", ""), (u or {}).get("email", ""), (u or {}).get("name", ""), m.get("org_role", ""), m.get("joined_at", "")])
        else:
            writer.writerow(["Error"])
            writer.writerow([f"Unknown data_type: {data_type}. Use budget, audit, or members."])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=org_{org_id}_{data_type}.csv"},
        )

    @api_router.get("/orgs/{org_id}/admin/member-activity")
    async def get_org_member_activity(org_id: str, request: Request):
        """Org admin: summarized member activity across org workspaces."""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        members = await db.org_memberships.find({"org_id": org_id}, {"_id": 0, "user_id": 1, "org_role": 1}).to_list(500)
        ws_ids = [ws["workspace_id"] async for ws in db.workspaces.find({"org_id": org_id}, {"workspace_id": 1, "_id": 0})]
        ch_ids = [ch["channel_id"] async for ch in db.channels.find({"workspace_id": {"$in": ws_ids}}, {"channel_id": 1, "_id": 0})] if ws_ids else []
        result = []
        for m in members:
            uid = m["user_id"]
            u = await db.users.find_one({"user_id": uid}, {"_id": 0, "email": 1, "name": 1, "last_active": 1})
            msg_count = await db.messages.count_documents({"sender_id": uid, "channel_id": {"$in": ch_ids}}) if ch_ids else 0
            # Budget spend
            pipeline = [{"$match": {"user_id": uid, "org_id": org_id}}, {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}}]
            spend_rows = await db.managed_key_usage_events.aggregate(pipeline).to_list(1)
            spend = round(spend_rows[0]["total"], 6) if spend_rows else 0.0
            result.append({
                "user_id": uid, "email": (u or {}).get("email", ""), "name": (u or {}).get("name", ""),
                "org_role": m.get("org_role", "member"), "last_active": (u or {}).get("last_active"),
                "messages_sent": msg_count, "total_spend_usd": spend,
            })
        return {"members": result}

    # ============ Knowledge Graph Consent ============

    @api_router.post("/orgs/{org_id}/knowledge-graph/consent")
    async def update_kg_consent(org_id: str, request: Request):
        """Update KG consent (Tier 2 + Tier 3). Org owner/admin only."""
        user = await get_current_user(request)
        await require_org_admin(org_id, user["user_id"])
        body = await request.json()
        from nexus_utils import now_iso, gen_id
        updates = {"updated_at": now_iso()}
        if "tenant_kg_enabled" in body:
            enabled = bool(body["tenant_kg_enabled"])
            updates["knowledge_graph.tenant_kg_enabled"] = enabled
            updates["knowledge_graph.tenant_kg_consented_by"] = user["user_id"] if enabled else None
            updates["knowledge_graph.tenant_kg_consented_at"] = now_iso() if enabled else None
            if not enabled:
                from knowledge_graph import _schedule_kg_purge
                await _schedule_kg_purge(db, org_id, "tenant")
        if "platform_kg_enabled" in body:
            enabled = bool(body["platform_kg_enabled"])
            updates["knowledge_graph.platform_kg_enabled"] = enabled
            updates["knowledge_graph.platform_kg_consented_by"] = user["user_id"] if enabled else None
            updates["knowledge_graph.platform_kg_consented_at"] = now_iso() if enabled else None
            if not enabled:
                from knowledge_graph import _schedule_kg_purge
                await _schedule_kg_purge(db, org_id, "platform")
        await db.organizations.update_one({"org_id": org_id}, {"$set": updates})
        await db.kg_consent_audit.insert_one({
            "audit_id": gen_id("kga"), "org_id": org_id, "changed_by": user["user_id"],
            "changes": {k: v for k, v in body.items() if k in ("tenant_kg_enabled", "platform_kg_enabled")},
            "timestamp": now_iso(), "consent_version": "1.0",
        })
        return {"status": "consent_updated"}

    @api_router.get("/orgs/{org_id}/knowledge-graph/consent")
    async def get_kg_consent(org_id: str, request: Request):
        user = await get_current_user(request)
        await require_org_member(org_id, user["user_id"])
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "knowledge_graph": 1})
        return {"knowledge_graph": (org or {}).get("knowledge_graph", {})}

    return get_org_role, require_org_member, require_org_admin
