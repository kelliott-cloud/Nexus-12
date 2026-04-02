"""Extracted from server.py — auto-generated module."""
import os
import uuid
import secrets
import asyncio
import logging
import time
import httpx
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

from nexus_utils import sanitize_html

def register_google_auth_routes(api_router, db, get_current_user):
    from nexus_models import SessionExchange, WorkspaceCreate, ChannelCreate, MessageCreate, WorkspaceUpdate, ChannelUpdate

    def _get_public_url(request: Request) -> str:
        """Get the public-facing URL, handling Kubernetes proxy correctly."""
        app_url = os.environ.get("APP_URL", "")
        if app_url:
            return app_url.rstrip("/")
        # Behind K8s ingress, use X-Forwarded headers
        proto = request.headers.get("x-forwarded-proto", "https")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        if host:
            return f"{proto}://{host}"
        # Last resort fallback
        return str(request.base_url).rstrip("/")

    
    @api_router.get("/auth/google/login")
    async def google_login_url(request: Request):
        """Generate Google OAuth login URL — custom bridge or Emergent managed."""
        try:
            from key_resolver import get_integration_key
            client_id = await get_integration_key(db, "GOOGLE_CLIENT_ID")
            client_secret = await get_integration_key(db, "GOOGLE_CLIENT_SECRET")
            
            if not client_id:
                settings = await db.platform_settings.find_one({"key": "google_oauth"}, {"_id": 0})
                if settings:
                    client_id = settings.get("client_id", "")
            
            if not client_id:
                return {"configured": False, "url": None, "use_emergent_bridge": True}
            redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", f"{_get_public_url(request)}/api/auth/google/callback")
            state_token = secrets.token_urlsafe(32)
            await db.oauth_states.insert_one({"state": state_token, "created_at": datetime.now(timezone.utc).isoformat()})
            import urllib.parse
            params = urllib.parse.urlencode({
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "select_account",
                "state": state_token,
            })
            return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}
        except Exception as e:
            logger.warning(f"Google OAuth setup error: {e}")
            return {"configured": False, "url": None}
    
    @api_router.get("/auth/google/callback")
    async def google_callback(request: Request, code: str = "", state: str = "", response: Response = None):
        """Handle Google OAuth callback — exchange code for tokens, create/login user."""
        if not code:
            raise HTTPException(400, "No authorization code received from Google")
        # Validate CSRF state
        if state:
            stored = await db.oauth_states.find_one_and_delete({"state": state})
            if not stored:
                raise HTTPException(400, "Invalid or expired OAuth state")
        
        from key_resolver import get_integration_key
        client_id = await get_integration_key(db, "GOOGLE_CLIENT_ID")
        client_secret = await get_integration_key(db, "GOOGLE_CLIENT_SECRET")
        if not client_id:
            settings = await db.platform_settings.find_one({"key": "google_oauth"}, {"_id": 0})
            if settings:
                client_id = settings.get("client_id", "")
                client_secret = settings.get("client_secret", "")
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", f"{_get_public_url(request)}/api/auth/google/callback")
        
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
        
        if token_resp.status_code != 200:
            logger.error(f"Google token exchange failed: {token_resp.text[:200]}")
            raise HTTPException(401, "Google authentication failed")
        
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(401, "No access token from Google")
        
        # Get user info
        async with httpx.AsyncClient() as client:
            user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                          headers={"Authorization": f"Bearer {access_token}"})
        
        if user_resp.status_code != 200:
            raise HTTPException(401, "Failed to get user info from Google")
        
        google_user = user_resp.json()
        email = google_user.get("email", "")
        name = google_user.get("name", email.split("@")[0])
        picture = google_user.get("picture", "")
        
        if not email:
            raise HTTPException(401, "No email in Google profile")
        
        # Create or update user
        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            user_id = existing["user_id"]
            await db.users.update_one({"email": email}, {"$set": {"name": name, "picture": picture}})
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id, "email": email, "name": name, "picture": picture,
                "auth_type": "google", "email_verified": True, "platform_role": "user",
                "language": "en", "plan": "free",
                "usage": {"ai_collaboration": 0, "reset_date": datetime.now(timezone.utc).isoformat()},
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create session
        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "session_token": session_token, "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        })
        
        # Redirect to dashboard with cookie set
        from fastapi.responses import RedirectResponse
        app_url = _get_public_url(request)
        redirect = RedirectResponse(url=f"{app_url}/dashboard", status_code=302)
        redirect.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)
        return redirect
    
    @api_router.post("/auth/session")
    async def exchange_session(data: SessionExchange, response: Response):
        """Emergent Google Auth bridge — exchanges session_id for user data and session cookie."""
        logger.info(f"Session exchange requested (session_id length: {len(data.session_id)})")
        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                resp = await http_client.get(
                    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                    headers={"X-Session-ID": data.session_id}
                )
        except Exception as e:
            logger.error(f"Emergent session exchange network error: {e}")
            raise HTTPException(status_code=502, detail="Authentication service unavailable. Please try again.")
        if resp.status_code != 200:
            logger.warning(f"Emergent session exchange returned {resp.status_code}: {resp.text[:200]}")
            raise HTTPException(status_code=401, detail="Invalid or expired session. Please try logging in again.")

        session_data = resp.json()
        email = session_data["email"]
        name = session_data["name"]
        picture = session_data.get("picture", "")
        session_token = session_data["session_token"]

        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            user_id = existing["user_id"]
            await db.users.update_one({"email": email}, {"$set": {"name": name, "picture": picture}})
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id, "email": email, "name": name, "picture": picture,
                "auth_type": "google", "platform_role": "user", "language": "en", "plan": "free",
                "usage": {"ai_collaboration": 0, "reset_date": datetime.now(timezone.utc).isoformat()},
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        await db.user_sessions.insert_one({
            "user_id": user_id, "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)

        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        user_data = dict(user) if user else {"user_id": user_id, "email": email, "name": name}
        user_data["session_token"] = session_token
        return user_data
    
    @api_router.get("/auth/me")
    async def get_me(request: Request):
        session_token = request.cookies.get('session_token')
        if not session_token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user = await get_current_user(request)
        # Add ToS status
        from routes_legal import TOS_VERSION
        user["tos_current_version"] = TOS_VERSION
        user["tos_needs_acceptance"] = user.get("tos_version") != TOS_VERSION
        return user
    
    
    @api_router.put("/auth/profile")
    async def update_profile(request: Request):
        """Update user profile (display name, avatar, timezone)"""
        user = await get_current_user(request)
        body = await request.json()
        updates = {}
        if "name" in body and body["name"].strip():
            updates["name"] = body["name"].strip()
        if "picture" in body and isinstance(body["picture"], str):
            if body["picture"].startswith("data:image/") and len(body["picture"]) < 500000:
                updates["picture"] = body["picture"]
        if "timezone" in body and isinstance(body["timezone"], str) and len(body["timezone"]) < 50:
            updates["timezone"] = body["timezone"]
        if updates:
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
        return {"message": "Profile updated"}
    
    @api_router.post("/auth/logout")
    async def logout(request: Request, response: Response):
        session_token = request.cookies.get('session_token')
        if session_token:
            await db.user_sessions.delete_one({"session_token": session_token})
        response.delete_cookie(key="session_token", path="/", samesite="none", secure=True)
        return {"message": "Logged out"}
    
