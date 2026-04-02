"""Repository — Org-level file store with indexing, search, and preview.
Integration Settings — Admin + Org-level API key management.
Per-Tenant Encryption — Org-specific encryption keys."""
import uuid
import os
import base64
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)



INTEGRATION_KEYS = [
    {"key": "SENDGRID_API_KEY", "name": "SendGrid (Email)", "provider": "sendgrid", "category": "email"},
    {"key": "RESEND_API_KEY", "name": "Resend (Email)", "provider": "resend", "category": "email"},
    {"key": "ELEVENLABS_API_KEY", "name": "ElevenLabs (Voice)", "provider": "elevenlabs", "category": "voice"},
    {"key": "SUNO_API_KEY", "name": "Suno (Music)", "provider": "suno", "category": "music"},
    {"key": "UDIO_API_KEY", "name": "Udio (Music)", "provider": "udio", "category": "music"},
    {"key": "YOUTUBE_API_KEY", "name": "YouTube", "provider": "youtube", "category": "publishing"},
    {"key": "TWITTER_API_KEY", "name": "Twitter/X", "provider": "twitter", "category": "publishing"},
    {"key": "MICROSOFT_CLIENT_ID", "name": "Microsoft OAuth", "provider": "microsoft", "category": "auth"},
    {"key": "MICROSOFT_CLIENT_SECRET", "name": "Microsoft OAuth Secret", "provider": "microsoft", "category": "auth"},
    {"key": "META_APP_ID", "name": "Meta OAuth", "provider": "meta", "category": "auth"},
    {"key": "META_APP_SECRET", "name": "Meta OAuth Secret", "provider": "meta", "category": "auth"},
    {"key": "PAYPAL_CLIENT_ID", "name": "PayPal", "provider": "paypal", "category": "payments"},
    {"key": "PAYPAL_CLIENT_SECRET", "name": "PayPal Secret", "provider": "paypal", "category": "payments"},
    {"key": "SLACK_CLIENT_ID", "name": "Slack", "provider": "slack", "category": "messaging"},
    {"key": "SLACK_CLIENT_SECRET", "name": "Slack Secret", "provider": "slack", "category": "messaging"},
    {"key": "DISCORD_BOT_TOKEN", "name": "Discord Bot", "provider": "discord", "category": "messaging"},
    {"key": "MSTEAMS_CLIENT_ID", "name": "Microsoft Teams", "provider": "msteams", "category": "messaging"},
    {"key": "MSTEAMS_CLIENT_SECRET", "name": "Microsoft Teams Secret", "provider": "msteams", "category": "messaging"},
    {"key": "MATTERMOST_BOT_TOKEN", "name": "Mattermost Bot", "provider": "mattermost", "category": "messaging"},
    {"key": "WHATSAPP_API_TOKEN", "name": "WhatsApp Business", "provider": "whatsapp", "category": "messaging"},
    {"key": "SIGNAL_API_KEY", "name": "Signal", "provider": "signal", "category": "messaging"},
    {"key": "TELEGRAM_BOT_TOKEN", "name": "Telegram Bot", "provider": "telegram", "category": "messaging"},
    {"key": "ZOOM_CLIENT_ID", "name": "Zoom", "provider": "zoom", "category": "meetings"},
    {"key": "ZOOM_CLIENT_SECRET", "name": "Zoom Secret", "provider": "zoom", "category": "meetings"},
    {"key": "GOOGLE_DRIVE_CLIENT_ID", "name": "Google Drive", "provider": "google_drive", "category": "storage"},
    {"key": "GOOGLE_DRIVE_CLIENT_SECRET", "name": "Google Drive Secret", "provider": "google_drive", "category": "storage"},
    {"key": "DROPBOX_APP_KEY", "name": "Dropbox", "provider": "dropbox", "category": "storage"},
    {"key": "DROPBOX_APP_SECRET", "name": "Dropbox Secret", "provider": "dropbox", "category": "storage"},
    {"key": "BOX_CLIENT_ID", "name": "Box", "provider": "box", "category": "storage"},
    {"key": "BOX_CLIENT_SECRET", "name": "Box Secret", "provider": "box", "category": "storage"},
    {"key": "GITHUB_CLIENT_ID", "name": "GitHub", "provider": "github", "category": "development"},
    {"key": "GITHUB_CLIENT_SECRET", "name": "GitHub Secret", "provider": "github", "category": "development"},
    {"key": "GITHUB_PAT", "name": "GitHub PAT", "provider": "github", "category": "development"},
    {"key": "MANUS_API_KEY", "name": "Manus AI", "provider": "manus", "category": "ai"},
]


from nexus_utils import now_iso, safe_regex

def register_repository_routes(api_router, db, get_current_user):

    # ======================================================
    # ORG REPOSITORY — File Store
    # ======================================================

    @api_router.post("/orgs/{org_id}/repository/upload")
    async def upload_to_repository(org_id: str, request: Request):
        user = await get_current_user(request)
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file provided")
        content = await file.read()
        filename = file.filename or "upload"
        mime = file.content_type or "application/octet-stream"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Determine preview type
        preview_type = "none"
        if ext in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
            preview_type = "image"
        elif ext == "pdf":
            preview_type = "pdf"
        elif ext in ("doc", "docx"):
            preview_type = "document"
        elif ext in ("mp4", "webm", "mov"):
            preview_type = "video"
        elif ext in ("mp3", "wav", "ogg"):
            preview_type = "audio"
        elif ext in ("txt", "md", "csv", "json", "xml", "py", "js", "html", "css"):
            preview_type = "text"

        file_id = f"rf_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        b64 = base64.b64encode(content).decode("utf-8")

        # Extract text for indexing
        index_text = ""
        if preview_type == "text":
            try:
                index_text = content.decode("utf-8", errors="replace")[:5000]
            except Exception as _e:
                logger.warning(f"Caught exception: {_e}")

        record = {
            "file_id": file_id, "org_id": org_id,
            "filename": filename, "ext": ext, "mime_type": mime,
            "size": len(content), "preview_type": preview_type,
            "folder": form.get("folder") or "/",
            "tags": [], "description": form.get("description") or "",
            "index_text": index_text,
            "uploaded_by": user["user_id"],
            "uploaded_by_name": user.get("name", ""),
            "created_at": now, "updated_at": now,
        }
        await db.org_repository.insert_one(record)
        await db.repo_file_data.insert_one({"file_id": file_id, "data": b64, "created_at": now})

        return {k: v for k, v in record.items() if k not in ("_id", "index_text")}

    @api_router.get("/orgs/{org_id}/repository")
    async def list_repository(org_id: str, request: Request, search: Optional[str] = None, folder: Optional[str] = None, preview_type: Optional[str] = None, limit: int = 50, offset: int = 0):
        await get_current_user(request)
        query = {"org_id": org_id}
        if search:
            query["$or"] = [
                {"filename": {"$regex": safe_regex(search), "$options": "i"}},
                {"description": {"$regex": safe_regex(search), "$options": "i"}},
                {"tags": {"$regex": safe_regex(search), "$options": "i"}},
                {"index_text": {"$regex": safe_regex(search), "$options": "i"}},
            ]
        if folder:
            query["folder"] = folder
        if preview_type:
            query["preview_type"] = preview_type

        files = await db.org_repository.find(query, {"_id": 0, "index_text": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.org_repository.count_documents(query)
        return {"files": files, "total": total}

    @api_router.get("/repository/{file_id}")
    async def get_repo_file(file_id: str, request: Request):
        await get_current_user(request)
        record = await db.org_repository.find_one({"file_id": file_id}, {"_id": 0, "index_text": 0})
        if not record:
            raise HTTPException(404, "File not found")
        return record

    @api_router.get("/repository/{file_id}/data")
    async def get_repo_file_data(file_id: str, request: Request):
        await get_current_user(request)
        data = await db.repo_file_data.find_one({"file_id": file_id}, {"_id": 0})
        if not data:
            raise HTTPException(404, "File data not found")
        return {"file_id": file_id, "data": data["data"]}

    @api_router.get("/repository/{file_id}/preview")
    async def get_file_preview(file_id: str, request: Request):
        """Get file with metadata + preview data for inline rendering"""
        await get_current_user(request)
        record = await db.org_repository.find_one({"file_id": file_id}, {"_id": 0, "index_text": 0})
        if not record:
            raise HTTPException(404, "File not found")
        data = await db.repo_file_data.find_one({"file_id": file_id}, {"_id": 0})
        preview = None
        if data:
            if record["preview_type"] in ("image", "pdf", "video", "audio"):
                preview = {"data_url": f"data:{record['mime_type']};base64,{data['data']}", "type": record["preview_type"]}
            elif record["preview_type"] == "text":
                try:
                    text = base64.b64decode(data["data"]).decode("utf-8", errors="replace")[:10000]
                    preview = {"text": text, "type": "text"}
                except Exception as _e:
                    logger.warning(f"Caught exception: {_e}")
                    preview = {"type": "unsupported"}
            else:
                preview = {"type": "unsupported"}
        return {"file": record, "preview": preview}

    @api_router.put("/repository/{file_id}")
    async def update_repo_file(file_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        updates = {"updated_at": now_iso()}
        for key in ["description", "folder", "tags"]:
            if key in body:
                updates[key] = body[key]
        await db.org_repository.update_one({"file_id": file_id}, {"$set": updates})
        return await db.org_repository.find_one({"file_id": file_id}, {"_id": 0, "index_text": 0})

    @api_router.delete("/repository/{file_id}")
    async def delete_repo_file(file_id: str, request: Request):
        user = await get_current_user(request)
        f = await db.org_repository.find_one({"file_id": file_id}, {"org_id": 1})
        if not f:
            raise HTTPException(404, "File not found")
        if f.get("org_id"):
            member = await db.org_memberships.find_one({"org_id": f["org_id"], "user_id": user["user_id"]})
            if not member and user.get("platform_role") != "super_admin":
                raise HTTPException(403, "Access denied")
        await db.org_repository.delete_one({"file_id": file_id})
        await db.repo_file_data.delete_one({"file_id": file_id})
        return {"message": "Deleted"}

    @api_router.get("/orgs/{org_id}/repository/folders")
    async def list_repo_folders(org_id: str, request: Request):
        await get_current_user(request)
        pipeline = [
            {"$match": {"org_id": org_id}},
            {"$group": {"_id": "$folder", "count": {"$sum": 1}, "total_size": {"$sum": "$size"}}}
        ]
        folders = [{"folder": d["_id"], "count": d["count"], "size_bytes": d.get("total_size", 0)} async for d in db.org_repository.aggregate(pipeline)]
        return {"folders": folders}

    # ======================================================
    # INTEGRATION SETTINGS — Platform Admin + Org Admin
    # ======================================================

    @api_router.get("/admin/integrations")
    async def get_platform_integrations(request: Request):
        """Platform admin — view all integration key statuses"""
        await get_current_user(request)
        # Load saved keys from DB
        saved_keys = {}
        db_settings = await db.platform_settings.find({}, {"_id": 0}).to_list(100)
        for s in db_settings:
            if s.get("value"):
                saved_keys[s["key"]] = s["value"]
        
        results = []
        for integ in INTEGRATION_KEYS:
            # Check DB first, then env vars
            db_val = saved_keys.get(integ["key"], "")
            env_val = os.environ.get(integ["key"], "")
            val = db_val or env_val
            results.append({
                "key": integ["key"], "name": integ["name"],
                "provider": integ["provider"], "category": integ["category"],
                "configured": bool(val),
                "masked_value": f"{val[:4]}...{val[-4:]}" if val and len(val) > 8 else ("****" if val else None),
            })
        return {"integrations": results}

    @api_router.post("/admin/integrations")
    async def set_platform_integration(request: Request):
        """Platform admin — set a platform-level integration key"""
        user = await get_current_user(request)
        body = await request.json()
        key_name = body.get("key", "")
        key_value = body.get("value", "")
        valid_keys = {i["key"] for i in INTEGRATION_KEYS}
        if key_name not in valid_keys:
            raise HTTPException(400, f"Unknown key. Valid: {valid_keys}")
        # Store in database (env vars can't be changed at runtime, so store in DB)
        await db.platform_settings.update_one(
            {"key": key_name},
            {"$set": {"key": key_name, "value": key_value, "updated_by": user["user_id"], "updated_at": now_iso()}},
            upsert=True,
        )
        # Clear key resolution cache so new value is used immediately
        from key_resolver import clear_cache
        clear_cache()
        return {"key": key_name, "configured": bool(key_value)}

    @api_router.post("/admin/integrations/test")
    async def test_platform_integration(request: Request):
        """Test an integration key with format and/or API validation"""
        await get_current_user(request)
        body = await request.json()
        key_name = body.get("key", "")
        value = body.get("value", "")
        if not value:
            return {"valid": False, "message": "No key provided"}
        # Format validation
        if key_name.startswith("STRIPE") and not value.startswith("sk_") and not value.startswith("whsec_"):
            return {"valid": False, "message": "Stripe keys should start with 'sk_' or 'whsec_'"}
        if key_name == "SENDGRID_API_KEY" and not value.startswith("SG."):
            return {"valid": False, "message": "SendGrid keys should start with 'SG.'"}
        if key_name == "RESEND_API_KEY" and not value.startswith("re_"):
            return {"valid": False, "message": "Resend keys should start with 're_'"}
        if len(value) < 8:
            return {"valid": False, "message": "Key is too short"}
        return {"valid": True, "message": "Key format validated"}

    @api_router.get("/orgs/{org_id}/integrations")
    async def get_org_integrations(org_id: str, request: Request):
        """Org admin — view org-specific integration overrides"""
        await get_current_user(request)
        overrides = await db.org_integrations.find({"org_id": org_id}, {"_id": 0, "value": 0}).to_list(20)
        override_map = {o["key"]: o for o in overrides}
        results = []
        for integ in INTEGRATION_KEYS:
            override = override_map.get(integ["key"])
            results.append({
                "key": integ["key"], "name": integ["name"],
                "provider": integ["provider"], "category": integ["category"],
                "has_override": bool(override),
                "using": "org" if override else "platform",
            })
        return {"integrations": results}

    @api_router.post("/orgs/{org_id}/integrations")
    async def set_org_integration(org_id: str, request: Request):
        """Org admin — set an org-level integration key override"""
        user = await get_current_user(request)
        body = await request.json()
        key_name = body.get("key", "")
        key_value = body.get("value", "")
        
        # F3 fix: Validate key name against allowed integration keys
        valid_keys = {k["key"] for k in INTEGRATION_KEYS}
        if key_name not in valid_keys:
            raise HTTPException(400, f"Unsupported integration key: {key_name}. Valid keys: {', '.join(sorted(valid_keys))}")
        
        from encryption import get_fernet; fernet = get_fernet()
        encrypted = fernet.encrypt(key_value.encode()).decode() if key_value else ""
        await db.org_integrations.update_one(
            {"org_id": org_id, "key": key_name},
            {"$set": {"org_id": org_id, "key": key_name, "value_encrypted": encrypted, "updated_by": user["user_id"], "updated_at": now_iso()}},
            upsert=True,
        )
        # F2 fix: Clear key resolver cache after org-level update
        from key_resolver import clear_cache
        clear_cache()
        return {"key": key_name, "configured": bool(key_value)}

    @api_router.delete("/orgs/{org_id}/integrations/{key_name}")
    async def remove_org_integration(org_id: str, key_name: str, request: Request):
        await get_current_user(request)
        await db.org_integrations.delete_one({"org_id": org_id, "key": key_name})
        # F2 fix: Clear key resolver cache after org-level delete
        from key_resolver import clear_cache
        clear_cache()
        return {"message": "Override removed, falling back to platform default"}

    # ======================================================
    # PER-TENANT ENCRYPTION
    # ======================================================

    @api_router.get("/orgs/{org_id}/encryption-status")
    async def get_org_encryption_status(org_id: str, request: Request):
        await get_current_user(request)
        key_record = await db.org_encryption_keys.find_one({"org_id": org_id}, {"_id": 0, "key": 0})
        return {
            "org_id": org_id,
            "has_dedicated_key": bool(key_record),
            "created_at": key_record.get("created_at") if key_record else None,
            "encryption_level": "tenant-isolated" if key_record else "platform-shared",
        }

    @api_router.post("/orgs/{org_id}/encryption/generate-key")
    async def generate_org_encryption_key(org_id: str, request: Request):
        """Generate a dedicated encryption key for this org (per-tenant isolation)"""
        user = await get_current_user(request)
        existing = await db.org_encryption_keys.find_one({"org_id": org_id})
        if existing:
            return {"org_id": org_id, "status": "already_exists", "encryption_level": "tenant-isolated"}
        new_key = Fernet.generate_key().decode()
        await db.org_encryption_keys.insert_one({
            "org_id": org_id, "key": new_key,
            "created_by": user["user_id"], "created_at": now_iso(),
        })
        return {"org_id": org_id, "status": "generated", "encryption_level": "tenant-isolated"}
