"""AI Provider Billing Dashboard — Per-user and per-workspace cost tracking."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Provider billing dashboard links
PROVIDER_LINKS = {
    "anthropic": {"name": "Anthropic (Claude)", "billing_url": "https://console.anthropic.com/settings/billing", "keys_url": "https://console.anthropic.com/settings/keys"},
    "openai": {"name": "OpenAI (ChatGPT)", "billing_url": "https://platform.openai.com/account/billing", "keys_url": "https://platform.openai.com/api-keys"},
    "gemini": {"name": "Google (Gemini)", "billing_url": "https://console.cloud.google.com/billing", "keys_url": "https://aistudio.google.com/app/apikey"},
    "deepseek": {"name": "DeepSeek", "billing_url": "https://platform.deepseek.com/usage", "keys_url": "https://platform.deepseek.com/api_keys"},
    "xai": {"name": "xAI (Grok)", "billing_url": "https://console.x.ai/billing", "keys_url": "https://console.x.ai/api-keys"},
    "cohere": {"name": "Cohere", "billing_url": "https://dashboard.cohere.com/billing", "keys_url": "https://dashboard.cohere.com/api-keys"},
    "mistral": {"name": "Mistral AI", "billing_url": "https://console.mistral.ai/billing", "keys_url": "https://console.mistral.ai/api-keys"},
    "groq": {"name": "Groq", "billing_url": "https://console.groq.com/settings/billing", "keys_url": "https://console.groq.com/keys"},
    "perplexity": {"name": "Perplexity", "billing_url": "https://www.perplexity.ai/settings/api", "keys_url": "https://www.perplexity.ai/settings/api"},
    "openrouter": {"name": "OpenRouter (Pi, Mercury)", "billing_url": "https://openrouter.ai/settings/credits", "keys_url": "https://openrouter.ai/settings/keys"},
}

# Pricing per 1M tokens (input/output)
from nexus_config import PROVIDER_PRICING


# Map agent keys to provider keys
AGENT_TO_PROVIDER = {
    "claude": "anthropic", "chatgpt": "openai", "gemini": "gemini",
    "deepseek": "deepseek", "grok": "xai", "cohere": "cohere",
    "mistral": "mistral", "groq": "groq", "perplexity": "perplexity",
    "pi": "openrouter", "mercury": "openrouter",
}


def register_ai_billing_routes(api_router, db, get_current_user):

    @api_router.get("/settings/ai-billing")
    async def get_my_ai_billing(request: Request, days: int = 30):
        """Per-user AI provider cost breakdown with billing links."""
        user = await get_current_user(request)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get usage per provider
        pipeline = [
            {"$match": {"user_id": user["user_id"], "timestamp": {"$gte": since}}},
            {"$group": {
                "_id": "$provider",
                "input_tokens": {"$sum": "$input_tokens"},
                "output_tokens": {"$sum": "$output_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "events": {"$sum": 1},
                "errors": {"$sum": {"$cond": [{"$ne": ["$error_type", None]}, 1, 0]}},
                "last_used": {"$max": "$timestamp"},
            }},
            {"$sort": {"total_cost": -1}},
        ]
        usage = await db.reporting_events.aggregate(pipeline).to_list(20)

        # Check which keys the user has configured
        ai_keys = user.get("ai_keys") or {}
        configured_agents = {agent: bool(key) for agent, key in ai_keys.items()}

        # Build response per provider
        providers = []
        total_cost = 0
        for provider_key, info in PROVIDER_LINKS.items():
            provider_usage = next((u for u in usage if u["_id"] == provider_key), None)
            agents = [a for a, p in AGENT_TO_PROVIDER.items() if p == provider_key]
            has_key = any(configured_agents.get(a, False) for a in agents)

            entry = {
                "provider": provider_key,
                "name": info["name"],
                "billing_url": info["billing_url"],
                "keys_url": info["keys_url"],
                "agents": agents,
                "has_key": has_key,
                "usage": None,
            }
            if provider_usage:
                cost = round(provider_usage["total_cost"], 4)
                total_cost += cost
                entry["usage"] = {
                    "input_tokens": provider_usage["input_tokens"],
                    "output_tokens": provider_usage["output_tokens"],
                    "total_tokens": provider_usage["total_tokens"],
                    "estimated_cost_usd": cost,
                    "events": provider_usage["events"],
                    "errors": provider_usage["errors"],
                    "last_used": provider_usage["last_used"],
                }
            providers.append(entry)

        return {
            "period_days": days,
            "total_estimated_cost_usd": round(total_cost, 4),
            "providers": providers,
        }

    @api_router.get("/settings/ai-billing/provider-links")
    async def get_provider_links(request: Request):
        """Get billing and API key URLs for all providers."""
        await get_current_user(request)
        return {"providers": PROVIDER_LINKS}

    @api_router.get("/workspaces/{workspace_id}/ai-billing")
    async def get_workspace_ai_billing(workspace_id: str, request: Request, days: int = 30):
        """Per-workspace AI provider cost breakdown."""
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        pipeline = [
            {"$match": {"workspace_id": workspace_id, "timestamp": {"$gte": since}}},
            {"$group": {
                "_id": {"provider": "$provider", "user_id": "$user_id"},
                "input_tokens": {"$sum": "$input_tokens"},
                "output_tokens": {"$sum": "$output_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "events": {"$sum": 1},
            }},
            {"$sort": {"total_cost": -1}},
        ]
        raw = await db.reporting_events.aggregate(pipeline).to_list(200)

        # Aggregate by provider
        by_provider = {}
        by_user = {}
        for r in raw:
            p = r["_id"]["provider"]
            uid = r["_id"]["user_id"]
            if p not in by_provider:
                by_provider[p] = {"tokens": 0, "cost": 0, "events": 0}
            by_provider[p]["tokens"] += r["total_tokens"]
            by_provider[p]["cost"] += r["total_cost"]
            by_provider[p]["events"] += r["events"]
            if uid not in by_user:
                by_user[uid] = {"tokens": 0, "cost": 0}
            by_user[uid]["tokens"] += r["total_tokens"]
            by_user[uid]["cost"] += r["total_cost"]

        # Enrich users
        top_users = sorted(by_user.items(), key=lambda x: -x[1]["cost"])[:10]
        enriched_users = []
        for uid, data in top_users:
            u = await db.users.find_one({"user_id": uid}, {"_id": 0, "name": 1, "email": 1})
            enriched_users.append({
                "user_id": uid,
                "name": u.get("name", "") if u else "",
                "tokens": data["tokens"],
                "estimated_cost_usd": round(data["cost"], 4),
            })

        return {
            "period_days": days,
            "total_cost_usd": round(sum(d["cost"] for d in by_provider.values()), 4),
            "by_provider": {p: {"tokens": d["tokens"], "cost_usd": round(d["cost"], 4), "events": d["events"],
                                 "billing_url": PROVIDER_LINKS.get(p, {}).get("billing_url", "")}
                            for p, d in sorted(by_provider.items(), key=lambda x: -x[1]["cost"])},
            "top_users": enriched_users,
        }
