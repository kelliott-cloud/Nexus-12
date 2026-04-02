"""Module Configuration Routes — CRUD for workspace modules, wizard, bundles."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)



class WizardSave(BaseModel):
    persona: str = ""
    modules: Dict[str, bool] = {}
    ai_models: List[str] = []


class ModuleUpdate(BaseModel):
    modules: Dict[str, bool] = {}
    ai_models: Optional[List[str]] = None


class OrgModuleDefaultsUpdate(BaseModel):
    modules: Optional[Dict[str, bool]] = None
    ai_models: Optional[List[str]] = None
    locked_modules: Optional[List[str]] = None
    blocked_modules: Optional[List[str]] = None
    max_ai_models: Optional[int] = None


def register_module_routes(api_router, db, get_current_user):

    @api_router.get("/modules/registry")
    async def get_registry():
        from module_registry import MODULE_REGISTRY
        return {"modules": MODULE_REGISTRY}

    @api_router.get("/modules/bundles")
    async def get_bundles():
        from module_registry import PERSONA_BUNDLES
        return {"bundles": PERSONA_BUNDLES}

    @api_router.get("/workspaces/{ws_id}/modules")
    async def get_workspace_modules(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "module_config": 1})
        config = (ws or {}).get("module_config")
        if not config:
            # Backward compat: no config = all modules enabled
            from module_registry import MODULE_REGISTRY, ALL_AI_MODELS
            config = {"wizard_completed": False, "modules": {mid: {"enabled": True} for mid in MODULE_REGISTRY}, "ai_models": ALL_AI_MODELS, "persona": None}
        # Compute enabled nav keys
        from module_registry import get_enabled_nav_keys
        nav_keys = list(get_enabled_nav_keys(config))
        return {**config, "enabled_nav_keys": nav_keys}

    @api_router.put("/workspaces/{ws_id}/modules")
    async def update_workspace_modules(ws_id: str, data: ModuleUpdate, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        from module_registry import MODULE_REGISTRY, check_module_tier, PLAN_MODEL_LIMITS

        # Get user plan
        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "plan": 1})
        plan = (user_doc or {}).get("plan", "free")

        # Validate modules against plan tier
        updates = {}
        for mid, enabled in data.modules.items():
            if mid not in MODULE_REGISTRY:
                continue
            if MODULE_REGISTRY[mid]["always_on"]:
                continue
            if enabled and not check_module_tier(mid, plan):
                raise HTTPException(403, f"{MODULE_REGISTRY[mid]['name']} requires a {MODULE_REGISTRY[mid]['min_tier']} plan or higher.")
            updates[f"module_config.modules.{mid}"] = {"enabled": enabled, "activated_at": now_iso() if enabled else None, "activated_by": user["user_id"] if enabled else None}

        if data.ai_models is not None:
            max_models = PLAN_MODEL_LIMITS.get(plan, 3)
            if len(data.ai_models) > max_models:
                raise HTTPException(403, f"Your {plan} plan allows up to {max_models} AI models.")
            updates["module_config.ai_models"] = data.ai_models

        if updates:
            await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": updates})
            from module_middleware import clear_module_cache
            clear_module_cache(ws_id)

        return await get_workspace_modules(ws_id, request)

    @api_router.post("/workspaces/{ws_id}/modules/wizard")
    async def save_wizard(ws_id: str, data: WizardSave, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        from module_registry import MODULE_REGISTRY

        modules = {}
        for mid in MODULE_REGISTRY:
            if MODULE_REGISTRY[mid]["always_on"]:
                modules[mid] = {"enabled": True, "activated_at": now_iso(), "activated_by": user["user_id"]}
            else:
                enabled = data.modules.get(mid, False)
                modules[mid] = {"enabled": enabled, "activated_at": now_iso() if enabled else None, "activated_by": user["user_id"] if enabled else None}

        config = {
            "module_config": {
                "persona": data.persona,
                "modules": modules,
                "ai_models": data.ai_models or ["claude", "chatgpt", "gemini"],
                "wizard_completed": True,
                "wizard_completed_at": now_iso(),
                "wizard_completed_by": user["user_id"],
            }
        }
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": config})
        from module_middleware import clear_module_cache
        clear_module_cache(ws_id)
        return {"saved": True, "workspace_id": ws_id}

    @api_router.get("/workspaces/{ws_id}/modules/usage")
    async def module_usage(ws_id: str, request: Request):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, ws_id)
        from module_registry import MODULE_REGISTRY

        usage = {}
        for mid, mod in MODULE_REGISTRY.items():
            count = 0
            for prefix in mod["route_prefixes"][:3]:
                collection = prefix.strip("/").split("/")[0].replace("-", "_")
                try:
                    count += await db[collection].count_documents({"workspace_id": ws_id})
                except Exception as _e:
                    import logging; logging.getLogger("routes/routes_modules").warning(f"Suppressed: {_e}")
            usage[mid] = {"name": mod["name"], "data_count": count, "has_data": count > 0}
        return {"usage": usage}

    @api_router.get("/orgs/{org_id}/module-defaults")
    async def get_org_defaults(org_id: str, request: Request):
        user = await get_current_user(request)
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "owner_id": 1, "org_module_defaults": 1})
        if not org:
            raise HTTPException(404, "Organization not found")
        is_owner = org.get("owner_id") == user["user_id"]
        is_super = user.get("platform_role") == "super_admin"
        if not is_owner and not is_super:
            membership = await db.org_memberships.find_one({"org_id": org_id, "user_id": user["user_id"]}, {"_id": 0})
            if not membership:
                raise HTTPException(403, "Not a member of this organization")
        return org.get("org_module_defaults", {"modules": {}, "ai_models": [], "locked_modules": [], "blocked_modules": [], "max_ai_models": None})

    @api_router.put("/orgs/{org_id}/module-defaults")
    async def update_org_defaults(org_id: str, data: OrgModuleDefaultsUpdate, request: Request):
        user = await get_current_user(request)
        # Check org ownership, super_admin, or org admin role
        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "owner_id": 1})
        is_owner = org and org.get("owner_id") == user["user_id"]
        is_super = user.get("platform_role") == "super_admin"
        is_org_admin = False
        if not is_owner and not is_super:
            membership = await db.org_memberships.find_one({"org_id": org_id, "user_id": user["user_id"]}, {"_id": 0, "role": 1})
            is_org_admin = membership and membership.get("role") in ("admin", "owner")
        if not is_owner and not is_super and not is_org_admin:
            raise HTTPException(403, "Only org owner, org admin, or super admin can update module defaults")
        updates = {}
        if data.modules is not None:
            updates["org_module_defaults.modules"] = data.modules
        if data.ai_models is not None:
            updates["org_module_defaults.ai_models"] = data.ai_models
        if data.locked_modules is not None:
            updates["org_module_defaults.locked_modules"] = data.locked_modules
        if data.blocked_modules is not None:
            updates["org_module_defaults.blocked_modules"] = data.blocked_modules
        if data.max_ai_models is not None:
            updates["org_module_defaults.max_ai_models"] = data.max_ai_models
        if updates:
            await db.organizations.update_one({"org_id": org_id}, {"$set": updates})
            from module_middleware import clear_module_cache
            clear_module_cache()  # Clear all — org defaults affect all workspaces
        return {"updated": True}
