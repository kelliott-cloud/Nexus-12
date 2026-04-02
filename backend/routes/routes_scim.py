"""SCIM 2.0 Provisioning Routes — User and group sync for enterprise identity providers.
Implements SCIM 2.0 endpoints for automated user lifecycle management.
"""
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

SCIM_SCHEMA_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_SCHEMA_GROUP = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_LIST_RESPONSE = "urn:ietf:params:scim:api:messages:2.0:ListResponse"


def register_scim_routes(api_router, db, get_current_user):

    async def _verify_scim_token(request: Request):
        """Verify SCIM bearer token via hash comparison."""
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(401, "Missing SCIM bearer token")
        token = auth[7:]
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        config = await db.scim_tokens.find_one({"token_hash": token_hash, "active": True}, {"_id": 0})
        if not config:
            raise HTTPException(401, "Invalid SCIM token")
        return config

    # ===== SCIM Users =====

    @api_router.get("/scim/v2/Users")
    async def scim_list_users(request: Request):
        """SCIM: List users with filtering and pagination."""
        config = await _verify_scim_token(request)
        start = int(request.query_params.get("startIndex", 1))
        count = int(request.query_params.get("count", 100))
        filter_q = request.query_params.get("filter", "")

        query = {}
        if filter_q:
            if 'userName eq' in filter_q:
                email = filter_q.split('"')[1] if '"' in filter_q else ""
                if email:
                    query["email"] = email

        users = await db.users.find(query, {"_id": 0}).skip(start - 1).limit(count).to_list(count)
        total = await db.users.count_documents(query)

        return {
            "schemas": [SCIM_LIST_RESPONSE],
            "totalResults": total,
            "startIndex": start,
            "itemsPerPage": count,
            "Resources": [_user_to_scim(u) for u in users],
        }

    @api_router.get("/scim/v2/Users/{user_id}")
    async def scim_get_user(user_id: str, request: Request):
        """SCIM: Get a specific user."""
        await _verify_scim_token(request)
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(404, "User not found")
        return _user_to_scim(user)

    @api_router.post("/scim/v2/Users")
    async def scim_create_user(request: Request):
        """SCIM: Create a new user."""
        config = await _verify_scim_token(request)
        body = await request.json()

        email = body.get("userName") or body.get("emails", [{}])[0].get("value", "")
        if not email:
            raise HTTPException(400, "userName (email) is required")

        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            raise HTTPException(409, "User already exists")

        name_obj = body.get("name") or {}
        display_name = body.get("displayName") or f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip() or email.split("@")[0]

        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": display_name,
            "platform_role": config.get("default_role", "member"),
            "email_verified": True,
            "auth_provider": "scim",
            "active": body.get("active", True),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scim_external_id": body.get("externalId"),
        }
        await db.users.insert_one(user)

        # Auto-add to workspace
        workspace_id = config.get("workspace_id")
        if workspace_id:
            await db.workspace_members.insert_one({
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": config.get("default_role", "member"),
                "joined_at": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(f"SCIM provisioned user: {email}")
        return Response(content=json.dumps(_user_to_scim(user)), status_code=201, media_type="application/scim+json")

    @api_router.put("/scim/v2/Users/{user_id}")
    async def scim_replace_user(user_id: str, request: Request):
        """SCIM: Replace (full update) a user."""
        await _verify_scim_token(request)
        body = await request.json()
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(404, "User not found")

        name_obj = body.get("name") or {}
        updates = {
            "email": body.get("userName", user.get("email")),
            "name": body.get("displayName") or f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip() or user.get("name"),
            "active": body.get("active", True),
            "scim_external_id": body.get("externalId"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
        updated = {**user, **updates}
        return _user_to_scim(updated)

    @api_router.patch("/scim/v2/Users/{user_id}")
    async def scim_patch_user(user_id: str, request: Request):
        """SCIM: Patch (partial update) a user."""
        await _verify_scim_token(request)
        body = await request.json()
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(404, "User not found")

        updates = {}
        for op in body.get("Operations", []):
            path = op.get("path", "")
            value = op.get("value")
            if path == "active" or (not path and isinstance(value, dict) and "active" in value):
                active = value if isinstance(value, bool) else value.get("active", True)
                updates["active"] = active
            elif path == "userName":
                updates["email"] = value
            elif path == "displayName":
                updates["name"] = value

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.users.update_one({"user_id": user_id}, {"$set": updates})

        updated = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        return _user_to_scim(updated)

    @api_router.delete("/scim/v2/Users/{user_id}")
    async def scim_delete_user(user_id: str, request: Request):
        """SCIM: Deactivate a user."""
        await _verify_scim_token(request)
        await db.users.update_one({"user_id": user_id}, {"$set": {"active": False}})
        return Response(status_code=204)

    # ===== SCIM Groups =====

    @api_router.get("/scim/v2/Groups")
    async def scim_list_groups(request: Request):
        """SCIM: List groups (workspaces)."""
        await _verify_scim_token(request)
        workspaces = await db.workspaces.find({}, {"_id": 0, "workspace_id": 1, "name": 1}).to_list(100)
        return {
            "schemas": [SCIM_LIST_RESPONSE],
            "totalResults": len(workspaces),
            "Resources": [{"schemas": [SCIM_SCHEMA_GROUP], "id": w["workspace_id"], "displayName": w["name"]} for w in workspaces],
        }

    # ===== Admin: SCIM Token Management =====

    @api_router.post("/admin/scim/tokens")
    async def create_scim_token(request: Request):
        """Create a SCIM provisioning token."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Admin only")
        body = await request.json()
        import secrets
        import hashlib
        token = f"scim_{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        doc = {
            "token_id": f"scimtok_{uuid.uuid4().hex[:8]}",
            "token_hash": token_hash,
            "workspace_id": body.get("workspace_id"),
            "default_role": body.get("default_role", "member"),
            "active": True,
            "created_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.scim_tokens.insert_one(doc)
        return {"token_id": doc["token_id"], "token": token}

    @api_router.get("/admin/scim/tokens")
    async def list_scim_tokens(request: Request):
        """List SCIM tokens."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Admin only")
        tokens = await db.scim_tokens.find({}, {"_id": 0, "token": 0}).to_list(20)
        return {"tokens": tokens}

    @api_router.delete("/admin/scim/tokens/{token_id}")
    async def revoke_scim_token(token_id: str, request: Request):
        """Revoke a SCIM token."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Admin only")
        await db.scim_tokens.update_one({"token_id": token_id}, {"$set": {"active": False}})
        return {"status": "revoked"}


def _user_to_scim(user):
    """Convert internal user to SCIM representation."""
    name_parts = (user.get("name") or "").split(" ", 1)
    return {
        "schemas": [SCIM_SCHEMA_USER],
        "id": user["user_id"],
        "externalId": user.get("scim_external_id"),
        "userName": user.get("email"),
        "name": {
            "givenName": name_parts[0] if name_parts else "",
            "familyName": name_parts[1] if len(name_parts) > 1 else "",
        },
        "displayName": user.get("name"),
        "emails": [{"value": user.get("email"), "primary": True}],
        "active": user.get("active", True),
        "meta": {
            "resourceType": "User",
            "created": user.get("created_at"),
            "lastModified": user.get("updated_at", user.get("created_at")),
        },
    }
