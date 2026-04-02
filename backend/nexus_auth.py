"""Nexus Auth — Session validation and user authentication.
Extracted from server.py for modularity.
"""
import os
from datetime import datetime, timezone
from fastapi import HTTPException, Request


async def get_current_user_impl(db, request: Request):
    """Validate session and return the authenticated user."""
    session_token = request.cookies.get('session_token')
    if not session_token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            session_token = auth_header[7:].strip()
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = await db.user_sessions.find_one(
        {"session_token": session_token}, {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one(
        {"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0}
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Ensure platform_role is set — check env var first, then DB value
    SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "")
    if SUPER_ADMIN_EMAIL and user.get("email", "").lower() == SUPER_ADMIN_EMAIL.lower():
        if user.get("platform_role") != "super_admin":
            # Persist the role in DB so it survives across deployments
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"platform_role": "super_admin"}}
            )
        user["platform_role"] = "super_admin"
    elif not user.get("platform_role"):
        user["platform_role"] = "user"
    return user
