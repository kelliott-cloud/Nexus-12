import uuid
import secrets
import bcrypt
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)


class UserRegister(BaseModel):
    email: str
    password: str
    name: str


class UserLogin(BaseModel):
    email: str
    password: str


class ForgotPasswordReq(BaseModel):
    email: str


class ResetPasswordReq(BaseModel):
    token: str
    new_password: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def register_auth_email_routes(api_router, db):

    async def _record_failed_attempt(db, email):
        """Record a failed login attempt and lock account if threshold reached."""
        MAX_ATTEMPTS = 5
        LOCKOUT_MINUTES = [1, 5, 15, 60]

        attempt = await db.login_attempts.find_one({"email": email}, {"_id": 0})
        if not attempt:
            await db.login_attempts.insert_one({
                "email": email, "count": 1, "first_attempt": datetime.now(timezone.utc).isoformat(),
                "locked_until": None, "lockout_count": 0,
            })
            return

        count = attempt.get("count", 0) + 1
        update = {"$set": {"count": count}}

        if count >= MAX_ATTEMPTS:
            lockout_idx = min(attempt.get("lockout_count", 0), len(LOCKOUT_MINUTES) - 1)
            lock_minutes = LOCKOUT_MINUTES[lockout_idx]
            lock_until = (datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)).isoformat()
            update["$set"]["locked_until"] = lock_until
            update["$set"]["count"] = 0
            update["$inc"] = {"lockout_count": 1}

        await db.login_attempts.update_one({"email": email}, update)
    @api_router.post("/auth/register")
    async def register(data: UserRegister, request: Request, response: Response):
        from nexus_utils import validate_password, normalize_email
        # Normalize email early
        data.email = normalize_email(data.email)
        # Password strength validation
        pw_error = validate_password(data.password)
        if pw_error:
            raise HTTPException(400, pw_error)
        import re as _re
        if not _re.search(r'[A-Z]', data.password):
            raise HTTPException(400, "Password must contain at least 1 uppercase letter")
        if not _re.search(r'[a-z]', data.password):
            raise HTTPException(400, "Password must contain at least 1 lowercase letter")
        if not _re.search(r'[0-9]', data.password):
            raise HTTPException(400, "Password must contain at least 1 number")

        existing = await db.users.find_one({"email": data.email}, {"_id": 0})
        if existing:
            # If user exists via Google auth (no password), allow them to add a password
            if existing.get("auth_type") == "google" and not existing.get("password_hash"):
                pw_hash = hash_password(data.password)
                await db.users.update_one(
                    {"email": data.email},
                    {"$set": {"password_hash": pw_hash, "auth_type": "both", "name": data.name or existing.get("name", "")}}
                )
                user_id = existing["user_id"]
                session_token = secrets.token_urlsafe(32)
                await db.user_sessions.insert_one({
                    "user_id": user_id,
                    "session_token": session_token,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                response.set_cookie(
                    key="session_token", value=session_token,
                    httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
                )
                user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
                return user
            raise HTTPException(400, "Email already registered. Try signing in instead.")

        user_id = f"user_{uuid.uuid4().hex[:12]}"
        pw_hash = hash_password(data.password)

        await db.users.insert_one({
            "user_id": user_id,
            "email": data.email,
            "name": data.name,
            "picture": "",
            "password_hash": pw_hash,
            "auth_type": "email",
            "email_verified": False,
            "platform_role": "user",
            "language": "en",
            "plan": "free",
            "usage": {"ai_collaboration": 0, "reset_date": datetime.now(timezone.utc).isoformat()},
            "tos_version": None,
            "tos_accepted_at": None,
            "beta_accepted_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        response.set_cookie(
            key="session_token", value=session_token,
            httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
        )

        user = await db.users.find_one(
            {"user_id": user_id},
            {"_id": 0, "password_hash": 0}
        )
        
        # Send verification email
        try:
            import secrets as _sec
            verify_token = _sec.token_urlsafe(32)
            await db.email_verifications.insert_one({
                "token": verify_token,
                "user_id": user_id,
                "email": data.email,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            })
            from routes_email import send_email
            import os
            app_url = os.environ.get("APP_URL", str(request.base_url).rstrip("/"))
            verify_url = f"{app_url}/api/auth/verify-email?token={verify_token}"
            await send_email(data.email, "Nexus — Verify Your Email",
                f"<h2>Welcome to Nexus!</h2><p>Click below to verify your email:</p>"
                f"<a href='{verify_url}' style='display:inline-block;padding:12px 24px;background:#10b981;color:white;border-radius:8px;text-decoration:none'>Verify Email</a>"
                f"<p>This link expires in 24 hours.</p>", db=db, user_id=user_id, action="verify_email")
        except Exception as _ve:
            logger.warning(f"Verification email failed: {_ve}")
        
        return user

    @api_router.post("/auth/login")
    async def login(data: UserLogin, response: Response):
        # Account lockout check
        lockout = await db.login_attempts.find_one({"email": data.email}, {"_id": 0})
        if lockout and lockout.get("locked_until"):
            locked_until = lockout["locked_until"]
            if isinstance(locked_until, str):
                locked_until = datetime.fromisoformat(locked_until)
            if locked_until > datetime.now(timezone.utc):
                remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
                raise HTTPException(429, f"Account locked due to too many failed attempts. Try again in {remaining} minutes.")

        user = await db.users.find_one({"email": data.email}, {"_id": 0})
        if not user:
            await _record_failed_attempt(db, data.email)
            raise HTTPException(401, "Invalid email or password. If you signed up with Google, use 'Sign in with Google' instead.")

        if not user.get("password_hash"):
            import os as _os
            super_email = _os.environ.get("SUPER_ADMIN_EMAIL", "")
            if super_email and data.email.lower() == super_email.lower():
                pw_hash = hash_password(data.password)
                await db.users.update_one(
                    {"email": data.email},
                    {"$set": {"password_hash": pw_hash, "auth_type": "both", "platform_role": "super_admin"}}
                )
                user["password_hash"] = pw_hash
                user["platform_role"] = "super_admin"
                logger.info(f"Super admin password set on first login for {data.email}")
            else:
                raise HTTPException(401, "This account uses Google login. Please use 'Sign in with Google' or contact your admin.")

        if not verify_password(data.password, user["password_hash"]):
            await _record_failed_attempt(db, data.email)
            raise HTTPException(401, "Invalid email or password")

        # Clear failed attempts on successful login
        await db.login_attempts.delete_one({"email": data.email})

        # Check if MFA is enabled — if so, create a challenge instead of a session
        if user.get("mfa_enabled"):
            challenge_token = secrets.token_urlsafe(16)
            await db.mfa_challenges.delete_many({"user_id": user["user_id"]})
            await db.mfa_challenges.insert_one({
                "user_id": user["user_id"],
                "email": user["email"],
                "challenge_token": challenge_token,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            })
            return {"mfa_required": True, "email": user["email"], "challenge_token": challenge_token}

        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip_address": "",
            "user_agent": "",
        })

        response.set_cookie(
            key="session_token", value=session_token,
            httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
        )

        safe_user = {k: v for k, v in user.items() if k != "password_hash"}
        safe_user["session_token"] = session_token
        return safe_user

    @api_router.post("/auth/forgot-password-legacy")
    async def forgot_password_legacy(data: ForgotPasswordReq):
        """Legacy endpoint — use /auth/forgot-password instead (now sends real email via Resend)"""
        return {"message": "Please use the updated forgot-password endpoint."}

    @api_router.get("/auth/verify-email")
    async def verify_email(token: str):
        """Verify a user's email address via token."""
        record = await db.email_verifications.find_one({"token": token}, {"_id": 0})
        if not record:
            raise HTTPException(400, "Invalid or expired verification link")
        if record.get("expires_at"):
            exp = record["expires_at"]
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                raise HTTPException(400, "Verification link has expired. Please request a new one.")
        await db.users.update_one(
            {"user_id": record["user_id"]},
            {"$set": {"email_verified": True, "email_verified_at": datetime.now(timezone.utc).isoformat()}}
        )
        await db.email_verifications.delete_one({"token": token})
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html><body style='font-family:sans-serif;text-align:center;padding:60px;background:#09090b;color:#fafafa'><h1>Email Verified!</h1><p>You can close this tab and return to Nexus.</p></body></html>")


    # === SESSION MANAGEMENT ===

    async def _get_current_user_for_sessions(request: Request):
        """Resolve current user from session token for session management endpoints."""
        token = request.cookies.get("session_token", "") or ""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            raise HTTPException(401, "Not authenticated")
        session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0, "user_id": 1, "expires_at": 1})
        if not session:
            raise HTTPException(401, "Session not found")
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(401, "User not found")
        return user

    @api_router.get("/user/sessions")
    async def list_sessions(request: Request):
        user = await _get_current_user_for_sessions(request)
        sessions = await db.user_sessions.find(
            {"user_id": user["user_id"], "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}},
            {"_id": 0, "session_token": 0}
        ).sort("created_at", -1).to_list(20)
        return sessions

    @api_router.delete("/user/sessions/{session_id}")
    async def revoke_session(session_id: str, request: Request):
        user = await _get_current_user_for_sessions(request)
        await db.user_sessions.delete_one({"user_id": user["user_id"], "session_token": session_id})
        return {"message": "Session revoked"}

    @api_router.delete("/user/sessions")
    async def revoke_all_sessions(request: Request):
        """Log out everywhere except current session."""
        user = await _get_current_user_for_sessions(request)
        current = request.cookies.get("session_token", "")
        await db.user_sessions.delete_many({"user_id": user["user_id"], "session_token": {"$ne": current}})
        return {"message": "All other sessions revoked"}


    @api_router.post("/auth/reset-password-legacy")
    async def reset_password_legacy(data: ResetPasswordReq):
        """Legacy — use /auth/reset-password instead (now with email confirmation)"""
        return {"message": "Please use the updated reset-password endpoint."}

    # Microsoft and Meta OAuth — handled by routes_integrations.py
