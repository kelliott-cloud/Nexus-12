"""Built-in File Storage / Drive — workspace + personal drives with folders, trash, sharing"""
import uuid
import base64
import logging
import re as _re
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso, sanitize_filename

logger = logging.getLogger(__name__)

STORAGE_LIMITS = {"free": 500 * 1024 * 1024, "starter": 5 * 1024**3, "pro": 10 * 1024**3, "team": 10 * 1024**3, "enterprise": 100 * 1024**3}



def register_drive_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.post("/drive/upload")
    async def upload_file(request: Request):
        user = await get_current_user(request)
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(400, "No file")
        workspace_id = form.get("workspace_id", "")
        parent_id = form.get("parent_id")
        path = form.get("path", "/")
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(413, "File exceeds 100MB limit")
        file_id = f"df_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        record = {
            "file_id": file_id, "workspace_id": workspace_id, "user_id": user["user_id"],
            "name": file.filename or "upload", "path": path,
            "type": "file", "mime_type": file.content_type or "application/octet-stream",
            "size": len(content), "parent_id": parent_id,
            "is_trashed": False, "shared": False,
            "created_at": now, "updated_at": now,
        }
        await db.drive_files.insert_one(record)
        # Store binary data in chunks
        chunk_size = 4 * 1024 * 1024  # 4MB chunks
        for i in range(0, len(content), chunk_size):
            chunk = base64.b64encode(content[i:i+chunk_size]).decode("utf-8")
            await db.drive_file_data.insert_one({"file_id": file_id, "chunk_index": i // chunk_size, "data": chunk, "created_at": now})
        await db.drive_activity.insert_one({"file_id": file_id, "user_id": user["user_id"], "action": "upload", "timestamp": now})
        return {k: v for k, v in record.items() if k != "_id"}

    @api_router.post("/drive/folder")
    async def create_folder(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        folder_id = f"df_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        folder = {
            "file_id": folder_id, "workspace_id": body.get("workspace_id", ""),
            "user_id": user["user_id"], "name": body.get("name", "New Folder"),
            "path": body.get("path", "/"), "type": "folder",
            "parent_id": body.get("parent_id"), "is_trashed": False,
            "created_at": now, "updated_at": now,
        }
        await db.drive_files.insert_one(folder)
        return {k: v for k, v in folder.items() if k != "_id"}

    @api_router.get("/drive/list")
    async def list_files(request: Request, workspace_id: str = "", path: str = "/", parent_id: Optional[str] = None, include_trashed: bool = False):
        user = await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if parent_id:
            query["parent_id"] = parent_id
        else:
            query["path"] = path
        if not include_trashed:
            query["is_trashed"] = False
        files = await db.drive_files.find(query, {"_id": 0}).sort([("type", -1), ("name", 1)]).to_list(200)
        return {"files": files, "path": path}

    async def _verify_drive_access(user, file_id):
        """Verify user has access to the file's workspace."""
        f = await db.drive_files.find_one({"file_id": file_id}, {"_id": 0, "workspace_id": 1, "user_id": 1})
        if not f:
            raise HTTPException(404, "File not found")
        ws_id = f.get("workspace_id", "")
        if ws_id:
            from nexus_utils import require_workspace_access
            await require_workspace_access(db, user, ws_id)
        elif f.get("user_id") != user["user_id"]:
            raise HTTPException(403, "Access denied")
        return f

    @api_router.get("/drive/file/{file_id}")
    async def get_file_metadata(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        f = await db.drive_files.find_one({"file_id": file_id}, {"_id": 0})
        if not f:
            raise HTTPException(404, "File not found")
        return f

    @api_router.get("/drive/file/{file_id}/download")
    async def download_file(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        chunks = await db.drive_file_data.find({"file_id": file_id}, {"_id": 0}).sort("chunk_index", 1).to_list(100)
        if not chunks:
            raise HTTPException(404, "File data not found")
        combined = "".join(c["data"] for c in chunks)
        meta = await db.drive_files.find_one({"file_id": file_id}, {"_id": 0, "name": 1, "mime_type": 1})
        return {"data": combined, "filename": meta.get("name", "file") if meta else "file", "mime_type": meta.get("mime_type", "application/octet-stream") if meta else "application/octet-stream"}

    @api_router.put("/drive/file/{file_id}/move")
    async def move_file(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        body = await request.json()
        await db.drive_files.update_one({"file_id": file_id}, {"$set": {"parent_id": body.get("parent_id"), "path": body.get("path", "/"), "updated_at": now_iso()}})
        return await db.drive_files.find_one({"file_id": file_id}, {"_id": 0})

    @api_router.put("/drive/file/{file_id}/rename")
    async def rename_file(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        body = await request.json()
        await db.drive_files.update_one({"file_id": file_id}, {"$set": {"name": body.get("name", ""), "updated_at": now_iso()}})
        return await db.drive_files.find_one({"file_id": file_id}, {"_id": 0})

    @api_router.delete("/drive/file/{file_id}")
    async def trash_file(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        await db.drive_files.update_one({"file_id": file_id}, {"$set": {"is_trashed": True, "updated_at": now_iso()}})
        await db.drive_activity.insert_one({"file_id": file_id, "user_id": user["user_id"], "action": "trash", "timestamp": now_iso()})
        return {"message": "Moved to trash"}

    @api_router.post("/drive/file/{file_id}/restore")
    async def restore_file(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        await db.drive_files.update_one({"file_id": file_id}, {"$set": {"is_trashed": False, "updated_at": now_iso()}})
        return {"message": "Restored"}

    @api_router.get("/drive/search")
    async def search_drive(request: Request, q: str = "", workspace_id: str = ""):
        user = await _authed_user(request, workspace_id)
        from nexus_utils import now_iso, safe_regex
        query = {"is_trashed": False, "name": {"$regex": safe_regex(q), "$options": "i"}}
        if workspace_id:
            query["workspace_id"] = workspace_id
        user = await _authed_user(request, workspace_id)
        from nexus_utils import now_iso, safe_regex
        query = {"is_trashed": False, "name": {"$regex": safe_regex(q), "$options": "i"}}
        if workspace_id:
            query["workspace_id"] = workspace_id
        files = await db.drive_files.find(query, {"_id": 0}).limit(50).to_list(50)
        return {"files": files, "query": q}

    @api_router.post("/drive/file/{file_id}/share")
    async def share_file(file_id: str, request: Request):
        user = await get_current_user(request)
        await _verify_drive_access(user, file_id)
        body = await request.json()
        import secrets
        token = secrets.token_urlsafe(16)
        share_id = f"ds_{uuid.uuid4().hex[:8]}"
        expires = (datetime.now(timezone.utc) + timedelta(hours=body.get("expires_hours", 48))).isoformat()
        await db.drive_shares.insert_one({
            "share_id": share_id, "file_id": file_id, "token": token,
            "permissions": body.get("permissions", "view"),
            "expires_at": expires, "created_at": now_iso(),
        })
        await db.drive_files.update_one({"file_id": file_id}, {"$set": {"shared": True}})
        return {"share_url": f"/api/drive/shared/{token}", "token": token, "expires_at": expires}

    @api_router.get("/drive/shared/{token}")
    async def get_shared_file(token: str):
        share = await db.drive_shares.find_one({"token": token}, {"_id": 0})
        if not share:
            raise HTTPException(404, "Share link not found")
        if share.get("expires_at", "") < now_iso():
            raise HTTPException(410, "Share link expired")
        f = await db.drive_files.find_one({"file_id": share["file_id"]}, {"_id": 0})
        return {"file": f, "permissions": share.get("permissions", "view")}

    @api_router.get("/drive/storage-usage")
    async def get_storage_usage(request: Request, workspace_id: str = ""):
        user = await _authed_user(request, workspace_id)
        query = {"is_trashed": False, "type": "file"}
        if workspace_id:
            query["workspace_id"] = workspace_id
        else:
            query["user_id"] = user["user_id"]
        pipeline = [{"$match": query}, {"$group": {"_id": None, "total": {"$sum": "$size"}, "count": {"$sum": 1}}}]
        result = await db.drive_files.aggregate(pipeline).to_list(1)
        used = result[0]["total"] if result else 0
        count = result[0]["count"] if result else 0
        plan = user.get("plan", "free")
        limit = STORAGE_LIMITS.get(plan, STORAGE_LIMITS["free"])
        return {"used_bytes": used, "used_mb": round(used / 1048576, 2), "limit_bytes": limit, "limit_gb": round(limit / 1073741824, 1), "usage_pct": round(used / max(limit, 1) * 100, 1), "file_count": count}
