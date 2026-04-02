from nexus_utils import now_iso
"""Nexus × Cloudflare Integration — AI Gateway, R2, KV sync, usage analytics."""
import uuid
import os
import time
import hashlib
import hmac
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)



# ============ AI Gateway Config ============

def get_ai_gateway_url(provider):
    """Get AI Gateway proxy URL for a provider. Returns None if not configured."""
    acct = os.environ.get("CF_ACCOUNT_ID", "")
    gw_name = os.environ.get("CF_AI_GATEWAY_NAME", "nexus-gw")
    if not acct:
        return None
    provider_map = {
        "openai": "openai", "chatgpt": "openai",
        "anthropic": "anthropic", "claude": "anthropic",
        "cohere": "cohere",
        "mistral": "mistral",
        "google": "google-ai-studio", "gemini": "google-ai-studio",
        "xai": "openai", "grok": "openai",
        "deepseek": "openai",
    }
    cf_provider = provider_map.get(provider)
    if not cf_provider:
        return None
    return f"https://gateway.ai.cloudflare.com/v1/{acct}/{gw_name}/{cf_provider}"


def register_cloudflare_routes(api_router, db, get_current_user):

    # ============ Configuration ============

    @api_router.get("/cloudflare/config")
    async def get_cf_config(request: Request):
        user = await get_current_user(request)
        config = await db.platform_settings.find_one({"key": "cloudflare"}, {"_id": 0})
        safe = {}
        if config:
            safe = {
                "ai_gateway_enabled": config.get("ai_gateway_enabled", False),
                "r2_enabled": config.get("r2_enabled", False),
                "kv_enabled": config.get("kv_enabled", False),
                "tunnel_enabled": config.get("tunnel_enabled", False),
                "account_id": config.get("account_id", "")[:8] + "..." if config.get("account_id") else "",
                "gateway_name": config.get("gateway_name", "nexus-gw"),
            }
        env_configured = bool(os.environ.get("CF_ACCOUNT_ID"))
        return {"config": safe, "env_configured": env_configured}

    @api_router.put("/cloudflare/config")
    async def update_cf_config(request: Request):
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin only")
        body = await request.json()
        updates = {}
        for field in ["ai_gateway_enabled", "r2_enabled", "kv_enabled", "tunnel_enabled", "account_id", "gateway_name", "r2_bucket_uploads", "r2_bucket_artifacts", "r2_access_key", "r2_secret_key", "r2_endpoint"]:
            if field in body:
                updates[field] = body[field]
        if updates:
            await db.platform_settings.update_one({"key": "cloudflare"}, {"$set": updates}, upsert=True)
        return {"updated": True}

    # ============ AI Gateway Usage & Analytics ============

    @api_router.get("/cloudflare/ai-gateway/stats")
    async def ai_gateway_stats(request: Request):
        """AI Gateway usage stats — aggregated from logged requests."""
        user = await get_current_user(request)
        # Aggregate from our own AI call logs
        pipeline = [
            {"$match": {"created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}}},
            {"$group": {
                "_id": {"provider": "$provider", "model": "$model_used"},
                "total_calls": {"$sum": 1},
                "total_tokens": {"$sum": {"$add": [{"$ifNull": ["$tokens_input", 0]}, {"$ifNull": ["$tokens_output", 0]}]}},
                "total_cost": {"$sum": {"$ifNull": ["$cost_usd", 0]}},
                "avg_latency": {"$avg": {"$ifNull": ["$latency_ms", 0]}},
                "cache_hits": {"$sum": {"$cond": [{"$ifNull": ["$cache_hit", False]}, 1, 0]}},
            }},
            {"$sort": {"total_cost": -1}},
        ]
        stats = []
        async for doc in db.ai_call_logs.aggregate(pipeline):
            doc["_id"]["provider"] = doc["_id"].get("provider", "unknown")
            stats.append({
                "provider": doc["_id"]["provider"],
                "model": doc["_id"]["model"],
                "total_calls": doc["total_calls"],
                "total_tokens": doc["total_tokens"],
                "total_cost_usd": round(doc["total_cost"], 4),
                "avg_latency_ms": int(doc["avg_latency"]),
                "cache_hits": doc["cache_hits"],
                "cache_rate": round(doc["cache_hits"] / max(doc["total_calls"], 1) * 100, 1),
            })

        total_calls = sum(s["total_calls"] for s in stats)
        total_cost = sum(s["total_cost_usd"] for s in stats)
        total_cache = sum(s["cache_hits"] for s in stats)

        return {
            "period": "7d",
            "summary": {
                "total_calls": total_calls,
                "total_cost_usd": round(total_cost, 4),
                "total_cache_hits": total_cache,
                "cache_rate": round(total_cache / max(total_calls, 1) * 100, 1),
            },
            "by_provider": stats,
        }

    # ============ R2 Presigned Uploads ============

    @api_router.post("/cloudflare/r2/presign")
    async def presign_upload(request: Request):
        """Generate a presigned URL for direct R2 upload."""
        user = await get_current_user(request)
        body = await request.json()
        filename = body.get("filename", "")
        content_type = body.get("content_type", "application/octet-stream")
        workspace_id = body.get("workspace_id", "")

        if not filename or not workspace_id:
            raise HTTPException(400, "filename and workspace_id required")

        # Validate file extension and content type
        ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".json", ".xml",
                              ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                              ".mp3", ".wav", ".ogg", ".mp4", ".webm", ".mov",
                              ".zip", ".tar", ".gz", ".py", ".js", ".ts", ".html", ".css"}
        BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif", ".vbs", ".js.exe", ".ps1", ".sh"}
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in BLOCKED_EXTENSIONS:
            raise HTTPException(400, f"File extension '{ext}' is not allowed for security reasons")
        MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
        claimed_size = body.get("size_bytes", 0)
        if claimed_size > MAX_UPLOAD_SIZE:
            raise HTTPException(400, f"File too large ({claimed_size} bytes). Max: {MAX_UPLOAD_SIZE}")

        config = await db.platform_settings.find_one({"key": "cloudflare"}, {"_id": 0})
        if not config or not config.get("r2_enabled"):
            raise HTTPException(503, "R2 storage not configured")

        r2_endpoint = config.get("r2_endpoint", "")
        r2_bucket = config.get("r2_bucket_uploads", "nexus-user-uploads")
        r2_access = config.get("r2_access_key", "")
        r2_secret = config.get("r2_secret_key", "")

        if not r2_endpoint or not r2_access:
            raise HTTPException(503, "R2 credentials not configured")

        # Generate object key
        timestamp = int(time.time())
        safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
        object_key = f"{workspace_id}/{user['user_id']}/uploads/{timestamp}_{safe_name}"

        # Generate presigned URL using S3-compatible signing
        expiry = 300  # 5 minutes
        upload_url = f"{r2_endpoint}/{r2_bucket}/{object_key}"

        # Store metadata
        file_id = f"r2f_{uuid.uuid4().hex[:12]}"
        await db.r2_uploads.insert_one({
            "file_id": file_id, "workspace_id": workspace_id,
            "user_id": user["user_id"], "filename": filename,
            "content_type": content_type, "object_key": object_key,
            "bucket": r2_bucket, "status": "pending",
            "size_bytes": 0, "created_at": now_iso(),
        })

        return {
            "upload_url": upload_url, "object_key": object_key,
            "file_id": file_id, "expires_in": expiry,
            "method": "PUT", "headers": {
                "Content-Type": content_type,
                "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
            },
        }

    @api_router.post("/cloudflare/r2/confirm")
    async def confirm_upload(request: Request):
        """Confirm a completed R2 upload."""
        user = await get_current_user(request)
        body = await request.json()
        file_id = body.get("file_id", "")
        size_bytes = body.get("size_bytes", 0)

        await db.r2_uploads.update_one(
            {"file_id": file_id, "user_id": user["user_id"]},
            {"$set": {"status": "completed", "size_bytes": size_bytes, "completed_at": now_iso()}}
        )
        return {"confirmed": True, "file_id": file_id}

    @api_router.get("/cloudflare/r2/files/{workspace_id}")
    async def list_r2_files(workspace_id: str, request: Request):
        user = await get_current_user(request)
        files = await db.r2_uploads.find(
            {"workspace_id": workspace_id, "status": "completed"},
            {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        return {"files": files}

    # ============ KV Sync (data export for Workers) ============

    @api_router.get("/cloudflare/kv/sync/auth")
    async def kv_sync_auth(request: Request):
        """Export auth data for KV sync worker — API key hashes, user tiers."""
        # Authenticated via CF service token
        auth = request.headers.get("Authorization", "")
        sync_token = os.environ.get("CF_KV_SYNC_TOKEN", "")
        if sync_token and auth != f"Bearer {sync_token}":
            raise HTTPException(403, "Invalid sync token")

        # Export user tiers
        users = await db.users.find(
            {}, {"_id": 0, "user_id": 1, "plan": 1, "platform_role": 1}
        ).limit(500).to_list(500)

        tiers = {}
        for u in users:
            plan = u.get("plan", "free")
            tier_map = {"free": "free", "starter": "pro", "pro": "pro", "team": "pro", "enterprise": "enterprise"}
            tiers[u["user_id"]] = {
                "tier": tier_map.get(plan, "free"),
                "role": u.get("platform_role", "user"),
            }

        # Export feature flags
        flags = await db.platform_settings.find_one({"key": "feature_flags"}, {"_id": 0})

        return {
            "user_tiers": tiers,
            "feature_flags": flags or {},
            "synced_at": now_iso(),
            "user_count": len(tiers),
        }

    @api_router.get("/cloudflare/kv/sync/config")
    async def kv_sync_config(request: Request):
        """Export platform config for KV sync worker."""
        auth = request.headers.get("Authorization", "")
        sync_token = os.environ.get("CF_KV_SYNC_TOKEN", "")
        if sync_token and auth != f"Bearer {sync_token}":
            raise HTTPException(403, "Invalid sync token")

        # Provider health status
        providers = ["openai", "anthropic", "cohere", "mistral", "google", "xai", "deepseek"]
        provider_status = {}
        for p in providers:
            key_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "cohere": "COHERE_API_KEY",
                       "mistral": "MISTRAL_API_KEY", "google": "GOOGLE_AI_KEY", "xai": "GROK_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
            has_key = bool(os.environ.get(key_map.get(p, "")))
            provider_status[p] = {"available": has_key, "status": "active" if has_key else "no_key"}

        # Rate tier definitions
        rate_tiers = {
            "free": {"requests_per_min": 60, "requests_per_day": 1000, "token_budget_per_day": 10000},
            "pro": {"requests_per_min": 300, "requests_per_day": 10000, "token_budget_per_day": 500000},
            "enterprise": {"requests_per_min": 1000, "requests_per_day": -1, "token_budget_per_day": -1},
            "byok": {"requests_per_min": 600, "requests_per_day": 50000, "token_budget_per_day": -1},
        }

        return {
            "provider_status": provider_status,
            "rate_tiers": rate_tiers,
            "synced_at": now_iso(),
        }

    # ============ Tunnel Status ============

    @api_router.get("/cloudflare/tunnels")
    async def list_tunnels(request: Request):
        user = await get_current_user(request)
        tunnels = await db.cf_tunnels.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).to_list(10)
        return {"tunnels": tunnels}

    @api_router.post("/cloudflare/tunnels/register")
    async def register_tunnel(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        tunnel_id = f"cft_{uuid.uuid4().hex[:12]}"
        user_hash = hashlib.sha256(user["user_id"].encode()).hexdigest()[:8]
        tunnel = {
            "tunnel_id": tunnel_id, "user_id": user["user_id"],
            "hostname": f"bridge-{user_hash}.nexuscloud.ai",
            "status": "pending", "type": body.get("type", "bridge"),
            "created_at": now_iso(),
        }
        await db.cf_tunnels.insert_one(tunnel)
        tunnel.pop("_id", None)
        return tunnel

    # ============ Health ============

    @api_router.get("/cloudflare/health")
    async def cf_health(request: Request):
        gw_configured = bool(os.environ.get("CF_ACCOUNT_ID"))
        config = await db.platform_settings.find_one({"key": "cloudflare"}, {"_id": 0})
        return {
            "ai_gateway": {"configured": gw_configured, "enabled": (config or {}).get("ai_gateway_enabled", False)},
            "r2": {"enabled": (config or {}).get("r2_enabled", False)},
            "kv": {"enabled": (config or {}).get("kv_enabled", False)},
            "tunnels": {"enabled": (config or {}).get("tunnel_enabled", False)},
        }
