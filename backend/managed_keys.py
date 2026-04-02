"""Nexus Managed Keys — Platform-provided AI keys with credit-based billing.

Tenants opt-in per provider. Usage deducts credits. Overages billed at cost + markup.
Core 5 providers: ChatGPT, Claude, Gemini, Mistral, DeepSeek.
"""
import os
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone

from nexus_config import PROVIDER_PRICING

logger = logging.getLogger(__name__)

# ALL platform providers — AI + Non-AI integrations
PLATFORM_KEY_PROVIDERS = {
    # AI Providers (19)
    "chatgpt", "claude", "gemini", "mistral", "deepseek",
    "perplexity", "cohere", "groq", "grok", "mercury",
    "pi", "manus", "qwen", "kimi", "llama", "glm",
    "cursor", "notebooklm", "copilot",
    # Cloud Storage (3)
    "google_drive", "onedrive", "dropbox", "box",
    # Social/Messaging / Publishing / Email (16)
    "telegram", "twitter", "linkedin", "youtube", "tiktok", "instagram",
    "slack", "discord", "msteams", "mattermost", "whatsapp", "signal", "zoom",
    "sendgrid", "resend", "meta", "microsoft",
    # Infrastructure (3)
    "cloudflare_r2", "cloudflare_kv", "cloudflare_ai_gateway",
    # Developer / Payments (2)
    "github", "paypal",
}

# Map managed key names → actual env var / platform_settings key names
INTEGRATION_KEY_MAP = {
    # Cloud Storage (each needs client_id + client_secret)
    "google_drive": ["GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET"],
    "onedrive": ["ONEDRIVE_CLIENT_ID", "ONEDRIVE_CLIENT_SECRET"],
    "dropbox": ["DROPBOX_CLIENT_ID", "DROPBOX_CLIENT_SECRET"],
    "box": ["BOX_CLIENT_ID", "BOX_CLIENT_SECRET"],
    # Social/Messaging
    "telegram": ["TELEGRAM_BOT_TOKEN"],
    "twitter": ["TWITTER_CLIENT_ID", "TWITTER_CLIENT_SECRET"],
    "linkedin": ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"],
    "youtube": ["YOUTUBE_API_KEY"],
    "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"],
    "instagram": ["META_APP_ID", "META_APP_SECRET"],
    "slack": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
    "discord": ["DISCORD_BOT_TOKEN"],
    "msteams": ["MSTEAMS_CLIENT_ID", "MSTEAMS_CLIENT_SECRET"],
    "mattermost": ["MATTERMOST_BOT_TOKEN"],
    "whatsapp": ["WHATSAPP_API_TOKEN"],
    "signal": ["SIGNAL_API_KEY"],
    "zoom": ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"],
    "sendgrid": ["SENDGRID_API_KEY"],
    "resend": ["RESEND_API_KEY"],
    "meta": ["META_APP_ID", "META_APP_SECRET"],
    "microsoft": ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"],
    # Infrastructure
    "cloudflare_r2": ["CF_R2_ACCESS_KEY", "CF_R2_SECRET_KEY", "CF_R2_BUCKET"],
    "cloudflare_kv": ["CF_KV_NAMESPACE_ID", "CF_KV_SYNC_TOKEN"],
    "cloudflare_ai_gateway": ["CF_ACCOUNT_ID", "CF_AI_GATEWAY_KEY"],
    # Developer
    "github": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
    "paypal": ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"],
}

# Credit cost per 1K tokens by AI model
MODEL_CREDIT_RATES = {
    # Tier 1: Premium models
    "claude": {"input": 3.0, "output": 15.0},
    "chatgpt": {"input": 2.0, "output": 6.0},
    "grok": {"input": 2.0, "output": 8.0},
    # Tier 2: Mid-range models
    "gemini": {"input": 0.5, "output": 1.5},
    "mistral": {"input": 1.0, "output": 3.0},
    "perplexity": {"input": 1.0, "output": 3.0},
    "cohere": {"input": 0.5, "output": 2.0},
    "deepseek": {"input": 0.5, "output": 2.0},
    "qwen": {"input": 0.5, "output": 2.0},
    "kimi": {"input": 0.5, "output": 2.0},
    # Tier 3: Fast/cheap models
    "groq": {"input": 0.2, "output": 0.6},
    "mercury": {"input": 0.3, "output": 1.0},
    "llama": {"input": 0.2, "output": 0.6},
    "glm": {"input": 0.3, "output": 1.0},
    "manus": {"input": 1.0, "output": 3.0},
    # Tier 4: OpenRouter proxied
    "pi": {"input": 1.0, "output": 3.0},
    "cursor": {"input": 1.0, "output": 3.0},
    "notebooklm": {"input": 1.0, "output": 3.0},
    "copilot": {"input": 1.0, "output": 3.0},
}

# Flat credit cost per API call for non-AI integrations
INTEGRATION_CREDIT_RATES = {
    "google_drive": 0.5,      # per API call
    "onedrive": 0.5,
    "dropbox": 0.5,
    "box": 0.5,
    "telegram": 0.2,          # per message
    "twitter": 1.0,           # per post
    "linkedin": 1.0,          # per post
    "youtube": 1.0,
    "tiktok": 1.0,
    "instagram": 1.0,
    "slack": 0.2,
    "discord": 0.2,
    "msteams": 0.3,
    "mattermost": 0.2,
    "whatsapp": 0.4,
    "signal": 0.4,
    "zoom": 0.5,
    "sendgrid": 0.2,
    "resend": 0.2,
    "meta": 0.5,
    "microsoft": 0.5,
    "cloudflare_r2": 0.1,     # per storage op
    "cloudflare_kv": 0.05,    # per KV op
    "cloudflare_ai_gateway": 0.0,  # free (just proxying)
    "github": 0.2,            # per API call
    "paypal": 0.5,
}

# Plan credit allocations
PLAN_CREDITS = {
    "free": 0,           # No platform key access
    "starter": 1000,     # 1,000 credits/month
    "pro": 5000,         # 5,000 credits/month
    "team": 5000,        # 5,000 credits/user/month
    "enterprise": 50000, # 50,000 credits/month
}

# Overage markup (30% on top of cost)
OVERAGE_MARKUP = 0.30

# Safety cap: max daily credit spend before throttle
DAILY_SAFETY_CAP = {
    "starter": 200,
    "pro": 1000,
    "team": 1000,
    "enterprise": 10000,
}

_db = None
PLATFORM_SCOPE_ID = "platform"

AI_PROVIDER_TO_BILLING = {
    "chatgpt": "openai",
    "claude": "anthropic",
    "gemini": "gemini",
    "deepseek": "deepseek",
    "grok": "xai",
    "cohere": "cohere",
    "mistral": "mistral",
    "groq": "groq",
    "perplexity": "perplexity",
    "pi": "openrouter",
    "mercury": "openrouter",
    "qwen": "alibaba",
    "kimi": "moonshot",
    "llama": "meta",
    "glm": "zhipu",
    "cursor": "openrouter",
    "notebooklm": "openrouter",
    "copilot": "openrouter",
    "manus": "openai",
}

INTEGRATION_RATE_USD = {
    provider: round(rate * 0.01, 4)
    for provider, rate in INTEGRATION_CREDIT_RATES.items()
}

def init_managed_keys(db):
    global _db
    _db = db


def is_placeholder_key(api_key: str | None) -> bool:
    key = (api_key or "").strip().lower()
    if not key:
        return False
    placeholder_markers = [
        "sk-test-",
        "test-key",
        "placeholder",
        "your-key",
        "demo-key",
        "example-key",
    ]
    return any(marker in key for marker in placeholder_markers)


async def should_bypass_budget(user_id: str | None) -> bool:
    if not user_id or _db is None:
        return False
    user = await _db.users.find_one({"user_id": user_id}, {"_id": 0, "plan": 1, "platform_role": 1})
    if not user:
        return False
    return user.get("platform_role") == "super_admin" or user.get("plan") == "enterprise"


def estimate_ai_cost_usd(provider: str, tokens_in: int, tokens_out: int) -> float:
    billing_provider = AI_PROVIDER_TO_BILLING.get(provider, provider)
    rates = PROVIDER_PRICING.get(billing_provider, {"input": 5.0, "output": 15.0})
    return round((tokens_in * rates["input"] + tokens_out * rates["output"]) / 1_000_000, 6)


def estimate_integration_cost_usd(provider: str, call_count: int = 1) -> float:
    return round(INTEGRATION_RATE_USD.get(provider, 0.005) * max(call_count, 1), 6)


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _budget_scope_filter(scope_type: str, scope_id: str) -> dict:
    if scope_type == "workspace":
        return {"workspace_id": scope_id}
    if scope_type == "org":
        return {"org_id": scope_id}
    return {}


async def get_scope_budget(scope_type: str, scope_id: str, provider: str | None = None):
    query = {"scope_type": scope_type, "scope_id": scope_id}
    if provider:
        query["provider"] = provider
    return await _db.scope_integration_budgets.find_one(query, {"_id": 0})


async def upsert_scope_budget(scope_type: str, scope_id: str, provider: str, warn_threshold_usd: Optional[float], hard_cap_usd: Optional[float], enabled: bool, updated_by: str):
    doc = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "provider": provider,
        "warn_threshold_usd": warn_threshold_usd,
        "hard_cap_usd": hard_cap_usd,
        "enabled": enabled,
        "updated_by": updated_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.scope_integration_budgets.update_one(
        {"scope_type": scope_type, "scope_id": scope_id, "provider": provider},
        {"$set": doc, "$setOnInsert": {"budget_id": f"mbg_{uuid.uuid4().hex[:12]}"}},
        upsert=True,
    )
    return doc


async def get_scope_spend_usd(scope_type: str, scope_id: str, provider: str | None = None, month_key: str | None = None) -> float:
    if month_key is None:
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    query = {"month_key": month_key, **_budget_scope_filter(scope_type, scope_id)}
    if provider:
        query["provider"] = provider
    pipeline = [
        {"$match": query},
        {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}},
    ]
    rows = await _db.managed_key_usage_events.aggregate(pipeline).to_list(1)
    return round(rows[0]["total"], 6) if rows else 0.0


async def emit_budget_alert(provider: str, scope_type: str, scope_id: str, alert_type: str, current_spend_usd: float, threshold_usd: float | None = None, user_id: str | None = None, workspace_id: str | None = None, org_id: str | None = None, message: str | None = None):
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    alert_key = f"{scope_type}:{scope_id}:{provider}:{alert_type}:{month_key}"
    existing = await _db.managed_key_budget_alerts.find_one({"alert_key": alert_key}, {"_id": 0, "alert_id": 1})
    payload = {
        "alert_key": alert_key,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "provider": provider,
        "alert_type": alert_type,
        "current_spend_usd": round(current_spend_usd, 6),
        "threshold_usd": threshold_usd,
        "workspace_id": workspace_id,
        "org_id": org_id,
        "last_triggered_at": now.isoformat(),
        "month_key": month_key,
        "message": message or "",
    }
    is_new = not bool(existing)
    await _db.managed_key_budget_alerts.update_one(
        {"alert_key": alert_key},
        {"$set": payload, "$setOnInsert": {"alert_id": f"mkal_{uuid.uuid4().hex[:12]}", "created_at": now.isoformat()}},
        upsert=True,
    )
    if user_id and is_new:
        try:
            try:
                from routes.routes_notifications import create_notification
            except ImportError:
                from routes_notifications import create_notification
            title = f"Nexus AI budget {alert_type}"
            await create_notification(
                _db,
                user_id=user_id,
                notification_type="budget_alert",
                title=title,
                message=message or f"{scope_type.capitalize()} budget alert for {provider}",
                workspace_id=workspace_id,
                channel_id=None,
                link="/settings?tab=nexus-keys",
                metadata={"provider": provider, "scope_type": scope_type, "scope_id": scope_id, "alert_type": alert_type, "current_spend_usd": round(current_spend_usd, 6), "threshold_usd": threshold_usd},
            )
        except Exception as exc:
            logger.debug(f"Budget notification creation failed: {exc}")
    return is_new


async def get_scope_alerts(scope_type: str, scope_id: str, limit: int = 25):
    alerts = await _db.managed_key_budget_alerts.find(
        {"scope_type": scope_type, "scope_id": scope_id},
        {"_id": 0}
    ).sort("last_triggered_at", -1).limit(limit).to_list(limit)
    return alerts


async def resolve_effective_budget(provider: str, workspace_id: str | None = None, org_id: str | None = None):
    scopes = []
    if workspace_id:
        scopes.append(("workspace", workspace_id))
    if org_id:
        scopes.append(("org", org_id))
    scopes.append(("platform", PLATFORM_SCOPE_ID))
    for scope_type, scope_id in scopes:
        budget = await get_scope_budget(scope_type, scope_id, provider)
        if budget and budget.get("enabled"):
            return budget
    return None


async def check_usage_budget(provider: str, estimated_cost_usd: float, workspace_id: str | None = None, org_id: str | None = None, user_id: str | None = None):
    if await should_bypass_budget(user_id):
        return {
            "blocked": False,
            "warn": False,
            "scope_type": None,
            "scope_id": None,
            "current_spend_usd": 0.0,
            "projected_spend_usd": estimated_cost_usd,
            "bypassed": True,
        }
    budget = await resolve_effective_budget(provider, workspace_id, org_id)
    if not budget:
        return {
            "blocked": False,
            "warn": False,
            "scope_type": None,
            "scope_id": None,
            "current_spend_usd": 0.0,
            "projected_spend_usd": estimated_cost_usd,
        }

    current_spend = await get_scope_spend_usd(budget["scope_type"], budget["scope_id"], provider)
    projected_spend = round(current_spend + max(estimated_cost_usd, 0), 6)
    warn_threshold = budget.get("warn_threshold_usd")
    hard_cap = budget.get("hard_cap_usd")
    warn = bool(warn_threshold and current_spend < warn_threshold <= projected_spend)
    blocked = bool(hard_cap and projected_spend > hard_cap)
    return {
        "blocked": blocked,
        "warn": warn,
        "scope_type": budget["scope_type"],
        "scope_id": budget["scope_id"],
        "warn_threshold_usd": warn_threshold,
        "hard_cap_usd": hard_cap,
        "current_spend_usd": current_spend,
        "projected_spend_usd": projected_spend,
    }


async def record_usage_event(provider: str, cost_usd: float, user_id: str | None = None, workspace_id: str | None = None, org_id: str | None = None, usage_type: str = "ai", key_source: str | None = None, tokens_in: int = 0, tokens_out: int = 0, call_count: int = 0, metadata: Optional[dict] = None):
    now = datetime.now(timezone.utc)
    doc = {
        "event_id": f"mkevt_{uuid.uuid4().hex[:16]}",
        "provider": provider,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "org_id": org_id,
        "usage_type": usage_type,
        "key_source": key_source,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "call_count": call_count,
        "cost_usd": round(cost_usd, 6),
        "timestamp": now.isoformat(),
        "date_key": now.strftime("%Y-%m-%d"),
        "month_key": now.strftime("%Y-%m"),
        "metadata": metadata or {},
    }
    await _db.managed_key_usage_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def get_scope_budget_dashboard(scope_type: str, scope_id: str):
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    scope_filter = _budget_scope_filter(scope_type, scope_id)
    pipeline = [
        {"$match": {"month_key": month_key, **scope_filter}},
        {"$group": {"_id": "$provider", "cost_usd": {"$sum": "$cost_usd"}, "events": {"$sum": 1}, "tokens_in": {"$sum": "$tokens_in"}, "tokens_out": {"$sum": "$tokens_out"}, "call_count": {"$sum": "$call_count"}}},
    ]
    rows = await _db.managed_key_usage_events.aggregate(pipeline).to_list(200)
    usage_map = {row["_id"]: row for row in rows if row.get("_id")}
    budget_docs = await _db.scope_integration_budgets.find({"scope_type": scope_type, "scope_id": scope_id}, {"_id": 0}).to_list(200)
    budget_map = {doc["provider"]: doc for doc in budget_docs}

    providers = {}
    total_cost = 0.0
    total_events = 0
    for provider in sorted(PLATFORM_KEY_PROVIDERS):
        usage = usage_map.get(provider) or {}
        budget = budget_map.get(provider) or {}
        cost = round(usage.get("cost_usd", 0.0), 6)
        total_cost += cost
        total_events += usage.get("events", 0)
        hard_cap = budget.get("hard_cap_usd")
        warn_threshold = budget.get("warn_threshold_usd")
        status = "ok"
        if hard_cap and cost >= hard_cap:
            status = "blocked"
        elif warn_threshold and cost >= warn_threshold:
            status = "warning"
        providers[provider] = {
            "provider": provider,
            "current_cost_usd": cost,
            "events": usage.get("events", 0),
            "tokens_in": usage.get("tokens_in", 0),
            "tokens_out": usage.get("tokens_out", 0),
            "call_count": usage.get("call_count", 0),
            "enabled": budget.get("enabled", False),
            "warn_threshold_usd": warn_threshold,
            "hard_cap_usd": hard_cap,
            "status": status,
        }

    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "month_key": month_key,
        "total_cost_usd": round(total_cost, 6),
        "total_events": total_events,
        "providers": providers,
    }


async def assess_ai_provider_key_health(provider: str) -> dict:
    if provider not in PLATFORM_KEY_PROVIDERS:
        return {"configured": False, "status": "missing", "message": "Provider not eligible"}
    settings = await _db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0}) if _db else None
    keys = (settings.get("keys") or {}) if settings else {}
    encrypted = keys.get(provider)
    if not encrypted:
        return {"configured": False, "status": "missing", "message": "No platform key configured"}
    try:
        try:
            from routes_ai_keys import decrypt_key
        except ImportError:
            from routes.routes_ai_keys import decrypt_key
        decrypted = decrypt_key(encrypted)
    except Exception:
        return {"configured": True, "status": "invalid", "message": "Could not decrypt key"}

    if is_placeholder_key(decrypted):
        return {"configured": True, "status": "placeholder", "message": "Placeholder/test key detected"}

    try:
        from ai_providers import test_api_key
        result = await test_api_key(provider, decrypted)
        if result.get("success"):
            return {"configured": True, "status": "healthy", "message": result.get("message", "OK")}
        return {"configured": True, "status": "invalid", "message": result.get("error", "Unknown error")}
    except Exception as exc:
        return {"configured": True, "status": "invalid", "message": str(exc)[:200]}


async def get_platform_key(provider: str) -> str | None:
    """Get the platform-level API key for a provider (set by Super Admin)."""
    global _db
    if _db is None:
        return None
    if provider not in PLATFORM_KEY_PROVIDERS:
        return None
    settings = await _db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
    if not settings:
        return None
    keys = settings.get("keys") or {}
    encrypted = keys.get(provider)
    if not encrypted:
        return None
    try:
        try:
            from routes_ai_keys import decrypt_key
        except ImportError:
            from routes.routes_ai_keys import decrypt_key
        decrypted = decrypt_key(encrypted)
        if is_placeholder_key(decrypted):
            logger.warning(f"Ignoring placeholder platform key for {provider}")
            return None
        return decrypted
    except Exception:
        return None


async def is_user_opted_in(user_id: str, provider: str) -> bool:
    """Check if user has opted in to platform keys for this provider."""
    user = await _db.users.find_one({"user_id": user_id}, {"_id": 0, "managed_keys_optin": 1, "plan": 1})
    if not user:
        return False
    plan = user.get("plan", "free")
    if plan == "free":
        return False  # Free users must BYOK
    optin = user.get("managed_keys_optin") or {}
    return optin.get(provider, False)


async def check_credits(user_id: str) -> dict:
    """Check user's credit balance and usage. W7: Never return None."""
    if not _db:
        return {"credits_total": 0, "credits_used": 0, "credits_remaining": 0,
                "overage_cost_usd": 0, "daily_used": 0, "plan": "free"}
    try:
        user = await _db.users.find_one({"user_id": user_id}, {"_id": 0, "plan": 1})
    except Exception:
        user = None
    plan = (user.get("plan") or "free") if user else "free"
    monthly_allocation = PLAN_CREDITS.get(plan, 0)

    usage = await _db.managed_key_usage.find_one({"user_id": user_id}, {"_id": 0})
    if not usage:
        return {
            "credits_total": monthly_allocation,
            "credits_used": 0,
            "credits_remaining": monthly_allocation,
            "overage_cost_usd": 0,
            "daily_used": 0,
            "plan": plan,
        }

    # Check if we need to reset (new month)
    reset_date = usage.get("reset_date", "")
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    if not reset_date or not reset_date.startswith(current_month):
        await _db.managed_key_usage.update_one(
            {"user_id": user_id},
            {"$set": {"credits_used": 0, "overage_cost_usd": 0, "daily_used": 0,
                      "daily_date": now.strftime("%Y-%m-%d"),
                      "reset_date": now.isoformat()}},
        )
        return {
            "credits_total": monthly_allocation,
            "credits_used": 0,
            "credits_remaining": monthly_allocation,
            "overage_cost_usd": 0,
            "daily_used": 0,
            "plan": plan,
        }

    credits_used = usage.get("credits_used", 0)
    daily_date = usage.get("daily_date", "")
    daily_used = usage.get("daily_used", 0) if daily_date == now.strftime("%Y-%m-%d") else 0

    return {
        "credits_total": monthly_allocation,
        "credits_used": credits_used,
        "credits_remaining": max(0, monthly_allocation - credits_used),
        "overage_cost_usd": usage.get("overage_cost_usd", 0),
        "daily_used": daily_used,
        "plan": plan,
    }


async def check_safety_cap(user_id: str, plan: str) -> bool:
    """Check if user hit the daily safety cap. Returns True if OK to proceed."""
    cap = DAILY_SAFETY_CAP.get(plan, 200)
    usage = await _db.managed_key_usage.find_one({"user_id": user_id}, {"_id": 0})
    if not usage:
        return True
    now = datetime.now(timezone.utc)
    daily_date = usage.get("daily_date", "")
    if daily_date != now.strftime("%Y-%m-%d"):
        return True
    return (usage.get("daily_used", 0)) < cap


async def deduct_credits(user_id: str, provider: str, tokens_in: int, tokens_out: int):
    """Deduct credits based on model usage. Tracks overage at cost + markup."""
    rates = MODEL_CREDIT_RATES.get(provider, {"input": 1.0, "output": 3.0})
    credits = (tokens_in / 1000) * rates["input"] + (tokens_out / 1000) * rates["output"]
    credits = round(credits, 2)

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # Get current balance
    balance = await check_credits(user_id)
    remaining = balance["credits_remaining"]

    update = {
        "$inc": {"credits_used": credits, "daily_used": credits, "total_requests": 1},
        "$set": {"last_used": now.isoformat()},
    }

    # If over credit allocation, track overage cost
    if credits > remaining:
        overage_credits = credits - max(remaining, 0)
        overage_usd = round(overage_credits * 0.01 * (1 + OVERAGE_MARKUP), 4)  # $0.01 per credit + markup
        update["$inc"]["overage_cost_usd"] = overage_usd

    # Reset daily counter if new day
    usage = await _db.managed_key_usage.find_one({"user_id": user_id}, {"_id": 0})
    if usage and usage.get("daily_date") != today:
        # T1: Remove daily_used from $inc to avoid MongoDB conflict with $set
        del update["$inc"]["daily_used"]
        update["$set"]["daily_used"] = credits
        update["$set"]["daily_date"] = today

    await _db.managed_key_usage.update_one(
        {"user_id": user_id},
        {**update, "$setOnInsert": {"reset_date": now.isoformat()}},
        upsert=True,
    )

    # Log the usage
    await _db.managed_key_logs.insert_one({
        "user_id": user_id, "provider": provider,
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "credits_deducted": credits, "timestamp": now.isoformat(),
    })

    return credits


async def resolve_platform_key(user_id: str, provider: str) -> tuple:
    """Resolve platform key for a user. Returns (api_key, source) or (None, reason).
    
    Resolution order:
    1. Check provider is in core 5
    2. Check user opted in
    3. Check platform key exists
    4. Check credits / safety cap
    5. Return key
    """
    if provider not in PLATFORM_KEY_PROVIDERS:
        return None, "not_eligible"

    if not await is_user_opted_in(user_id, provider):
        return None, "not_opted_in"

    platform_key = await get_platform_key(provider)
    if not platform_key:
        return None, "no_platform_key"

    balance = await check_credits(user_id)
    # T2: Block non-enterprise users at 0 credits (enterprise gets overage billing)
    if balance["credits_remaining"] <= 0 and balance["plan"] != "enterprise":
        return None, "credits_exhausted"
    if not await check_safety_cap(user_id, balance["plan"]):
        return None, "safety_cap_reached"

    return platform_key, "nexus_managed"


async def resolve_integration_keys(user_id: str, integration: str) -> tuple:
    """Resolve platform keys for a non-AI integration.
    Returns (dict_of_keys, source) or (None, reason).
    For multi-key integrations (OAuth), returns all required keys.
    """
    if integration not in INTEGRATION_KEY_MAP:
        return None, "not_eligible"

    if not await is_user_opted_in(user_id, integration):
        return None, "not_opted_in"

    balance = await check_credits(user_id)
    if balance["credits_remaining"] <= 0 and balance["plan"] != "enterprise":
        return None, "credits_exhausted"

    # Get all required keys for this integration
    key_names = INTEGRATION_KEY_MAP[integration]
    settings = await _db.platform_settings.find_one({"setting_id": "managed_keys"}, {"_id": 0})
    if not settings:
        return None, "no_platform_keys"

    stored_keys = settings.get("keys") or {}
    result = {}
    try:
        try:
            from routes_ai_keys import decrypt_key
        except ImportError:
            from routes.routes_ai_keys import decrypt_key
        for key_name in key_names:
            # Keys stored as integration:key_name
            stored = stored_keys.get(f"{integration}:{key_name}")
            if stored:
                result[key_name] = decrypt_key(stored)
            else:
                return None, f"missing_key:{key_name}"
    except Exception as e:
        return None, f"decrypt_error:{e}"

    return result, "nexus_managed"


async def deduct_integration_credits(user_id: str, integration: str, call_count: int = 1):
    """Deduct flat-rate credits for non-AI integration usage."""
    rate = INTEGRATION_CREDIT_RATES.get(integration, 0.5)
    credits = round(rate * call_count, 2)
    if credits <= 0:
        return 0

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    update = {
        "$inc": {"credits_used": credits, "daily_used": credits, "total_requests": call_count},
        "$set": {"last_used": now.isoformat()},
    }

    usage = await _db.managed_key_usage.find_one({"user_id": user_id}, {"_id": 0})
    if usage and usage.get("daily_date") != today:
        del update["$inc"]["daily_used"]
        update["$set"]["daily_used"] = credits
        update["$set"]["daily_date"] = today

    await _db.managed_key_usage.update_one(
        {"user_id": user_id},
        {**update, "$setOnInsert": {"reset_date": now.isoformat()}},
        upsert=True,
    )

    await _db.managed_key_logs.insert_one({
        "user_id": user_id, "provider": integration,
        "tokens_in": 0, "tokens_out": 0,
        "credits_deducted": credits, "call_count": call_count,
        "timestamp": now.isoformat(),
    })

    return credits
