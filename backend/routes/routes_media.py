"""Multimedia — Video/Audio/Media Generation, TTS, STT, Media Library"""
import uuid
import os
import base64
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_config import FEATURE_FLAGS

logger = logging.getLogger(__name__)

# Voice options for TTS
TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
VIDEO_SIZES = ["1280x720", "1792x1024", "1024x1792", "1024x1024"]
VIDEO_DURATIONS = [4, 8, 12]


class VideoGenRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: str = ""
    size: str = "1280x720"
    duration: int = 4
    model: str = "gemini-veo"
    style: str = "natural"  # natural, cinematic, animated, documentary
    fps: int = 24
    use_own_key: bool = False

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
    voice: str = "alloy"
    model: str = "tts-1"
    speed: float = 1.0
    use_own_key: bool = False

class STTRequest(BaseModel):
    use_own_key: bool = False



async def _get_api_key(db, use_own_key, user_keys, provider="chatgpt"):
    """Get API key — user's own or platform key via key_resolver."""
    if use_own_key and user_keys:
        from routes_ai_keys import decrypt_key
        encrypted = user_keys.get(provider) or user_keys.get("chatgpt")
        if encrypted:
            try:
                return decrypt_key(encrypted), "user"
            except Exception as _e:
                logger.warning(f"Caught exception: {_e}")
    from key_resolver import get_integration_key
    key = await get_integration_key(db, "OPENAI_API_KEY")
    if not key:
        raise HTTPException(500, "OpenAI API key not configured. Set OPENAI_API_KEY in Integration Settings.")
    return key, "platform"


from nexus_utils import now_iso, safe_regex

def register_media_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ============ Config (MUST be before /:id routes) ============

    @api_router.get("/media/config")
    async def get_media_config(request: Request):
        await get_current_user(request)
        return {
            "tts_voices": [{"id": v, "name": v.capitalize()} for v in TTS_VOICES],
            "tts_models": [{"id": "tts-1", "name": "Standard"}, {"id": "tts-1-hd", "name": "HD Quality"}],
            "video_sizes": VIDEO_SIZES,
            "video_durations": VIDEO_DURATIONS,
            "video_models": [{"id": "gemini-veo", "name": "Gemini Veo (Text Concept)"}],
            "video_styles": ["natural", "cinematic", "animated", "documentary", "slow_motion", "timelapse"],
            "video_fps_options": [24, 30, 60],
            "publish_destinations": ["youtube", "twitter", "linkedin", "custom_webhook"],
            "supported_upload_types": {"video": ["mp4", "webm", "mov"], "audio": ["mp3", "wav", "ogg", "flac"], "image": ["png", "jpg", "jpeg", "gif", "webp"]},
            "features": FEATURE_FLAGS,
        }

    # ============ Video Generation (Google Veo via Gemini) ============

    @api_router.post("/workspaces/{workspace_id}/generate-video")
    async def generate_video(workspace_id: str, data: VideoGenRequest, request: Request):
        """Generate a video concept from text prompt using Gemini"""
        user = await _authed_user(request, workspace_id)
        if not FEATURE_FLAGS.get('video_generation', {}).get('enabled', False):
            raise HTTPException(501, FEATURE_FLAGS.get('video_generation', {}).get('reason', 'Video generation not enabled'))
        if data.size not in VIDEO_SIZES:
            raise HTTPException(400, f"Invalid size. Use: {VIDEO_SIZES}")
        if data.duration not in VIDEO_DURATIONS:
            raise HTTPException(400, f"Invalid duration. Use: {VIDEO_DURATIONS}")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "GEMINI_API_KEY")
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise HTTPException(400, "Video generation requires GEMINI_API_KEY. Configure in Settings > AI Keys.")

        key_source = "platform"
        start_time = time.time()

        # Budget pre-check
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        org_id = (workspace or {}).get("org_id")
        try:
            from managed_keys import check_usage_budget, estimate_ai_cost_usd, emit_budget_alert
            estimated_cost = 0.05  # ~$0.05 per video generation
            budget = await check_usage_budget("gemini", estimated_cost, workspace_id=workspace_id, org_id=org_id, user_id=user["user_id"])
            if budget.get("blocked"):
                raise HTTPException(429, "Nexus AI budget reached for video generation.")
        except HTTPException:
            raise
        except Exception as _be:
            logger.warning(f"Budget check skipped for video gen: {_be}")

        try:
            from ai_providers import call_veo
            result = await call_veo(
                api_key, data.prompt,
                resolution=data.size or "720p",
                aspect_ratio="16:9",
                workspace_id=workspace_id
            )
            duration_ms = int((time.time() - start_time) * 1000)

            # Store async operation for polling
            op_id = f"vop_{uuid.uuid4().hex[:12]}"
            await db.media_operations.insert_one({
                "operation_id": op_id, "workspace_id": workspace_id,
                "type": "video", "provider": "veo-3.1",
                "veo_operation": result.get("operation_name", ""),
                "prompt": data.prompt, "status": "pending",
                "created_by": user["user_id"], "created_at": now_iso(),
            })

            # Record budget usage
            try:
                from managed_keys import record_usage_event
                await record_usage_event("gemini", 0.05, user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, usage_type="ai", key_source=key_source, metadata={"action": "video_generation", "operation_id": op_id})
            except Exception as _be:
                logger.warning(f"Budget record failed for video gen: {_be}")

            return {
                "operation_id": op_id, "status": "generating", "provider": "veo-3.1",
                "duration_ms": duration_ms,
                "message": "Video generation started via Veo 3.1. Poll /media/operations/{operation_id}/status for completion.",
            }

        except HTTPException:
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            await db.media_metrics.insert_one({
                "metric_id": f"mm_{uuid.uuid4().hex[:8]}", "workspace_id": workspace_id,
                "type": "video", "provider": "gemini-veo", "success": False,
                "duration_ms": duration_ms, "error": str(e)[:200], "created_at": now_iso(),
            })
            logger.error(f"Video generation failed: {e}")
            raise HTTPException(500, f"Video generation failed: {str(e)[:200]}")

    # ============ Text-to-Speech (OpenAI TTS) ============

    @api_router.post("/workspaces/{workspace_id}/generate-audio")
    async def generate_audio(workspace_id: str, data: TTSRequest, request: Request):
        """Generate audio from text using OpenAI TTS"""
        user = await _authed_user(request, workspace_id)
        if data.voice not in TTS_VOICES:
            raise HTTPException(400, f"Invalid voice. Use: {TTS_VOICES}")

        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_keys": 1})
        api_key, key_source = await _get_api_key(db, data.use_own_key, user_doc.get("ai_keys") or {} if user_doc else {})

        start_time = time.time()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as _tts_client:
                _tts_resp = await _tts_client.post("https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": data.model, "voice": data.voice, "input": data.text[:4096], "speed": data.speed})
                if _tts_resp.status_code != 200:
                    raise HTTPException(502, f"TTS API error: {_tts_resp.status_code}")
                audio_bytes = _tts_resp.content
            duration_ms = int((time.time() - start_time) * 1000)

            audio_id = f"aud_{uuid.uuid4().hex[:12]}"
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            now = now_iso()

            await db.media_items.insert_one({
                "media_id": audio_id, "workspace_id": workspace_id, "type": "audio",
                "prompt": data.text[:200], "model": data.model, "provider": "openai_tts",
                "key_source": key_source, "voice": data.voice, "speed": data.speed,
                "mime_type": "audio/mp3", "file_size": len(audio_bytes),
                "duration_ms": duration_ms, "created_by": user["user_id"], "created_at": now,
                "tags": [], "folder": None,
            })
            await db.media_data.insert_one({"media_id": audio_id, "data": audio_b64, "created_at": now})

            await db.media_metrics.insert_one({
                "metric_id": f"mm_{uuid.uuid4().hex[:8]}", "workspace_id": workspace_id,
                "type": "audio", "provider": "openai_tts", "success": True,
                "duration_ms": duration_ms, "file_size": len(audio_bytes), "created_at": now,
            })

            return {"media_id": audio_id, "type": "audio", "mime_type": "audio/mp3",
                    "file_size": len(audio_bytes), "duration_ms": duration_ms, "voice": data.voice, "key_source": key_source}

        except HTTPException:
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            await db.media_metrics.insert_one({
                "metric_id": f"mm_{uuid.uuid4().hex[:8]}", "workspace_id": workspace_id,
                "type": "audio", "provider": "openai_tts", "success": False,
                "duration_ms": duration_ms, "error": str(e)[:200], "created_at": now_iso(),
            })
            raise HTTPException(500, f"Audio generation failed: {str(e)[:200]}")

    # ============ Speech-to-Text (Whisper) ============

    @api_router.post("/workspaces/{workspace_id}/transcribe")
    async def transcribe_audio(workspace_id: str, request: Request):
        """Transcribe audio to text using OpenAI Whisper"""
        user = await _authed_user(request, workspace_id)
        form = await request.form()
        audio_file = form.get("file")
        use_own_key = form.get("use_own_key", "false") == "true"

        if not audio_file:
            raise HTTPException(400, "No audio file provided")

        user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_keys": 1})
        api_key, key_source = await _get_api_key(db, use_own_key, user_doc.get("ai_keys") or {} if user_doc else {})

        audio_bytes = await audio_file.read()
        start_time = time.time()

        try:
            import httpx
            headers = {"Authorization": f"Bearer {api_key}"}
            files = {"file": (audio_file.filename or "audio.webm", audio_bytes, audio_file.content_type or "audio/webm")}
            data_fields = {"model": "whisper-1"}

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data=data_fields)
                resp.raise_for_status()
                result = resp.json()

            duration_ms = int((time.time() - start_time) * 1000)
            return {"text": result.get("text", ""), "duration_ms": duration_ms, "key_source": key_source}

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise HTTPException(500, f"Transcription failed: {str(e)[:200]}")

    # ============ Media Library ============

    @api_router.get("/workspaces/{workspace_id}/media")
    async def list_media(
        workspace_id: str, request: Request,
        media_type: Optional[str] = None, search: Optional[str] = None,
        folder: Optional[str] = None, limit: int = 30, offset: int = 0,
    ):
        """List all media items in a workspace"""
        await get_current_user(request)
        query = {"workspace_id": workspace_id}
        if media_type and media_type in ("video", "audio", "image"):
            query["type"] = media_type
        if search:
            query["$or"] = [{"prompt": {"$regex": safe_regex(search), "$options": "i"}}, {"tags": {"$regex": safe_regex(search), "$options": "i"}}]
        if folder:
            query["folder"] = folder

        items = await db.media_items.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.media_items.count_documents(query)
        return {"items": items, "total": total}

    @api_router.get("/media/{media_id}")
    async def get_media_item(media_id: str, request: Request):
        await get_current_user(request)
        item = await db.media_items.find_one({"media_id": media_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Media not found")
        return item


    @api_router.get("/media/operations/{operation_id}/status")
    async def poll_media_operation(operation_id: str, request: Request):
        """Poll async media generation (Veo video, Lyria music) status."""
        user = await get_current_user(request)
        op = await db.media_operations.find_one({"operation_id": operation_id}, {"_id": 0})
        if not op:
            raise HTTPException(404, "Operation not found")
        if op["status"] == "completed":
            return op
        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "GOOGLE_AI_KEY")
        if not api_key:
            api_key = os.environ.get("GOOGLE_AI_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return {**op, "error": "API key missing for polling"}
        if op.get("type") == "video" and op.get("veo_operation"):
            from ai_providers import poll_veo_operation
            result = await poll_veo_operation(api_key, op["veo_operation"])
            if result["status"] == "completed":
                await db.media_operations.update_one(
                    {"operation_id": operation_id},
                    {"$set": {"status": "completed", "result": result, "completed_at": now_iso()}})
            return {**{k: v for k, v in op.items() if k != "_id"}, **result}
        return op


    @api_router.get("/media/{media_id}/data")
    async def get_media_data(media_id: str, request: Request):
        user = await get_current_user(request)
        # Check the media item exists and user has workspace access
        media = await db.media_items.find_one({"media_id": media_id}, {"_id": 0, "workspace_id": 1})
        if not media:
            raise HTTPException(404, "Media not found")
        ws_id = media.get("workspace_id", "")
        if ws_id and user.get("platform_role") != "super_admin":
            ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "owner_id": 1})
            if ws and ws.get("owner_id") != user["user_id"]:
                member = await db.workspace_members.find_one(
                    {"workspace_id": ws_id, "user_id": user["user_id"]}, {"_id": 0})
                if not member:
                    raise HTTPException(403, "Access denied")
        data = await db.media_data.find_one({"media_id": media_id}, {"_id": 0})
        if not data:
            raise HTTPException(404, "Media data not found")
        return {"media_id": media_id, "data": data["data"]}

    @api_router.put("/media/{media_id}")
    async def update_media(media_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {}
        if "tags" in body:
            updates["tags"] = body["tags"]
        if "folder" in body:
            updates["folder"] = body["folder"]
        if "name" in body:
            updates["name"] = body["name"]
        if updates:
            await db.media_items.update_one({"media_id": media_id}, {"$set": updates})
        return await db.media_items.find_one({"media_id": media_id}, {"_id": 0})

    @api_router.delete("/media/{media_id}")
    async def delete_media(media_id: str, request: Request):
        await get_current_user(request)
        await db.media_items.delete_one({"media_id": media_id})
        await db.media_data.delete_one({"media_id": media_id})
        return {"message": "Deleted"}

    # ============ Media Metrics ============

    @api_router.get("/workspaces/{workspace_id}/media/metrics")
    async def get_media_metrics(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": {"type": "$type", "provider": "$provider"},
                "total": {"$sum": 1},
                "successful": {"$sum": {"$cond": ["$success", 1, 0]}},
                "avg_duration": {"$avg": "$duration_ms"},
                "total_size": {"$sum": "$file_size"},
            }}
        ]
        results = []
        async for doc in db.media_metrics.aggregate(pipeline):
            results.append({
                "type": doc["_id"]["type"], "provider": doc["_id"]["provider"],
                "total": doc["total"], "successful": doc["successful"],
                "success_rate": round(doc["successful"] / max(doc["total"], 1) * 100, 1),
                "avg_duration_ms": round(doc.get("avg_duration") or 0),
                "total_size_mb": round((doc.get("total_size") or 0) / 1048576, 2),
            })
        return {"metrics": results}

    # ============ Media Folders ============

    @api_router.get("/workspaces/{workspace_id}/media/folders")
    async def list_media_folders(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        pipeline = [
            {"$match": {"workspace_id": workspace_id, "folder": {"$ne": None}}},
            {"$group": {"_id": "$folder", "count": {"$sum": 1}}}
        ]
        folders = [{"name": doc["_id"], "count": doc["count"]} async for doc in db.media_items.aggregate(pipeline)]
        return {"folders": folders}

    # Config defined above /media/{id} routes to avoid conflict


    # ============ Job Queue ============

    @api_router.post("/workspaces/{workspace_id}/media/jobs")
    async def create_media_job(workspace_id: str, request: Request):
        """Create a generation job for tracking"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        job_id = f"mjob_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        job = {
            "job_id": job_id, "workspace_id": workspace_id,
            "type": body.get("type", "text_to_video"),
            "provider": body.get("provider", "gemini-veo"),
            "input": body.get("input") or {},
            "status": "queued", "progress": 0,
            "result_media_id": None, "error": None,
            "cost_usd": None, "requested_by": user["user_id"],
            "created_at": now, "completed_at": None,
        }
        await db.media_jobs.insert_one(job)
        return {k: v for k, v in job.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/media/jobs")
    async def list_media_jobs(workspace_id: str, request: Request, status: Optional[str] = None):
        await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if status:
            query["status"] = status
        jobs = await db.media_jobs.find(query, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
        return {"jobs": jobs}

    @api_router.get("/media/jobs/{job_id}")
    async def get_media_job(job_id: str, request: Request):
        await get_current_user(request)
        job = await db.media_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    # ============ Image-to-Video ============

    @api_router.post("/workspaces/{workspace_id}/image-to-video")
    async def image_to_video(workspace_id: str, request: Request):
        """Generate video from an existing image using Gemini"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        source_image_id = body.get("source_image_id", "")

        if not source_image_id:
            raise HTTPException(400, "source_image_id required")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "GEMINI_API_KEY")
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise HTTPException(400, "Image-to-video requires GEMINI_API_KEY.")

        # Get source image
        img = await db.generated_images.find_one({"image_id": source_image_id}, {"_id": 0})
        if not img:
            img = await db.media_items.find_one({"media_id": source_image_id}, {"_id": 0})
        if not img:
            raise HTTPException(404, "Source image not found")

        return {"status": "processing", "message": "Image-to-video queued via Google Veo.", "source_image_id": source_image_id}

    # ============ Bulk Media Operations ============

    @api_router.post("/workspaces/{workspace_id}/media/bulk/tag")
    async def bulk_tag_media(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        body = await request.json()
        media_ids = body.get("media_ids") or []
        tags = body.get("tags") or []
        if not media_ids or not tags:
            raise HTTPException(400, "media_ids and tags required")
        result = await db.media_items.update_many(
            {"media_id": {"$in": media_ids}, "workspace_id": workspace_id},
            {"$addToSet": {"tags": {"$each": tags}}}
        )
        return {"updated": result.modified_count}

    @api_router.post("/workspaces/{workspace_id}/media/bulk/move")
    async def bulk_move_media(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        body = await request.json()
        media_ids = body.get("media_ids") or []
        folder = body.get("folder", None)
        result = await db.media_items.update_many(
            {"media_id": {"$in": media_ids}, "workspace_id": workspace_id},
            {"$set": {"folder": folder}}
        )
        return {"moved": result.modified_count}

    @api_router.post("/workspaces/{workspace_id}/media/bulk/delete")
    async def bulk_delete_media(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        body = await request.json()
        media_ids = body.get("media_ids") or []
        result = await db.media_items.delete_many({"media_id": {"$in": media_ids}, "workspace_id": workspace_id})
        await db.media_data.delete_many({"media_id": {"$in": media_ids}})
        return {"deleted": result.deleted_count}

    # ============ Share Links ============

    @api_router.post("/media/{media_id}/share")
    async def create_share_link(media_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        import secrets
        token = secrets.token_urlsafe(16)
        expires_hours = body.get("expires_hours", 24)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=expires_hours)).isoformat()
        await db.media_shares.insert_one({
            "share_id": f"msh_{uuid.uuid4().hex[:8]}",
            "media_id": media_id, "token": token,
            "password": body.get("password"),
            "expires_at": expires_at, "created_at": now.isoformat(),
        })
        return {"share_url": f"/api/media/shared/{token}", "token": token, "expires_at": expires_at}

    @api_router.get("/media/shared/{token}")
    async def get_shared_media(token: str):
        share = await db.media_shares.find_one({"token": token}, {"_id": 0})
        if not share:
            raise HTTPException(404, "Share link not found or expired")
        if share.get("expires_at") and share["expires_at"] < now_iso():
            raise HTTPException(410, "Share link expired")
        item = await db.media_items.find_one({"media_id": share["media_id"]}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Media not found")
        return item

    # ============ Music Generation (OpenAI Audio) ============

    @api_router.post("/workspaces/{workspace_id}/generate-music")
    async def generate_music(workspace_id: str, request: Request):
        """Generate music — requires dedicated music composition API"""
        user = await _authed_user(request, workspace_id)
        if not FEATURE_FLAGS.get('music_generation', {}).get('enabled', False):
            raise HTTPException(501, FEATURE_FLAGS.get('music_generation', {}).get('reason', 'Music generation not enabled'))
        body = await request.json()
        prompt = body.get("prompt", "")
        duration = body.get("duration", 30)
        genre = body.get("genre", "ambient")
        mood = body.get("mood", "calm")

        if not prompt:
            raise HTTPException(400, "prompt is required")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "GOOGLE_AI_KEY")
        if not api_key:
            api_key = os.environ.get("GOOGLE_AI_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise HTTPException(400, "Google AI key required for music generation. Configure in Settings > AI Keys.")

        start_time = time.time()
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        org_id = (workspace or {}).get("org_id")

        try:
            from ai_providers import call_lyria
            tier = body.get("lyria_tier", "clip")
            model = "lyria-3-pro-preview" if tier == "pro" else "lyria-3-clip-preview"
            result = await call_lyria(api_key, f"{genre} {mood} - {prompt}", model=model, workspace_id=workspace_id)
            duration_ms = int((time.time() - start_time) * 1000)

            if not result.get("audio"):
                raise Exception("Lyria returned no audio content")

            media_id = f"mus_{uuid.uuid4().hex[:12]}"
            now = now_iso()
            await db.media_items.insert_one({
                "media_id": media_id, "workspace_id": workspace_id, "type": "music",
                "prompt": prompt, "provider": "lyria-3", "genre": genre, "mood": mood,
                "duration_requested": duration, "duration_ms": duration_ms,
                "mime_type": result["audio"][0].get("mime_type", "audio/wav"), "status": "completed",
                "lyrics": result.get("lyrics", ""),
                "created_by": user["user_id"], "created_at": now,
            })
            await db.media_data.insert_one({"media_id": media_id, "data": result["audio"][0]["base64"], "created_at": now})

            try:
                from managed_keys import record_usage_event
                await record_usage_event("gemini", 0.03, user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, usage_type="ai", key_source="platform", metadata={"action": "music_generation", "media_id": media_id})
            except Exception as _be:
                logger.warning(f"Budget record failed for music gen: {_be}")

            return {"media_id": media_id, "type": "music", "mime_type": result["audio"][0].get("mime_type", "audio/wav"), "duration_ms": duration_ms, "status": "completed", "provider": "lyria-3"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Music generation failed: {e}")
            raise HTTPException(500, f"Music generation failed: {str(e)[:200]}")

    # ============ SFX Generation (ElevenLabs) ============

    @api_router.post("/workspaces/{workspace_id}/generate-sfx")
    async def generate_sfx(workspace_id: str, request: Request):
        """Generate sound effects using ElevenLabs Sound Generation API"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        prompt = body.get("prompt", "")
        duration = body.get("duration", 5)

        if not prompt:
            raise HTTPException(400, "prompt is required")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "ELEVENLABS_API_KEY")
        if not api_key:
            api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise HTTPException(400, "SFX generation requires ELEVENLABS_API_KEY. Configure in Settings > AI Keys or Platform Keys.")

        start_time = time.time()
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        org_id = (workspace or {}).get("org_id")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.elevenlabs.io/v1/sound-generation",
                    headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                    json={"text": prompt, "duration_seconds": min(duration, 22), "prompt_influence": 0.3}
                )

            duration_ms = int((time.time() - start_time) * 1000)

            if resp.status_code != 200:
                raise Exception(f"ElevenLabs API error: {resp.status_code} - {resp.text[:200]}")

            audio_data = base64.b64encode(resp.content).decode()
            media_id = f"sfx_{uuid.uuid4().hex[:12]}"
            now = now_iso()

            await db.media_items.insert_one({
                "media_id": media_id, "workspace_id": workspace_id, "type": "sfx",
                "prompt": prompt, "provider": "elevenlabs",
                "duration_requested": duration, "duration_ms": duration_ms,
                "mime_type": "audio/mpeg", "status": "completed",
                "created_by": user["user_id"], "created_at": now,
            })
            await db.media_data.insert_one({"media_id": media_id, "data": audio_data, "created_at": now})

            try:
                from managed_keys import record_usage_event
                await record_usage_event("elevenlabs", 0.01, user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, usage_type="integration", key_source="platform", call_count=1, metadata={"action": "sfx_generation", "media_id": media_id})
            except Exception as _be:
                logger.warning(f"Budget record failed for SFX gen: {_be}")

            return {"media_id": media_id, "type": "sfx", "mime_type": "audio/mpeg", "duration_ms": duration_ms, "status": "completed"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"SFX generation failed: {e}")
            raise HTTPException(500, f"SFX generation failed: {str(e)[:200]}")


    # ============ Storyboarding ============

    @api_router.post("/workspaces/{workspace_id}/video/storyboard")
    async def create_storyboard(workspace_id: str, request: Request):
        """Multi-agent storyboard — create scenes from topic, generate videos for each"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        topic = body.get("topic", "")
        num_scenes = body.get("num_scenes", 3)
        narration_voice = body.get("narration_voice", "nova")
        music_prompt = body.get("background_music_prompt")

        if not topic:
            raise HTTPException(400, "Topic required")

        storyboard_id = f"sb_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # AI-generate scene descriptions from topic
        scenes = []
        budget = {}
        try:
            from ai_providers import call_ai_direct
            from managed_keys import check_usage_budget, estimate_ai_cost_usd, estimate_tokens, emit_budget_alert
            scene_prompt = f"""Create a {min(num_scenes, 8)}-scene storyboard for a short video about: {topic}

For each scene, provide:
- A vivid visual description (what the viewer sees)
- Narration text (what the narrator says)

Format each scene as:
SCENE 1:
VISUAL: [description]
NARRATION: [text]

Be creative, cinematic, and engaging."""
            api_key, _ = await _get_api_key(db, False, {}, provider="chatgpt")
            estimated_cost = estimate_ai_cost_usd("chatgpt", estimate_tokens(scene_prompt), 900)
            budget = await check_usage_budget("chatgpt", estimated_cost, workspace_id=workspace_id, user_id=user["user_id"])
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                await emit_budget_alert("chatgpt", budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=workspace_id, message="Nexus AI budget reached during storyboard generation.")
                raise HTTPException(429, f"{scope_name} Nexus AI budget reached for storyboard generation")
            ai_response = await call_ai_direct("chatgpt", api_key, "You are a professional video storyboard creator.", scene_prompt)
            try:
                from managed_keys import record_usage_event, emit_budget_alert
                actual_cost = estimate_ai_cost_usd("chatgpt", estimate_tokens(scene_prompt), estimate_tokens(ai_response))
                await record_usage_event("chatgpt", actual_cost, user_id=user["user_id"], workspace_id=workspace_id, usage_type="ai", key_source="media_storyboard", tokens_in=estimate_tokens(scene_prompt), tokens_out=estimate_tokens(ai_response), metadata={"action": "storyboard_generation", "storyboard_id": storyboard_id})
                if budget.get("warn"):
                    await emit_budget_alert("chatgpt", budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", actual_cost), budget.get("warn_threshold_usd"), user_id=user["user_id"], workspace_id=workspace_id, message="Nexus AI budget warning during storyboard generation.")
            except Exception as exc:
                logger.debug(f"Storyboard usage log skipped: {exc}")
            # Parse AI response into scenes
            scene_blocks = [b.strip() for b in ai_response.split("SCENE") if b.strip() and "VISUAL:" in b]
            for i, block in enumerate(scene_blocks[:min(num_scenes, 8)]):
                visual = ""
                narration = ""
                for line in block.split("\n"):
                    line = line.strip()
                    if line.startswith("VISUAL:"):
                        visual = line.replace("VISUAL:", "").strip()
                    elif line.startswith("NARRATION:"):
                        narration = line.replace("NARRATION:", "").strip()
                scenes.append({
                    "scene_number": i + 1,
                    "description": visual or f"Scene {i+1}: {topic}",
                    "narration_text": narration or f"Narration for scene {i+1} about {topic}.",
                    "duration_sec": body.get("scene_duration", 4),
                    "transition": "fade" if i > 0 else "none",
                    "video_job_id": None, "audio_job_id": None, "status": "pending",
                })
        except Exception as e:
            logger.warning(f"AI storyboard generation failed, using fallback: {e}")

        # Fallback: fill remaining scenes with templates
        for i in range(len(scenes), min(num_scenes, 8)):
            scenes.append({
                "scene_number": i + 1,
                "description": f"Scene {i+1}: {topic} — visual segment {i+1}",
                "narration_text": f"Narration for scene {i+1} about {topic}.",
                "duration_sec": body.get("scene_duration", 4),
                "transition": "fade" if i > 0 else "none",
                "video_job_id": None, "audio_job_id": None, "status": "pending",
            })

        storyboard = {
            "storyboard_id": storyboard_id,
            "workspace_id": workspace_id,
            "topic": topic,
            "scenes": scenes,
            "narration_voice": narration_voice,
            "background_music_prompt": music_prompt,
            "status": "draft",  # draft, generating, completed, failed
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.storyboards.insert_one(storyboard)
        return {k: v for k, v in storyboard.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/video/storyboards")
    async def list_storyboards(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        items = await db.storyboards.find({"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"storyboards": items}

    @api_router.post("/video/storyboards/{storyboard_id}/generate")
    async def generate_storyboard_scenes(storyboard_id: str, request: Request):
        """Batch generate videos for all storyboard scenes"""
        await get_current_user(request)
        sb = await db.storyboards.find_one({"storyboard_id": storyboard_id}, {"_id": 0})
        if not sb:
            raise HTTPException(404, "Storyboard not found")

        await db.storyboards.update_one({"storyboard_id": storyboard_id}, {"$set": {"status": "generating"}})

        # Create jobs for each scene
        jobs = []
        for scene in sb.get("scenes") or []:
            job_id = f"mjob_{uuid.uuid4().hex[:12]}"
            await db.media_jobs.insert_one({
                "job_id": job_id, "workspace_id": sb["workspace_id"],
                "type": "text_to_video", "provider": "gemini-veo",
                "input": {"prompt": scene["description"], "duration": scene["duration_sec"]},
                "status": "queued", "progress": 0,
                "storyboard_id": storyboard_id, "scene_number": scene["scene_number"],
                "created_at": now_iso(),
            })
            jobs.append({"job_id": job_id, "scene_number": scene["scene_number"]})

        return {"storyboard_id": storyboard_id, "jobs": jobs, "total_scenes": len(jobs)}

    # ============ TTS Preview ============

    @api_router.post("/workspaces/{workspace_id}/audio/tts-preview")
    async def tts_preview(workspace_id: str, request: Request):
        """Quick TTS preview — generates a short audio clip without saving"""
        await _authed_user(request, workspace_id)
        body = await request.json()
        text = body.get("text", "")[:200]  # Max 200 chars for preview
        voice = body.get("voice", "alloy")

        if not text:
            raise HTTPException(400, "Text required")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(500, "TTS not configured")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as _tts_client:
                _tts_resp = await _tts_client.post("https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "tts-1", "voice": voice, "input": text[:4096], "speed": 1.0})
                if _tts_resp.status_code != 200:
                    raise HTTPException(502, f"TTS API error: {_tts_resp.status_code}")
                audio_bytes = _tts_resp.content
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            return {"audio_data": audio_b64, "mime_type": "audio/mp3", "voice": voice}
        except Exception as e:
            raise HTTPException(500, f"Preview failed: {str(e)[:100]}")

    # ============ Podcast Generation Template ============

    @api_router.post("/workspaces/{workspace_id}/podcast/generate")
    async def generate_podcast(workspace_id: str, request: Request):
        """Generate a podcast-style discussion between AI agents"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        topic = body.get("topic", "")
        agents = body.get("agents", ["claude", "chatgpt"])
        duration_minutes = body.get("duration_minutes", 5)
        style = body.get("style", "conversational")  # conversational, debate, interview

        if not topic:
            raise HTTPException(400, "Topic required")

        podcast_id = f"pod_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # Generate episode outline
        segments_count = max(2, duration_minutes)
        segments = []
        for i in range(segments_count):
            speaker = agents[i % len(agents)]
            segments.append({
                "segment_number": i + 1,
                "speaker": speaker,
                "topic_point": f"Discussion point {i+1} about {topic}",
                "estimated_duration_sec": 60,
                "audio_job_id": None,
                "status": "pending",
            })

        podcast = {
            "podcast_id": podcast_id, "workspace_id": workspace_id,
            "topic": topic, "agents": agents, "style": style,
            "duration_minutes": duration_minutes,
            "segments": segments,
            "status": "draft",
            "created_by": user["user_id"], "created_at": now,
        }
        await db.podcasts.insert_one(podcast)
        return {k: v for k, v in podcast.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/podcasts")
    async def list_podcasts(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        items = await db.podcasts.find({"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"podcasts": items}

    # ============ Full Media Analytics Dashboard ============

    @api_router.get("/workspaces/{workspace_id}/media/analytics")
    async def get_media_analytics(workspace_id: str, request: Request, days: int = 30):
        """Full media analytics dashboard"""
        await _authed_user(request, workspace_id)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Summary
        total_items = await db.media_items.count_documents({"workspace_id": workspace_id})
        total_videos = await db.media_items.count_documents({"workspace_id": workspace_id, "type": "video"})
        total_audio = await db.media_items.count_documents({"workspace_id": workspace_id, "type": "audio"})
        total_images = await db.media_items.count_documents({"workspace_id": workspace_id, "type": "image"})

        # Cost breakdown by provider
        cost_pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {"_id": {"type": "$type", "provider": "$provider"}, "count": {"$sum": 1}, "total_size": {"$sum": "$file_size"}}}
        ]
        cost_breakdown = []
        async for doc in db.media_metrics.aggregate(cost_pipeline):
            cost_breakdown.append({"type": doc["_id"]["type"], "provider": doc["_id"]["provider"], "count": doc["count"], "total_size_bytes": doc.get("total_size", 0)})

        # Performance (avg generation time by type)
        perf_pipeline = [
            {"$match": {"workspace_id": workspace_id, "success": True}},
            {"$group": {"_id": "$type", "avg_duration_ms": {"$avg": "$duration_ms"}, "count": {"$sum": 1}}}
        ]
        performance = []
        async for doc in db.media_metrics.aggregate(perf_pipeline):
            performance.append({"type": doc["_id"], "avg_duration_ms": round(doc.get("avg_duration_ms") or 0), "count": doc["count"]})

        # Daily generation timeseries
        daily_pipeline = [
            {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "count": {"$sum": 1}}}
        ]
        timeseries = [{"date": d["_id"], "generations": d["count"]} async for d in db.media_metrics.aggregate(daily_pipeline)]

        # Storage usage
        size_pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {"_id": None, "total_bytes": {"$sum": "$file_size"}}}
        ]
        size_result = await db.media_items.aggregate(size_pipeline).to_list(1)
        total_storage = size_result[0]["total_bytes"] if size_result else 0

        return {
            "summary": {"total_items": total_items, "videos": total_videos, "audio": total_audio, "images": total_images, "storage_mb": round(total_storage / 1048576, 2)},
            "cost_breakdown": cost_breakdown,
            "performance": performance,
            "timeseries": sorted(timeseries, key=lambda x: x["date"]),
        }

    # ============ Media Scheduling ============

    @api_router.post("/workspaces/{workspace_id}/media/schedules")
    async def create_media_schedule(workspace_id: str, request: Request):
        """Schedule recurring media generation"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        sched_id = f"msched_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        schedule = {
            "schedule_id": sched_id, "workspace_id": workspace_id,
            "name": body.get("name", "Media Schedule"),
            "type": body.get("type", "text_to_video"),  # text_to_video, text_to_speech, podcast
            "config": body.get("config") or {},  # prompt, voice, size, etc.
            "interval_hours": body.get("interval_hours", 24),
            "enabled": True,
            "last_run_at": None, "next_run_at": now,
            "run_count": 0,
            "created_by": user["user_id"], "created_at": now,
        }
        await db.media_schedules.insert_one(schedule)
        return {k: v for k, v in schedule.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/media/schedules")
    async def list_media_schedules(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        items = await db.media_schedules.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(20)
        return {"schedules": items}

    @api_router.delete("/media/schedules/{schedule_id}")
    async def delete_media_schedule(schedule_id: str, request: Request):
        await get_current_user(request)
        result = await db.media_schedules.delete_one({"schedule_id": schedule_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Schedule not found")
        return {"message": "Deleted"}

    # ============ Smart Folders ============

    @api_router.get("/workspaces/{workspace_id}/media/smart-folders")
    async def get_smart_folders(workspace_id: str, request: Request):
        """Get smart folder counts (Recent, Starred, by type)"""
        await _authed_user(request, workspace_id)
        recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent = await db.media_items.count_documents({"workspace_id": workspace_id, "created_at": {"$gte": recent_cutoff}})
        starred = await db.media_items.count_documents({"workspace_id": workspace_id, "tags": "starred"})
        videos = await db.media_items.count_documents({"workspace_id": workspace_id, "type": "video"})
        audio = await db.media_items.count_documents({"workspace_id": workspace_id, "type": "audio"})
        images = await db.media_items.count_documents({"workspace_id": workspace_id, "type": "image"})
        return {"smart_folders": [
            {"name": "Recent", "count": recent, "filter": "recent"},
            {"name": "Starred", "count": starred, "filter": "starred"},
            {"name": "Videos", "count": videos, "filter": "video"},
            {"name": "Audio", "count": audio, "filter": "audio"},
            {"name": "Images", "count": images, "filter": "image"},
        ]}

    # ============ Media Version History ============

    @api_router.get("/media/{media_id}/versions")
    async def get_media_versions(media_id: str, request: Request):
        await get_current_user(request)
        versions = await db.media_versions.find({"media_id": media_id}, {"_id": 0}).sort("version", -1).to_list(20)
        return {"versions": versions}

    @api_router.post("/media/{media_id}/versions/{version}/restore")
    async def restore_media_version(media_id: str, version: int, request: Request):
        await get_current_user(request)
        ver = await db.media_versions.find_one({"media_id": media_id, "version": version}, {"_id": 0})
        if not ver:
            raise HTTPException(404, "Version not found")
        # Restore the data
        if ver.get("data_ref"):
            await db.media_data.update_one({"media_id": media_id}, {"$set": {"data": ver["data_ref"]}})
        item = await db.media_items.find_one({"media_id": media_id})
        new_ver = (item.get("version", 1) if item else 1) + 1
        await db.media_items.update_one({"media_id": media_id}, {"$set": {"version": new_ver}})
        return {"restored_version": version, "new_version": new_ver}


    # ============ Streaming TTS ============

    @api_router.post("/workspaces/{workspace_id}/audio/tts-stream")
    async def streaming_tts(workspace_id: str, request: Request):
        """Streaming TTS — returns full audio as base64 (simulated streaming for HTTP)"""
        await _authed_user(request, workspace_id)
        body = await request.json()
        text = body.get("text", "")
        voice = body.get("voice", "alloy")
        speed = body.get("speed", 1.0)
        if not text:
            raise HTTPException(400, "Text required")

        from key_resolver import get_integration_key
        api_key = await get_integration_key(db, "OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(500, "TTS not configured")

        # Split long text into chunks for simulated streaming
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        audio_parts = []

        import httpx
        for chunk in chunks:
            async with httpx.AsyncClient(timeout=120.0) as _tts_client:
                _tts_resp = await _tts_client.post("https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "tts-1", "voice": voice, "input": chunk[:4096], "speed": speed})
                if _tts_resp.status_code != 200:
                    raise HTTPException(502, f"TTS API error: {_tts_resp.status_code}")
                audio_parts.append(base64.b64encode(_tts_resp.content).decode("utf-8"))

        return {"chunks": audio_parts, "total_chunks": len(audio_parts), "voice": voice}

    # ============ Video Composition ============

    @api_router.post("/workspaces/{workspace_id}/video/compose")
    async def compose_video(workspace_id: str, request: Request):
        """Compose a video from multiple clips with transitions and overlays"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        clips = body.get("clips") or []
        audio_track = body.get("audio_track")
        text_overlays = body.get("text_overlays") or []
        transitions = body.get("transitions") or []
        output = body.get("output", {"resolution": "1280x720", "format": "mp4"})

        if not clips:
            raise HTTPException(400, "At least one clip required")

        # Create composition job
        job_id = f"mjob_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        job = {
            "job_id": job_id, "workspace_id": workspace_id,
            "type": "video_compose", "provider": "internal",
            "input": {"clips": clips, "audio_track": audio_track, "text_overlays": text_overlays, "transitions": transitions, "output": output},
            "status": "queued", "progress": 0,
            "requested_by": user["user_id"], "created_at": now,
        }
        await db.media_jobs.insert_one(job)
        return {k: v for k, v in job.items() if k != "_id"}

    # ============ Storage Overview ============

    @api_router.get("/workspaces/{workspace_id}/media/storage")
    async def get_storage_overview(workspace_id: str, request: Request):
        """Get storage usage breakdown"""
        await _authed_user(request, workspace_id)

        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": "$type",
                "count": {"$sum": 1},
                "total_bytes": {"$sum": "$file_size"},
            }}
        ]
        breakdown = []
        total_bytes = 0
        async for doc in db.media_items.aggregate(pipeline):
            b = doc.get("total_bytes", 0)
            total_bytes += b
            breakdown.append({"type": doc["_id"], "count": doc["count"], "size_bytes": b, "size_mb": round(b / 1048576, 2)})

        return {
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / 1048576, 2),
            "total_gb": round(total_bytes / 1073741824, 3),
            "breakdown": breakdown,
            "limit_gb": 10,  # Free tier limit
            "usage_percent": round(total_bytes / (10 * 1073741824) * 100, 1),
        }

    # Social publishing handled by routes_social_publish.py

    # ============ Upload with drag-and-drop support ============

    @api_router.post("/workspaces/{workspace_id}/media/upload")
    async def upload_media_file(workspace_id: str, request: Request):
        """Upload a media file directly (for dropzone)"""
        user = await _authed_user(request, workspace_id)
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file provided")

        content = await file.read()
        filename = file.filename or "upload"
        mime = file.content_type or "application/octet-stream"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Determine type
        media_type = "image"
        if ext in ("mp4", "webm", "mov", "avi"):
            media_type = "video"
        elif ext in ("mp3", "wav", "ogg", "flac", "aac", "m4a"):
            media_type = "audio"
        elif ext in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
            media_type = "image"

        media_id = f"upl_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        b64 = base64.b64encode(content).decode("utf-8")

        await db.media_items.insert_one({
            "media_id": media_id, "workspace_id": workspace_id,
            "type": media_type, "name": filename,
            "prompt": f"Uploaded: {filename}", "provider": "upload",
            "mime_type": mime, "file_size": len(content),
            "created_by": user["user_id"], "created_at": now,
            "tags": ["uploaded", ext], "folder": form.get("folder"),
        })
        await db.media_data.insert_one({"media_id": media_id, "data": b64, "created_at": now})

        return {"media_id": media_id, "type": media_type, "filename": filename, "size": len(content)}
