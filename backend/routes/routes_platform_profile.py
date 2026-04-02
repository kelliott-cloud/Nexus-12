"""Platform Profile Routes — Public profile access + admin configuration."""
from fastapi import HTTPException, Request
import logging

logger = logging.getLogger(__name__)


def register_platform_profile_routes(api_router, db, get_current_user):

    @api_router.get("/platform/profile")
    async def get_platform_profile():
        """Public endpoint — returns the current platform profile."""
        from platform_profile import get_profile
        profile = get_profile()
        return {
            "profile_id": profile.get("profile_id"),
            "profile_name": profile.get("profile_name"),
            "branding": profile.get("branding", {}),
            "features": profile.get("features", {}),
            "ai_models": profile.get("ai_models", {}),
            "integrations": profile.get("integrations", {}),
            "billing": {
                "product_line": profile.get("billing", {}).get("product_line"),
                "managed_keys_enabled": profile.get("billing", {}).get("managed_keys_enabled", True),
            },
            "onboarding": profile.get("onboarding", {}),
        }

    @api_router.get("/admin/platform/profile")
    async def get_admin_profile(request: Request):
        """Admin-only — returns full profile with all internal fields."""
        user = await get_current_user(request)
        from routes.routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        from platform_profile import get_profile
        return {"profile": get_profile()}

    @api_router.put("/admin/platform/profile")
    async def update_platform_profile(request: Request):
        """Super admin — update the platform profile."""
        user = await get_current_user(request)
        from routes.routes_admin import is_super_admin
        if not await is_super_admin(db, user["user_id"]):
            raise HTTPException(403, "Super admin required")
        body = await request.json()
        from platform_profile import get_profile
        from nexus_utils import now_iso
        current = get_profile().copy()
        for key in ["features", "ai_models", "integrations", "billing", "branding", "onboarding"]:
            if key in body:
                if isinstance(body[key], dict) and isinstance(current.get(key), dict):
                    current[key].update(body[key])
                else:
                    current[key] = body[key]
        current["updated_at"] = now_iso()
        current["updated_by"] = user["user_id"]
        await db.platform_settings.update_one(
            {"setting_id": "platform_profile"},
            {"$set": {"profile": current, "updated_at": now_iso()}},
            upsert=True)
        import platform_profile
        platform_profile._profile = current
        return {"status": "updated", "profile_id": current.get("profile_id")}
