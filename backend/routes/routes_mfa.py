"""MFA/TOTP Routes — Multi-factor authentication with TOTP, backup codes, and admin enforcement."""
import secrets
import logging
import io
import base64
import pyotp
import qrcode
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import HTTPException, Request, Response
from typing import Optional

logger = logging.getLogger(__name__)


class MFASetupRequest(BaseModel):
    code: str


class MFAVerifyRequest(BaseModel):
    code: str
    email: Optional[str] = None
    challenge_token: Optional[str] = None


class MFADisableRequest(BaseModel):
    code: str
    password: str


def register_mfa_routes(api_router, db, get_current_user):

    @api_router.post("/auth/mfa/setup")
    async def mfa_setup_init(request: Request):
        """Generate TOTP secret and QR code for MFA setup."""
        user = await get_current_user(request)
        if user.get("mfa_enabled"):
            raise HTTPException(400, "MFA is already enabled on this account")

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user["email"],
            issuer_name="Nexus Cloud"
        )

        # Generate QR code as base64
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="white", back_color="#09090b")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()

        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        hashed_codes = [_hash_code(c, user["user_id"]) for c in backup_codes]

        # Store pending setup (not yet verified)
        await db.mfa_pending.delete_many({"user_id": user["user_id"]})
        await db.mfa_pending.insert_one({
            "user_id": user["user_id"],
            "secret": secret,
            "backup_codes": hashed_codes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_b64}",
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes,
        }

    @api_router.post("/auth/mfa/setup/confirm")
    async def mfa_setup_confirm(data: MFASetupRequest, request: Request):
        """Verify TOTP code to finalize MFA setup."""
        user = await get_current_user(request)
        pending = await db.mfa_pending.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if not pending:
            raise HTTPException(400, "No pending MFA setup found. Start setup first.")

        totp = pyotp.TOTP(pending["secret"])
        if not totp.verify(data.code, valid_window=1):
            raise HTTPException(400, "Invalid verification code. Please try again.")

        # Activate MFA on the user account
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "mfa_enabled": True,
                "mfa_secret": pending["secret"],
                "mfa_backup_codes": pending["backup_codes"],
                "mfa_enabled_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await db.mfa_pending.delete_many({"user_id": user["user_id"]})

        logger.info(f"MFA enabled for user {user['user_id']}")
        return {"status": "mfa_enabled", "message": "MFA has been enabled on your account."}

    @api_router.post("/auth/mfa/verify")
    async def mfa_verify(data: MFAVerifyRequest, response: Response):
        """Verify TOTP code during login (second factor)."""
        # Look up the pending MFA challenge
        challenge = None
        if data.challenge_token:
            challenge = await db.mfa_challenges.find_one(
                {"challenge_token": data.challenge_token}, {"_id": 0}
            )
        if not challenge and data.email:
            challenge = await db.mfa_challenges.find_one(
                {"email": data.email}, {"_id": 0}
            )
        if not challenge:
            raise HTTPException(400, "No pending MFA challenge. Please log in first.")
        if data.email and challenge.get("email") != data.email:
            raise HTTPException(400, "MFA challenge does not match this email")

        # Check challenge expiry (5 minutes)
        created = challenge.get("created_at", "")
        if created:
            challenge_delete_query = {"challenge_token": data.challenge_token} if data.challenge_token else {"email": data.email}
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - created_dt > timedelta(minutes=5):
                    await db.mfa_challenges.delete_one(challenge_delete_query)
                    raise HTTPException(400, "MFA challenge expired. Please log in again.")
            except (ValueError, TypeError):
                await db.mfa_challenges.delete_one(challenge_delete_query)
                raise HTTPException(400, "MFA challenge invalid or expired. Please log in again.")

        user = await db.users.find_one({"user_id": challenge["user_id"]}, {"_id": 0})
        if not user or not user.get("mfa_enabled"):
            raise HTTPException(400, "MFA is not enabled on this account")

        verified = False
        used_backup = False

        # Try TOTP code first
        totp = pyotp.TOTP(user["mfa_secret"])
        if totp.verify(data.code, valid_window=1):
            verified = True
        else:
            # Try backup codes
            code_hash = _hash_code(data.code.strip().upper(), user["user_id"])
            backup_codes = user.get("mfa_backup_codes") or []
            if code_hash in backup_codes:
                verified = True
                used_backup = True
                backup_codes.remove(code_hash)
                await db.users.update_one(
                    {"user_id": user["user_id"]},
                    {"$set": {"mfa_backup_codes": backup_codes}}
                )

        if not verified:
            raise HTTPException(401, "Invalid MFA code")

        # MFA passed — create session
        import secrets as _secrets
        session_token = _secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip_address": "",
            "user_agent": "",
            "mfa_verified": True,
        })

        response.set_cookie(
            key="session_token", value=session_token,
            httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
        )

        # Clean up challenge
        delete_query = {"user_id": user["user_id"]}
        if data.challenge_token:
            delete_query = {"challenge_token": data.challenge_token}
        await db.mfa_challenges.delete_many(delete_query)

        safe_user = {k: v for k, v in user.items() if k not in ("password_hash", "mfa_secret", "mfa_backup_codes")}
        result = {**safe_user, "mfa_verified": True, "session_token": session_token}
        if used_backup:
            remaining = len(backup_codes)
            result["backup_warning"] = f"Backup code used. {remaining} remaining."
        return result

    @api_router.post("/auth/mfa/disable")
    async def mfa_disable(data: MFADisableRequest, request: Request):
        """Disable MFA (requires current TOTP code + password)."""
        user = await db.users.find_one({"user_id": (await get_current_user(request))["user_id"]}, {"_id": 0})
        if not user.get("mfa_enabled"):
            raise HTTPException(400, "MFA is not enabled")

        # Verify password
        import bcrypt
        if not user.get("password_hash") or not bcrypt.checkpw(data.password.encode(), user["password_hash"].encode()):
            raise HTTPException(401, "Invalid password")

        # Verify TOTP
        totp = pyotp.TOTP(user["mfa_secret"])
        if not totp.verify(data.code, valid_window=1):
            raise HTTPException(401, "Invalid MFA code")

        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$unset": {"mfa_enabled": "", "mfa_secret": "", "mfa_backup_codes": "", "mfa_enabled_at": ""}}
        )
        logger.info(f"MFA disabled for user {user['user_id']}")
        return {"status": "mfa_disabled"}

    @api_router.get("/auth/mfa/status")
    async def mfa_status(request: Request):
        """Get MFA status for current user."""
        user = await get_current_user(request)
        return {
            "mfa_enabled": bool(user.get("mfa_enabled")),
            "enabled_at": user.get("mfa_enabled_at"),
            "backup_codes_remaining": len(user.get("mfa_backup_codes") or []) if user.get("mfa_enabled") else 0,
        }

    @api_router.post("/auth/mfa/regenerate-backup")
    async def regenerate_backup_codes(request: Request):
        """Generate new backup codes (invalidates old ones)."""
        user = await get_current_user(request)
        if not user.get("mfa_enabled"):
            raise HTTPException(400, "MFA is not enabled")

        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        hashed_codes = [_hash_code(c, user["user_id"]) for c in backup_codes]

        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"mfa_backup_codes": hashed_codes}}
        )
        return {"backup_codes": backup_codes}


def _hash_code(code: str, salt: str = "") -> str:
    """Hash a backup code with user-specific salt."""
    import hashlib
    return hashlib.sha256(f"{salt}:{code.strip().upper()}".encode()).hexdigest()
