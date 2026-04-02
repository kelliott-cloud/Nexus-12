"""Routes for Nexus Managed Keys — platform-provided AI keys with credit billing."""
import os
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class SetPlatformKeys(BaseModel):
    keys: Dict[str, str]  # {provider: api_key}


class OptInToggle(BaseModel):
    provider: str
    enabled: bool


def register_managed_keys_routes(api_router, db, get_current_user):
    from managed_keys import (
        PLATFORM_KEY_PROVIDERS, PLAN_CREDITS, MODEL_CREDIT_RATES,
        INTEGRATION_KEY_MAP, INTEGRATION_CREDIT_RATES,
        check_credits, init_managed_keys,
        get_scope_budget, upsert_scope_budget, get_scope_budget_dashboard, get_scope_alerts,
        PLATFORM_SCOPE_ID,
    )
    from routes_ai_keys import encrypt_key, decrypt_key, mask_key

    init_managed_keys(db)

    async def _require_super_admin(request: Request):
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin only")
        return user

    async def _require_org_admin(request: Request, org_id: str):
        user = await get_current_user(request)
        membership = await db.org_memberships.find_one(
            {"org_id": org_id, "user_id": user["user_id"], "org_role": {"$in": ["org_owner", "org_admin"]}},
            {"_id": 0, "org_role": 1},
        )
        if not membership and user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Organization admin access required")
        return user

    async def _require_workspace_budget_admin(request: Request, workspace_id: str):
        user = await get_current_user(request)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "owner_id": 1, "org_id": 1, "members": 1})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        if user.get("platform_role") == "super_admin":
            return user, workspace
        if workspace.get("owner_id") == user["user_id"]:
            return user, workspace
        if workspace.get("org_id"):
            membership = await db.org_memberships.find_one(
                {"org_id": workspace["org_id"], "user_id": user["user_id"], "org_role": {"$in": ["org_owner", "org_admin"]}},
                {"_id": 0, "org_role": 1},
            )
            if membership:
                return user, workspace
        raise HTTPException(403, "Workspace owner or org admin access required")

    async def _require_workspace_budget_viewer(request: Request, workspace_id: str):
        user = await get_current_user(request)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "owner_id": 1, "org_id": 1, "members": 1})
        if not workspace:
            raise HTTPException(404, "Workspace not found")
        if user.get("platform_role") == "super_admin" or user["user_id"] == workspace.get("owner_id") or user["user_id"] in (workspace.get("members") or []):
            return user, workspace
        raise HTTPException(403, "Workspace access required")

    def _normalize_budget_payload(body: dict):
        budgets = body.get("budgets") or {}
        normalized = {}
        for provider in PLATFORM_KEY_PROVIDERS:
            cfg = budgets.get(provider)
            if not isinstance(cfg, dict):
                continue
            warn = cfg.get("warn_threshold_usd")
            hard = cfg.get("hard_cap_usd")
            enabled = bool(cfg.get("enabled", False))
            if warn is not None:
                warn = float(warn) if warn != "" else None
            if hard is not None:
                hard = float(hard) if hard != "" else None
            if warn is not None and warn < 0:
                raise HTTPException(422, f"{provider}: warn_threshold_usd must be >= 0")
            if hard is not None and hard < 0:
                raise HTTPException(422, f"{provider}: hard_cap_usd must be >= 0")
            if warn is not None and hard is not None and warn > hard:
                raise HTTPException(422, f"{provider}: warn_threshold_usd cannot exceed hard_cap_usd")
            normalized[provider] = {
                "warn_threshold_usd": warn,
                "hard_cap_usd": hard,
                "enabled": enabled,
            }
        return normalized

    async def _get_budget_map(scope_type: str, scope_id: str):
        result = {}
        for provider in sorted(PLATFORM_KEY_PROVIDERS):
            budget = await get_scope_budget(scope_type, scope_id, provider)
            result[provider] = {
                "provider": provider,
                "enabled": bool((budget or {}).get("enabled", False)),
                "warn_threshold_usd": (budget or {}).get("warn_threshold_usd"),
                "hard_cap_usd": (budget or {}).get("hard_cap_usd"),
                "updated_at": (budget or {}).get("updated_at"),
            }
        return result

    # === ADMIN: Set platform keys ===
    @api_router.post("/admin/managed-keys")
    async def set_platform_keys(data: SetPlatformKeys, request: Request):
        """Super admin: set platform-level API keys. Handles both AI provider keys and
        multi-key integrations (e.g., google_drive:GOOGLE_DRIVE_CLIENT_ID)."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin only")
        encrypted_keys = {}
        for key_path, key_value in data.keys.items():
            if not key_value or not key_value.strip() or key_value.startswith("****"):
                continue
            # Accept both "chatgpt" (AI) and "google_drive:GOOGLE_DRIVE_CLIENT_ID" (integration)
            provider = key_path.split(":")[0] if ":" in key_path else key_path
            if provider not in PLATFORM_KEY_PROVIDERS:
                continue
            encrypted_keys[key_path] = encrypt_key(key_value.strip())
        existing = await db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
        current_keys = (existing.get("keys") or {}) if existing else {}
        current_keys.update(encrypted_keys)
        await db.platform_settings.update_one(
            {"setting_id": "managed_keys"},
            {"$set": {"keys": current_keys, "updated_by": user["user_id"]}},
            upsert=True,
        )
        return {"message": "Platform keys updated", "providers": list(set(k.split(":")[0] for k in current_keys.keys()))}

    @api_router.get("/admin/managed-keys")
    async def get_platform_keys(request: Request):
        """Super admin: view which platform keys are configured (AI + integrations)."""
        await _require_super_admin(request)
        settings = await db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
        keys = (settings.get("keys") or {}) if settings else {}
        
        result = {}
        # AI providers (single key)
        ai_providers = PLATFORM_KEY_PROVIDERS - set(INTEGRATION_KEY_MAP.keys())
        for provider in ai_providers:
            encrypted = keys.get(provider)
            if encrypted:
                try:
                    result[provider] = {"configured": True, "masked": mask_key(decrypt_key(encrypted)), "type": "ai"}
                except Exception:
                    result[provider] = {"configured": True, "masked": "****", "type": "ai"}
            else:
                result[provider] = {"configured": False, "masked": "", "type": "ai"}
        
        # Non-AI integrations (multi-key)
        for integration, key_names in INTEGRATION_KEY_MAP.items():
            all_set = True
            for kn in key_names:
                if f"{integration}:{kn}" not in keys:
                    all_set = False
                    break
            result[integration] = {
                "configured": all_set,
                "masked": f"{len(key_names)} keys" if all_set else f"0/{len(key_names)} keys",
                "type": "integration",
                "required_keys": key_names,
            }
        
        return {"providers": result}

    @api_router.get("/admin/managed-keys/budgets")
    async def get_platform_budget_settings(request: Request):
        await _require_super_admin(request)
        return {"scope_type": "platform", "scope_id": PLATFORM_SCOPE_ID, "budgets": await _get_budget_map("platform", PLATFORM_SCOPE_ID)}

    @api_router.put("/admin/managed-keys/budgets")
    async def save_platform_budget_settings(request: Request):
        user = await _require_super_admin(request)
        body = await request.json()
        budgets = _normalize_budget_payload(body)
        for provider, cfg in budgets.items():
            await upsert_scope_budget("platform", PLATFORM_SCOPE_ID, provider, cfg["warn_threshold_usd"], cfg["hard_cap_usd"], cfg["enabled"], user["user_id"])
        return {"scope_type": "platform", "scope_id": PLATFORM_SCOPE_ID, "saved": len(budgets)}

    @api_router.get("/admin/managed-keys/dashboard")
    async def get_platform_budget_dashboard(request: Request):
        await _require_super_admin(request)
        return await get_scope_budget_dashboard("platform", PLATFORM_SCOPE_ID)

    @api_router.get("/admin/managed-keys/alerts")
    async def get_platform_budget_alerts(request: Request, limit: int = 25):
        await _require_super_admin(request)
        return {"alerts": await get_scope_alerts("platform", PLATFORM_SCOPE_ID, limit)}

    @api_router.get("/admin/managed-keys/health")
    async def get_platform_key_health(request: Request):
        await _require_super_admin(request)
        from ai_providers import test_api_key
        from managed_keys import INTEGRATION_KEY_MAP, assess_ai_provider_key_health

        settings = await db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
        keys = (settings.get("keys") or {}) if settings else {}
        ai_providers = sorted(PLATFORM_KEY_PROVIDERS - set(INTEGRATION_KEY_MAP.keys()))
        health = {}

        for provider in ai_providers:
            encrypted = keys.get(provider)
            if not encrypted:
                health[provider] = {"configured": False, "status": "missing", "message": "No platform key configured"}
                continue
            health[provider] = await assess_ai_provider_key_health(provider)

        return {"health": health}

    @api_router.get("/orgs/{org_id}/nexus-ai/budgets")
    async def get_org_budget_settings(org_id: str, request: Request):
        await _require_org_admin(request, org_id)
        return {"scope_type": "org", "scope_id": org_id, "budgets": await _get_budget_map("org", org_id)}

    @api_router.put("/orgs/{org_id}/nexus-ai/budgets")
    async def save_org_budget_settings(org_id: str, request: Request):
        user = await _require_org_admin(request, org_id)
        body = await request.json()
        budgets = _normalize_budget_payload(body)
        for provider, cfg in budgets.items():
            await upsert_scope_budget("org", org_id, provider, cfg["warn_threshold_usd"], cfg["hard_cap_usd"], cfg["enabled"], user["user_id"])
        return {"scope_type": "org", "scope_id": org_id, "saved": len(budgets)}

    @api_router.get("/orgs/{org_id}/nexus-ai/dashboard")
    async def get_org_budget_dashboard(org_id: str, request: Request):
        await _require_org_admin(request, org_id)
        return await get_scope_budget_dashboard("org", org_id)

    @api_router.get("/orgs/{org_id}/nexus-ai/alerts")
    async def get_org_budget_alerts(org_id: str, request: Request, limit: int = 25):
        await _require_org_admin(request, org_id)
        return {"alerts": await get_scope_alerts("org", org_id, limit)}

    @api_router.get("/workspaces/{workspace_id}/nexus-ai/budgets")
    async def get_workspace_budget_settings(workspace_id: str, request: Request):
        await _require_workspace_budget_viewer(request, workspace_id)
        return {"scope_type": "workspace", "scope_id": workspace_id, "budgets": await _get_budget_map("workspace", workspace_id)}

    @api_router.put("/workspaces/{workspace_id}/nexus-ai/budgets")
    async def save_workspace_budget_settings(workspace_id: str, request: Request):
        user, _workspace = await _require_workspace_budget_admin(request, workspace_id)
        body = await request.json()
        budgets = _normalize_budget_payload(body)
        for provider, cfg in budgets.items():
            await upsert_scope_budget("workspace", workspace_id, provider, cfg["warn_threshold_usd"], cfg["hard_cap_usd"], cfg["enabled"], user["user_id"])
        return {"scope_type": "workspace", "scope_id": workspace_id, "saved": len(budgets)}

    @api_router.get("/workspaces/{workspace_id}/nexus-ai/dashboard")
    async def get_workspace_budget_dashboard(workspace_id: str, request: Request):
        await _require_workspace_budget_viewer(request, workspace_id)
        return await get_scope_budget_dashboard("workspace", workspace_id)

    @api_router.get("/workspaces/{workspace_id}/nexus-ai/alerts")
    async def get_workspace_budget_alerts(workspace_id: str, request: Request, limit: int = 25):
        await _require_workspace_budget_viewer(request, workspace_id)
        return {"alerts": await get_scope_alerts("workspace", workspace_id, limit)}

    @api_router.get("/admin/managed-keys/alerts/history")
    async def get_alert_history(request: Request, limit: int = 50, offset: int = 0, alert_type: str = None, provider: str = None):
        """Paginated alert history across all scopes for super admin."""
        await _require_super_admin(request)
        query = {}
        if alert_type:
            query["alert_type"] = alert_type
        if provider:
            query["provider"] = provider
        total = await db.managed_key_budget_alerts.count_documents(query)
        alerts = await db.managed_key_budget_alerts.find(query, {"_id": 0}).sort("last_triggered_at", -1).skip(offset).limit(limit).to_list(limit)
        return {"alerts": alerts, "total": total, "offset": offset, "limit": limit}

    @api_router.put("/admin/managed-keys/alerts/{alert_key}/dismiss")
    async def dismiss_alert(alert_key: str, request: Request):
        """Dismiss/acknowledge a specific budget alert."""
        user = await _require_super_admin(request)
        result = await db.managed_key_budget_alerts.update_one(
            {"alert_key": alert_key},
            {"$set": {"dismissed": True, "dismissed_by": user["user_id"], "dismissed_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Alert not found")
        return {"status": "dismissed"}

    # === USER: Opt-in/out per provider ===
    @api_router.post("/settings/managed-keys/toggle")
    async def toggle_managed_key(data: OptInToggle, request: Request):
        """User: opt in/out of platform keys for a specific provider."""
        user = await get_current_user(request)
        plan = user.get("plan", "free")
        if plan == "free":
            raise HTTPException(403, "Platform keys require a paid plan. Upgrade to Starter or above.")
        if data.provider not in PLATFORM_KEY_PROVIDERS:
            raise HTTPException(400, f"Provider must be one of: {', '.join(PLATFORM_KEY_PROVIDERS)}")
        # Check platform key is actually configured
        settings = await db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
        keys = (settings.get("keys") or {}) if settings else {}
        if data.enabled and data.provider not in keys:
            raise HTTPException(400, f"Platform key for {data.provider} is not configured by admin.")
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {f"managed_keys_optin.{data.provider}": data.enabled}},
        )
        return {"provider": data.provider, "enabled": data.enabled}

    @api_router.get("/settings/managed-keys")
    async def get_managed_key_settings(request: Request):
        """User: get current opt-in status — AI providers + non-AI integrations."""
        user = await get_current_user(request)
        plan = user.get("plan", "free")
        optin = user.get("managed_keys_optin") or {}
        settings = await db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
        stored_keys = (settings.get("keys") or {}) if settings else {}
        
        providers = {}
        # AI providers
        ai_providers = PLATFORM_KEY_PROVIDERS - set(INTEGRATION_KEY_MAP.keys())
        for p in ai_providers:
            providers[p] = {
                "available": p in stored_keys,
                "opted_in": optin.get(p, False),
                "eligible": plan != "free",
                "type": "ai",
            }
        # Non-AI integrations
        for integration, key_names in INTEGRATION_KEY_MAP.items():
            all_set = all(f"{integration}:{kn}" in stored_keys for kn in key_names)
            providers[integration] = {
                "available": all_set,
                "opted_in": optin.get(integration, False),
                "eligible": plan != "free",
                "type": "integration",
            }
        return {
            "providers": providers,
            "plan": plan,
            "plan_credits": PLAN_CREDITS.get(plan, 0),
            "credit_rates": MODEL_CREDIT_RATES,
            "integration_rates": INTEGRATION_CREDIT_RATES,
        }

    # === USER: Credit balance and usage ===
    @api_router.get("/settings/managed-keys/credits")
    async def get_credit_balance(request: Request):
        """User: get current credit balance, usage, and overage."""
        user = await get_current_user(request)
        balance = await check_credits(user["user_id"])
        return balance

    @api_router.get("/settings/managed-keys/usage")
    async def get_usage_history(request: Request):
        """User: get recent managed key usage logs."""
        user = await get_current_user(request)
        logs = await db.managed_key_logs.find(
            {"user_id": user["user_id"]},
            {"_id": 0}
        ).sort("timestamp", -1).to_list(50)
        return {"logs": logs}
