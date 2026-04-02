import bcrypt as _share_bcrypt
import secrets
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import HTTPException, Request
from typing import Optional


class ShareCreate(BaseModel):
    is_public: bool = True
    password: Optional[str] = None
    expires_in_days: int = 7


class ShareAccess(BaseModel):
    password: Optional[str] = None


def register_sharing_routes(api_router, db, get_current_user):
    @api_router.post("/channels/{channel_id}/share")
    async def create_share(channel_id: str, data: ShareCreate, request: Request):
        user = await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            raise HTTPException(404, "Channel not found")

        share_id = f"share_{secrets.token_urlsafe(12)}"
        share = {
            "share_id": share_id,
            "channel_id": channel_id,
            "workspace_id": channel.get("workspace_id"),
            "created_by": user["user_id"],
            "is_public": data.is_public,
            
            "password_hash": _share_bcrypt.hashpw(data.password.encode(), _share_bcrypt.gensalt()).decode() if not data.is_public and data.password else None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)).isoformat(),
            "views": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.shares.insert_one(share)
        result = await db.shares.find_one({"share_id": share_id}, {"_id": 0})
        return result

    @api_router.get("/shares/{share_id}")
    async def get_share_info(share_id: str):
        share = await db.shares.find_one({"share_id": share_id}, {"_id": 0})
        if not share:
            raise HTTPException(404, "Share not found")
        expires_at = datetime.fromisoformat(share["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(410, "Share link has expired")
        return {
            "share_id": share["share_id"],
            "is_public": share["is_public"],
            "has_password": bool(share.get("password")),
            "views": share.get("views", 0),
            "created_at": share["created_at"]
        }

    @api_router.post("/replay/{share_id}")
    async def get_replay(share_id: str, data: ShareAccess = None, request: Request = None):
        share = await db.shares.find_one({"share_id": share_id}, {"_id": 0})
        if not share:
            raise HTTPException(404, "Share not found")

        expires_at = datetime.fromisoformat(share["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(410, "Share link has expired")

        if not share["is_public"]:
            stored_hash = share.get("password_hash", "")
            if not data or not data.password or not stored_hash or not _share_bcrypt.checkpw(data.password.encode(), stored_hash.encode()):
                raise HTTPException(403, "Invalid password")

        ip = request.client.host if request and request.client else "unknown"
        rate_key = f"replay:{ip}:{share_id}"
        now_ts = datetime.now(timezone.utc).timestamp()
        existing = await db.replay_rate_limits.find_one({"key": rate_key})
        if existing:
            attempts = [t for t in (existing.get("attempts") or []) if now_ts - t < 60]
            if len(attempts) >= 10:
                raise HTTPException(429, "Too many replay requests. Please wait a moment.")
            attempts.append(now_ts)
            await db.replay_rate_limits.update_one({"key": rate_key}, {"$set": {"attempts": attempts}})
        else:
            await db.replay_rate_limits.update_one(
                {"key": rate_key}, {"$set": {"attempts": [now_ts]}}, upsert=True
            )

        await db.shares.update_one({"share_id": share_id}, {"$inc": {"views": 1}})

        channel = await db.channels.find_one({"channel_id": share["channel_id"]}, {"_id": 0})
        messages = await db.messages.find(
            {"channel_id": share["channel_id"]}, {"_id": 0}
        ).sort("created_at", 1).to_list(500)
        workspace = await db.workspaces.find_one(
            {"workspace_id": share.get("workspace_id")}, {"_id": 0, "name": 1, "workspace_id": 1}
        )

        return {
            "channel": channel,
            "workspace": workspace,
            "messages": messages,
            "share": {"share_id": share["share_id"], "views": share.get("views", 0) + 1}
        }

    @api_router.get("/channels/{channel_id}/shares")
    async def get_channel_shares(channel_id: str, request: Request):
        await get_current_user(request)
        shares = await db.shares.find(
            {"channel_id": channel_id}, {"_id": 0, "password": 0}
        ).sort("created_at", -1).to_list(50)
        return shares
