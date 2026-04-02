from nexus_utils import validate_external_url, now_iso
"""Social Media Publishing — OAuth connections + publishing for YouTube, TikTok, Instagram.

Provides OAuth connection management, per-platform publishing, and publish job tracking.
"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



SOCIAL_PROVIDERS = {
    "youtube": {
        "name": "YouTube", "icon": "youtube",
        "client_id_key": "YOUTUBE_API_KEY",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"],
        "upload_url": "https://www.googleapis.com/upload/youtube/v3/videos",
    },
    "tiktok": {
        "name": "TikTok", "icon": "tiktok",
        "client_id_key": "TIKTOK_CLIENT_KEY",
        "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "scopes": ["video.publish", "video.upload"],
        "upload_init_url": "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
    },
    "instagram": {
        "name": "Instagram", "icon": "instagram",
        "client_id_key": "META_APP_ID",
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scopes": ["instagram_content_publish", "pages_read_engagement", "instagram_basic"],
        "graph_url": "https://graph.facebook.com/v18.0",
    },
}


def register_social_publish_routes(api_router, db, get_current_user):

    async def _budget_guard(provider: str, user_id: str, org_id: str = None, workspace_id: str = None, call_count: int = 1, action: str = "social_publish"):
        try:
            from managed_keys import PLATFORM_KEY_PROVIDERS, check_usage_budget, estimate_integration_cost_usd, emit_budget_alert
            if provider not in PLATFORM_KEY_PROVIDERS:
                return {"cost": 0, "budget": {}}
            estimated_cost = estimate_integration_cost_usd(provider, call_count)
            budget = await check_usage_budget(provider, estimated_cost, workspace_id=workspace_id, org_id=org_id, user_id=user_id)
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                message = f"{scope_name} Nexus AI budget reached for {provider} during {action}."
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=message)
                raise HTTPException(429, message)
            return {"cost": estimated_cost, "budget": budget}
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug(f"Social budget guard skipped for {provider}: {exc}")
            return {"cost": 0, "budget": {}}

    async def _budget_log(provider: str, user_id: str, budget_ctx: dict, org_id: str = None, workspace_id: str = None, call_count: int = 1, action: str = "social_publish"):
        try:
            from managed_keys import PLATFORM_KEY_PROVIDERS, record_usage_event, emit_budget_alert
            if provider not in PLATFORM_KEY_PROVIDERS:
                return
            cost = budget_ctx.get("cost", 0)
            await record_usage_event(provider, cost, user_id=user_id, workspace_id=workspace_id, org_id=org_id, usage_type="integration", key_source="managed_or_override", call_count=call_count, metadata={"action": action})
            budget = budget_ctx.get("budget") or {}
            if budget.get("warn"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                message = f"{scope_name} Nexus AI budget warning for {provider} during {action}."
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", cost), budget.get("warn_threshold_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=message)
        except Exception as exc:
            logger.debug(f"Social budget log skipped for {provider}: {exc}")

    @api_router.get("/social/platforms")
    async def list_social_platforms(request: Request):
        user = await get_current_user(request)
        from key_resolver import get_integration_key
        result = []
        for key, prov in SOCIAL_PROVIDERS.items():
            configured = bool(await get_integration_key(db, prov["client_id_key"]))
            conns = await db.social_connections.count_documents({"provider": key, "user_id": user["user_id"], "status": "active"})
            result.append({
                "platform": key, "name": prov["name"], "icon": prov["icon"],
                "configured": configured, "connected": conns > 0, "connections": conns,
            })
        return {"platforms": result}

    @api_router.post("/social/connect")
    async def connect_social(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        platform = body.get("platform", "")
        if platform not in SOCIAL_PROVIDERS:
            raise HTTPException(400, f"Unknown platform: {platform}")
        
        prov = SOCIAL_PROVIDERS[platform]
        from key_resolver import get_integration_key
        client_id = await get_integration_key(db, prov["client_id_key"])
        if not client_id:
            raise HTTPException(501, f"{prov['name']} not configured. Add {prov['client_id_key']} in Integration Settings.")
        
        import secrets
        state = secrets.token_urlsafe(24)
        conn_id = f"sc_{uuid.uuid4().hex[:12]}"
        
        await db.social_connections.insert_one({
            "connection_id": conn_id, "provider": platform,
            "user_id": user["user_id"], "org_id": body.get("org_id"),
            "status": "pending", "oauth_state": state,
            "access_token": None, "refresh_token": None,
            "token_expires_at": None, "account_name": None, "account_id": None,
            "platform_metadata": {}, "created_at": now_iso(), "updated_at": now_iso(),
        })
        
        redirect_uri = body.get("redirect_uri", f"{str(request.base_url).rstrip('/')}/social/callback")
        scopes = "+".join(prov["scopes"])
        auth_url = f"{prov['auth_url']}?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={state}&scope={scopes}"
        
        return {"connection_id": conn_id, "auth_url": auth_url, "state": state}

    @api_router.post("/social/callback")
    async def social_callback(request: Request):
        body = await request.json()
        code = body.get("code", "")
        state = body.get("state", "")
        
        conn = await db.social_connections.find_one({"oauth_state": state, "status": "pending"})
        if not conn:
            raise HTTPException(404, "Connection not found")
        
        platform = conn["provider"]
        prov = SOCIAL_PROVIDERS[platform]
        budget_ctx = await _budget_guard(platform, conn["user_id"], org_id=conn.get("org_id"), action="social_oauth_callback")
        from key_resolver import get_integration_key
        client_id = await get_integration_key(db, prov["client_id_key"])
        client_secret_key = prov["client_id_key"].replace("API_KEY", "CLIENT_SECRET").replace("CLIENT_KEY", "CLIENT_SECRET").replace("APP_ID", "APP_SECRET")
        client_secret = await get_integration_key(db, client_secret_key)
        
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(prov["token_url"], data={
                "client_id": client_id, "client_secret": client_secret,
                "code": code, "grant_type": "authorization_code",
                "redirect_uri": body.get("redirect_uri", ""),
            })
            if resp.status_code != 200:
                raise HTTPException(400, f"Token exchange failed: {resp.text[:200]}")
            tokens = resp.json()
        
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")
        expires_in = tokens.get("expires_in", 3600)
        
        from encryption import get_fernet; fernet = get_fernet()
        enc_access = fernet.encrypt(access_token.encode()).decode() if access_token else ""
        enc_refresh = fernet.encrypt(refresh_token.encode()).decode() if refresh_token else ""
        
        await db.social_connections.update_one(
            {"connection_id": conn["connection_id"]},
            {"$set": {
                "status": "active",
                "access_token": enc_access, "refresh_token": enc_refresh,
                "token_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat(),
                "account_name": tokens.get("open_id", tokens.get("name", platform)),
                "updated_at": now_iso(),
            }}
        )
        await _budget_log(platform, conn["user_id"], budget_ctx, org_id=conn.get("org_id"), action="social_oauth_callback")
        return {"connection_id": conn["connection_id"], "status": "active"}

    @api_router.get("/social/connections")
    async def list_social_connections(request: Request):
        user = await get_current_user(request)
        conns = await db.social_connections.find(
            {"user_id": user["user_id"], "status": {"$ne": "revoked"}},
            {"_id": 0, "access_token": 0, "refresh_token": 0, "oauth_state": 0}
        ).to_list(20)
        return conns

    @api_router.delete("/social/connections/{conn_id}")
    async def disconnect_social(conn_id: str, request: Request):
        user = await get_current_user(request)
        await db.social_connections.update_one(
            {"connection_id": conn_id, "user_id": user["user_id"]},
            {"$set": {"status": "revoked", "updated_at": now_iso()}}
        )
        return {"message": "Disconnected"}

    # ============ Publishing ============

    @api_router.post("/media/{media_id}/publish")
    async def publish_media(media_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        connection_id = body.get("connection_id", "")
        
        conn = await db.social_connections.find_one({"connection_id": connection_id, "status": "active"}, {"_id": 0})
        if not conn:
            raise HTTPException(400, "Social connection not found or not active")
        
        media = await db.media_items.find_one({"media_id": media_id}, {"_id": 0})
        if not media:
            raise HTTPException(404, "Media not found")

        budget_ctx = await _budget_guard(conn["provider"], user["user_id"], org_id=conn.get("org_id"), workspace_id=media.get("workspace_id"), action="social_publish")
        
        job_id = f"pj_{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "media_id": media_id,
            "connection_id": connection_id,
            "platform": conn["provider"],
            "status": "queued",
            "platform_post_id": None,
            "platform_url": None,
            "title": body.get("title", media.get("name", "")),
            "description": body.get("description", ""),
            "tags": body.get("tags") or [],
            "privacy": body.get("privacy", "public"),
            "scheduled_at": body.get("scheduled_at"),
            "error_message": None,
            "created_by": user["user_id"],
            "created_at": now_iso(),
            "published_at": None,
        }
        await db.publish_jobs.insert_one(job)
        job.pop("_id", None)
        await _budget_log(conn["provider"], user["user_id"], budget_ctx, org_id=conn.get("org_id"), workspace_id=media.get("workspace_id"), action="social_publish")
        
        # Execute publishing asynchronously
        asyncio.create_task(_execute_publish(db, job, conn, media))
        
        return job

    @api_router.get("/social/publish-jobs")
    async def list_publish_jobs(request: Request, limit: int = 20):
        user = await get_current_user(request)
        jobs = await db.publish_jobs.find(
            {"created_by": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return jobs

    @api_router.get("/social/publish-jobs/{job_id}")
    async def get_publish_job(job_id: str, request: Request):
        await get_current_user(request)
        job = await db.publish_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Publish job not found")
        return job

    # ============ AI Caption Generation ============

    @api_router.post("/content/social-caption")
    async def generate_social_caption(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        
        description = body.get("description", "")
        platform = body.get("platform", "instagram")
        tone = body.get("tone", "casual")
        
        char_limits = {"tiktok": 150, "instagram": 2200, "youtube": 5000}
        hashtag_counts = {"tiktok": 5, "instagram": 15, "youtube": 10}
        
        char_limit = char_limits.get(platform, 2200)
        hashtag_count = hashtag_counts.get(platform, 10)
        
        from collaboration_core import get_ai_key_for_agent
        api_key, _ = await get_ai_key_for_agent(user["user_id"], body.get("workspace_id", ""), "chatgpt")
        if not api_key:
            raise HTTPException(400, "No AI key available for caption generation")

        budget = {}
        try:
            from managed_keys import check_usage_budget, estimate_ai_cost_usd, emit_budget_alert, estimate_tokens
            estimated_cost = estimate_ai_cost_usd("chatgpt", estimate_tokens(description), 600)
            budget = await check_usage_budget("chatgpt", estimated_cost, workspace_id=body.get("workspace_id", ""), org_id=body.get("org_id"), user_id=user["user_id"])
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                await emit_budget_alert("chatgpt", budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=body.get("workspace_id", ""), org_id=body.get("org_id"), message="Nexus AI budget reached during social caption generation.")
                raise HTTPException(429, f"{scope_name} Nexus AI budget reached for caption generation")
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug(f"Social caption budget check skipped: {exc}")
        
        from ai_providers import call_ai_direct
        prompt = f"""Generate 3 caption variants for {platform}. The content is about: {description}. 
Tone: {tone}. Max length: {char_limit} characters per caption. Include {hashtag_count} relevant hashtags.
Return ONLY valid JSON: {{"variants": [{{"caption": "...", "hashtags": ["..."], "title": "..."}}]}}"""
        
        try:
            response = await call_ai_direct("chatgpt", api_key, 
                "You are a social media content specialist. Always return valid JSON.", 
                prompt, workspace_id=body.get("workspace_id", ""), db=db)
            
            import json
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    data = {"variants": [{"caption": response[:char_limit], "hashtags": [], "title": ""}]}

            try:
                from managed_keys import record_usage_event, estimate_ai_cost_usd, emit_budget_alert, estimate_tokens
                actual_cost = estimate_ai_cost_usd("chatgpt", estimate_tokens(prompt), estimate_tokens(response))
                await record_usage_event("chatgpt", actual_cost, user_id=user["user_id"], workspace_id=body.get("workspace_id", ""), org_id=body.get("org_id"), usage_type="ai", key_source="direct_route", tokens_in=estimate_tokens(prompt), tokens_out=estimate_tokens(response), metadata={"action": "social_caption"})
                if budget.get("warn"):
                    await emit_budget_alert("chatgpt", budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", actual_cost), budget.get("warn_threshold_usd"), user_id=user["user_id"], workspace_id=body.get("workspace_id", ""), org_id=body.get("org_id"), message="Nexus AI budget warning during social caption generation.")
            except Exception as exc:
                logger.debug(f"Social caption usage log skipped: {exc}")
            
            return data
        except Exception as e:
            raise HTTPException(500, f"Caption generation failed: {str(e)[:200]}")


async def _execute_publish(db, job, conn, media):
    """Execute a publish job asynchronously."""
    job_id = job["job_id"]
    platform = job["platform"]
    
    try:
        await db.publish_jobs.update_one({"job_id": job_id}, {"$set": {"status": "uploading"}})
        
        # Get access token
        from encryption import get_fernet; fernet = get_fernet()
        access_token = fernet.decrypt(conn["access_token"].encode()).decode()
        
        # Platform-specific publishing
        if platform == "youtube":
            result = await _publish_youtube(access_token, job, media)
        elif platform == "tiktok":
            result = await _publish_tiktok(access_token, job, media)
        elif platform == "instagram":
            result = await _publish_instagram(access_token, job, media, conn)
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        await db.publish_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "published",
            "platform_post_id": result.get("post_id", ""),
            "platform_url": result.get("url", ""),
            "published_at": now_iso(),
        }})
        logger.info(f"Published {job_id} to {platform}: {result.get('url', '')}")
        
    except Exception as e:
        logger.error(f"Publish job {job_id} failed: {e}")
        await db.publish_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "failed",
            "error_message": str(e)[:500],
        }})


async def _publish_youtube(token, job, media):
    """Upload video to YouTube via Data API v3 resumable upload."""
    import httpx
    
    # Step 1: Get video bytes from media storage
    video_data = media.get("data")
    if not video_data:
        raise Exception("No video data found in media record")
    
    import base64
    if isinstance(video_data, str):
        video_bytes = base64.b64decode(video_data)
    else:
        video_bytes = video_data
    
    metadata = {
        "snippet": {
            "title": job.get("title", "Untitled")[:100],
            "description": job.get("description", "")[:5000],
            "tags": job.get("tags") or [][:30],
            "categoryId": "22",
        },
        "status": {"privacyStatus": job.get("privacy", "public")},
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 2: Initiate resumable upload
        init_resp = await client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": media.get("mime_type", "video/mp4"),
                "X-Upload-Content-Length": str(len(video_bytes)),
            },
            json=metadata,
        )
        if init_resp.status_code not in (200, 308):
            raise Exception(f"YouTube init failed: {init_resp.status_code} {init_resp.text[:200]}")
        
        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            raise Exception("YouTube did not return upload URL")
        
        # Step 3: Upload video bytes
        upload_resp = await client.put(
            upload_url,
            content=video_bytes,
            headers={"Content-Type": media.get("mime_type", "video/mp4")},
        )
        upload_resp.raise_for_status()
        result = upload_resp.json()
        
        video_id = result.get("id", "")
        return {
            "post_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}" if video_id else "",
            "status": "processing",
        }


async def _publish_tiktok(token, job, media):
    """Upload video to TikTok via Content Posting API v2."""
    import httpx
    import base64
    
    video_data = media.get("data")
    if not video_data:
        raise Exception("No video data found in media record")
    
    if isinstance(video_data, str):
        video_bytes = base64.b64decode(video_data)
    else:
        video_bytes = video_data
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 1: Initialize upload
        init_resp = await client.post(
            "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "post_info": {
                    "title": job.get("title", "")[:150],
                    "privacy_level": "SELF_ONLY" if job.get("privacy") == "private" else "PUBLIC_TO_EVERYONE",
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": len(video_bytes),
                },
            },
        )
        if init_resp.status_code != 200:
            raise Exception(f"TikTok init failed: {init_resp.status_code} {init_resp.text[:200]}")
        
        result = init_resp.json()
        upload_url = (result.get("data") or {}).get("upload_url", "")
        publish_id = (result.get("data") or {}).get("publish_id", "")
        
        if not upload_url:
            raise Exception("TikTok did not return upload URL")
        
        # Step 2: Upload video
        await client.put(upload_url, content=video_bytes, headers={"Content-Type": "video/mp4"})
        
        return {
            "post_id": publish_id,
            "url": f"https://tiktok.com/@user/video/{publish_id}" if publish_id else "",
            "status": "processing",
        }


async def _publish_instagram(token, job, media, conn):
    """Publish to Instagram via Graph API (Reels/Feed)."""
    import httpx
    
    media_url = media.get("url") or media.get("public_url", "")
    if not media_url:
        raise Exception("Instagram requires a public URL for the media. Upload to cloud storage first.")
    
    ig_user_id = conn.get("account_id") or (conn.get("platform_metadata") or {}).get("instagram_user_id", "")
    if not ig_user_id:
        raise Exception("Instagram user ID not found. Please reconnect your account.")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Create media container
        is_video = media.get("mime_type", "").startswith("video/")
        container_data = {
            "access_token": token,
            "caption": job.get("description", "")[:2200],
        }
        if is_video:
            container_data["media_type"] = "REELS"
            container_data["video_url"] = media_url
        else:
            container_data["image_url"] = media_url
        
        create_resp = await client.post(
            f"https://graph.facebook.com/v18.0/{ig_user_id}/media",
            data=container_data,
        )
        create_resp.raise_for_status()
        container_id = create_resp.json().get("id", "")
        
        if not container_id:
            raise Exception("Instagram did not return container ID")
        
        # Step 2: Publish the container
        pub_resp = await client.post(
            f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
        )
        pub_resp.raise_for_status()
        post_id = pub_resp.json().get("id", "")
        
        return {
            "post_id": post_id,
            "url": f"https://instagram.com/p/{post_id}" if post_id else "",
            "status": "published",
        }
