"""Email Notification Service — Resend-based transactional email for password resets, invitations, system notifications"""
from nexus_utils import now_iso, validate_password, normalize_email
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
PLATFORM_NAME = "Nexus"



# ============ Email Templates ============

def password_reset_email(user_name, reset_link):
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; background: #10B981; color: white; font-weight: bold; font-size: 18px; padding: 10px 16px; border-radius: 8px;">N</div>
            <h2 style="color: #fafafa; margin: 12px 0 0; font-size: 20px;">{PLATFORM_NAME}</h2>
        </div>
        <div style="background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 32px;">
            <h3 style="color: #fafafa; margin: 0 0 8px; font-size: 18px;">Reset Your Password</h3>
            <p style="color: #a1a1aa; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
                Hi {user_name},<br><br>
                We received a request to reset your password. Click the button below to create a new password.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{reset_link}" style="display: inline-block; background: #10B981; color: white; text-decoration: none; padding: 12px 32px; border-radius: 8px; font-weight: 600; font-size: 14px;">Reset Password</a>
            </div>
            <p style="color: #71717a; font-size: 12px; margin: 24px 0 0;">
                This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
            </p>
        </div>
        <p style="color: #52525b; font-size: 11px; text-align: center; margin-top: 24px;">
            &copy; {datetime.now().year} {PLATFORM_NAME}. All rights reserved.
        </p>
    </div>
    """


def invite_email(inviter_name, org_name, invite_link, role):
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; background: #10B981; color: white; font-weight: bold; font-size: 18px; padding: 10px 16px; border-radius: 8px;">N</div>
            <h2 style="color: #fafafa; margin: 12px 0 0; font-size: 20px;">{PLATFORM_NAME}</h2>
        </div>
        <div style="background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 32px;">
            <h3 style="color: #fafafa; margin: 0 0 8px; font-size: 18px;">You've Been Invited!</h3>
            <p style="color: #a1a1aa; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
                <strong style="color: #fafafa;">{inviter_name}</strong> has invited you to join
                <strong style="color: #10B981;">{org_name}</strong> on {PLATFORM_NAME} as a <strong style="color: #fafafa;">{role}</strong>.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{invite_link}" style="display: inline-block; background: #10B981; color: white; text-decoration: none; padding: 12px 32px; border-radius: 8px; font-weight: 600; font-size: 14px;">Accept Invitation</a>
            </div>
            <p style="color: #71717a; font-size: 12px; margin: 24px 0 0;">
                This invitation expires in 7 days.
            </p>
        </div>
        <p style="color: #52525b; font-size: 11px; text-align: center; margin-top: 24px;">
            &copy; {datetime.now().year} {PLATFORM_NAME}. All rights reserved.
        </p>
    </div>
    """


def system_notification_email(user_name, subject, message, action_label=None, action_link=None):
    action_html = ""
    if action_label and action_link:
        action_html = f"""
        <div style="text-align: center; margin: 24px 0;">
            <a href="{action_link}" style="display: inline-block; background: #10B981; color: white; text-decoration: none; padding: 10px 24px; border-radius: 8px; font-weight: 600; font-size: 14px;">{action_label}</a>
        </div>
        """
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; background: #10B981; color: white; font-weight: bold; font-size: 18px; padding: 10px 16px; border-radius: 8px;">N</div>
            <h2 style="color: #fafafa; margin: 12px 0 0; font-size: 20px;">{PLATFORM_NAME}</h2>
        </div>
        <div style="background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 32px;">
            <h3 style="color: #fafafa; margin: 0 0 8px; font-size: 18px;">{subject}</h3>
            <p style="color: #a1a1aa; font-size: 14px; line-height: 1.6; margin: 0 0 16px;">
                Hi {user_name},
            </p>
            <p style="color: #a1a1aa; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
                {message}
            </p>
            {action_html}
        </div>
        <p style="color: #52525b; font-size: 11px; text-align: center; margin-top: 24px;">
            &copy; {datetime.now().year} {PLATFORM_NAME}. All rights reserved.
        </p>
    </div>
    """


# ============ Core Send Function ============

# Module-level db reference (set during route registration)
_email_db = None

async def send_email(to_email, subject, html_content, db=None, user_id=None, org_id=None, workspace_id=None, action="email_send"):
    """Send an email via Resend. Returns success boolean."""
    _db = db or _email_db
    from key_resolver import get_integration_key
    provider = "resend"
    api_key = await get_integration_key(_db, "RESEND_API_KEY") if _db else os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        provider = "sendgrid"
        api_key = await get_integration_key(_db, "SENDGRID_API_KEY") if _db else os.environ.get("SENDGRID_API_KEY", "")
    if not api_key:
        logger.warning("No email provider key configured — email not sent")
        return False

    budget_ctx = {"cost": 0, "budget": {}}
    if _db:
        try:
            from managed_keys import check_usage_budget, estimate_integration_cost_usd, emit_budget_alert
            budget_ctx["cost"] = estimate_integration_cost_usd(provider, 1)
            budget_ctx["budget"] = await check_usage_budget(provider, budget_ctx["cost"], workspace_id=workspace_id, org_id=org_id, user_id=user_id)
            if budget_ctx["budget"].get("blocked"):
                scope_name = (budget_ctx["budget"].get("scope_type") or "platform").capitalize()
                message = f"{scope_name} Nexus AI budget reached for {provider} during {action}."
                await emit_budget_alert(provider, budget_ctx["budget"].get("scope_type") or "platform", budget_ctx["budget"].get("scope_id") or "platform", "blocked", budget_ctx["budget"].get("projected_spend_usd", budget_ctx["cost"]), budget_ctx["budget"].get("hard_cap_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=message)
                logger.warning(message)
                return False
        except Exception as exc:
            logger.debug(f"Email budget guard skipped: {exc}")

    try:
        if provider == "resend":
            import resend
            resend.api_key = api_key
            params = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            result = await asyncio.to_thread(resend.Emails.send, params)
        else:
            import sendgrid
            from sendgrid.helpers.mail import Mail
            message = Mail(from_email=SENDER_EMAIL, to_emails=to_email, subject=subject, html_content=html_content)
            sg = sendgrid.SendGridAPIClient(api_key)
            result = await asyncio.to_thread(sg.send, message)
        result_id = result.get('id', 'ok') if isinstance(result, dict) else getattr(result, 'status_code', 'ok')
        logger.info(f"Email sent to {to_email}: {result_id}")
        if _db:
            try:
                from managed_keys import record_usage_event, emit_budget_alert
                await record_usage_event(provider, budget_ctx.get("cost", 0), user_id=user_id, workspace_id=workspace_id, org_id=org_id, usage_type="integration", key_source="managed_or_override", call_count=1, metadata={"action": action, "to": to_email})
                if budget_ctx.get("budget", {}).get("warn"):
                    scope_name = (budget_ctx["budget"].get("scope_type") or "platform").capitalize()
                    await emit_budget_alert(provider, budget_ctx["budget"].get("scope_type") or "platform", budget_ctx["budget"].get("scope_id") or "platform", "warning", budget_ctx["budget"].get("projected_spend_usd", budget_ctx.get("cost", 0)), budget_ctx["budget"].get("warn_threshold_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget warning for {provider} during {action}.")
            except Exception as exc:
                logger.debug(f"Email budget log skipped: {exc}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to_email}: {e}")
        return False


# ============ Route Registration ============

def register_email_routes(api_router, db, get_current_user):
    global _email_db
    _email_db = db

    # ============ Password Reset ============

    @api_router.post("/auth/forgot-password")
    async def forgot_password(request: Request):
        """Send password reset email"""
        body = await request.json()
        email = body.get("email", "").strip().lower()
        if not email:
            raise HTTPException(400, "Email required")

        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            # Don't reveal if email exists
            return {"message": "If an account exists, a reset link has been sent."}

        # Generate reset token
        import secrets
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        await db.password_resets.update_one(
            {"email": email},
            {"$set": {"email": email, "token": token, "expires_at": expires, "used": False, "created_at": now_iso()}},
            upsert=True,
        )

        app_url = os.environ.get("APP_URL", "")
        reset_link = f"{app_url}/reset-password?token={token}"

        html = password_reset_email(user.get("name", "there"), reset_link)
        sent = await send_email(email, f"{PLATFORM_NAME} — Reset Your Password", html, db=db, user_id=user["user_id"], action="password_reset_email")

        if not sent:
            logger.warning(f"Password reset email not sent to {email} (Resend not configured)")

        # Log
        await db.email_log.insert_one({
            "log_id": f"el_{uuid.uuid4().hex[:8]}", "type": "password_reset",
            "to": email, "sent": sent, "timestamp": now_iso(),
        })

        return {"message": "If an account exists, a reset link has been sent."}

    @api_router.post("/auth/reset-password")
    async def reset_password(request: Request):
        """Reset password using token from email"""
        body = await request.json()
        token = body.get("token", "")
        new_password = body.get("password", "")

        if not token or not new_password:
            raise HTTPException(400, "Token and new password required")
        pw_error = validate_password(new_password)
        if pw_error:
            raise HTTPException(400, pw_error)

        reset = await db.password_resets.find_one({"token": token, "used": False})
        if not reset:
            raise HTTPException(400, "Invalid or expired reset link")

        if reset.get("expires_at", "") < now_iso():
            raise HTTPException(400, "Reset link has expired. Request a new one.")

        # Fetch user BEFORE using user_id
        user = await db.users.find_one({"email": reset["email"]}, {"_id": 0, "user_id": 1, "name": 1})
        if not user:
            raise HTTPException(400, "Account not found")

        # Update password
        import bcrypt
        hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        await db.users.update_one({"email": reset["email"]}, {"$set": {"password_hash": hashed}})
        await db.user_sessions.delete_many({"user_id": user["user_id"]})
        await db.password_resets.update_one({"token": token}, {"$set": {"used": True}})
        html = system_notification_email(
            user.get("name", "there"),
            "Password Changed",
            "Your password has been successfully reset. If you didn't make this change, please contact support immediately."
        )
        await send_email(reset["email"], f"{PLATFORM_NAME} — Password Changed", html, db=db, user_id=user["user_id"], action="password_changed_email")

        return {"message": "Password reset successfully. You can now log in."}

    # ============ User Invitations ============

    @api_router.post("/email/invite")
    async def send_invite_email(request: Request):
        """Send an invitation email to join an org"""
        user = await get_current_user(request)
        body = await request.json()
        to_email = body.get("email", "").strip().lower()
        org_id = body.get("org_id", "")
        role = body.get("role", "member")

        if not to_email:
            raise HTTPException(400, "Email required")

        org = await db.organizations.find_one({"org_id": org_id}, {"_id": 0, "name": 1, "slug": 1})
        if not org:
            raise HTTPException(404, "Organization not found")

        # Generate invite token
        import secrets
        token = secrets.token_urlsafe(24)
        await db.invitations.update_one(
            {"email": to_email, "org_id": org_id},
            {"$set": {
                "email": to_email, "org_id": org_id, "role": role,
                "token": token, "status": "pending",
                "invited_by": user["user_id"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "created_at": now_iso(),
            }},
            upsert=True,
        )

        app_url = os.environ.get("APP_URL", "")
        invite_link = f"{app_url}/org/{org['slug']}?invite={token}"

        html = invite_email(user.get("name", "Someone"), org["name"], invite_link, role)
        sent = await send_email(to_email, f"You're invited to {org['name']} on {PLATFORM_NAME}", html, db=db, user_id=user["user_id"], org_id=org_id, action="org_invite_email")

        await db.email_log.insert_one({
            "log_id": f"el_{uuid.uuid4().hex[:8]}", "type": "invitation",
            "to": to_email, "org_id": org_id, "sent": sent, "timestamp": now_iso(),
        })

        return {"message": f"Invitation sent to {to_email}", "sent": sent}

    # ============ System Notifications ============

    @api_router.post("/email/notify")
    async def send_system_notification(request: Request):
        """Send a system notification email"""
        user = await get_current_user(request)
        body = await request.json()
        to_email = body.get("email", "")
        subject = body.get("subject", "")
        message = body.get("message", "")
        action_label = body.get("action_label")
        action_link = body.get("action_link")

        if not to_email or not subject or not message:
            raise HTTPException(400, "email, subject, and message required")

        # Look up recipient name
        recipient = await db.users.find_one({"email": to_email}, {"_id": 0, "name": 1})
        recipient_name = recipient.get("name", "there") if recipient else "there"

        html = system_notification_email(recipient_name, subject, message, action_label, action_link)
        sent = await send_email(to_email, f"{PLATFORM_NAME} — {subject}", html, db=db, user_id=user["user_id"], action="system_notification_email")

        await db.email_log.insert_one({
            "log_id": f"el_{uuid.uuid4().hex[:8]}", "type": "system_notification",
            "to": to_email, "subject": subject, "sent": sent,
            "sent_by": user["user_id"], "timestamp": now_iso(),
        })

        return {"message": f"Notification sent to {to_email}", "sent": sent}

    @api_router.post("/email/notify-bulk")
    async def send_bulk_notification(request: Request):
        """Send notification to multiple users"""
        await get_current_user(request)
        body = await request.json()
        emails = body.get("emails") or []
        subject = body.get("subject", "")
        message = body.get("message", "")

        if not emails or not subject or not message:
            raise HTTPException(400, "emails, subject, and message required")

        results = {"sent": 0, "failed": 0}
        for email in emails[:50]:  # Max 50 per batch
            html = system_notification_email("there", subject, message)
            sent = await send_email(email, f"{PLATFORM_NAME} — {subject}", html, db=db, action="bulk_notification_email")
            if sent:
                results["sent"] += 1
            else:
                results["failed"] += 1

        return results

    # ============ Email Service Status ============

    @api_router.get("/email/status")
    async def get_email_status(request: Request):
        await get_current_user(request)
        from key_resolver import get_integration_key
        configured = bool(await get_integration_key(db, "RESEND_API_KEY"))
        recent = await db.email_log.find({}, {"_id": 0}).sort("timestamp", -1).limit(10).to_list(10)
        total_sent = await db.email_log.count_documents({"sent": True})
        total_failed = await db.email_log.count_documents({"sent": False})
        return {
            "configured": configured,
            "provider": "resend",
            "sender": SENDER_EMAIL,
            "total_sent": total_sent,
            "total_failed": total_failed,
            "recent": recent,
        }

    @api_router.post("/email/test")
    async def test_email(request: Request):
        """Send a test email to verify configuration"""
        user = await get_current_user(request)
        body = await request.json()
        to_email = body.get("email", user.get("email", ""))

        html = system_notification_email(
            user.get("name", "Admin"),
            "Test Email from Nexus",
            "This is a test email to verify your email notification service is configured correctly. If you're reading this, it's working!",
            "Open Nexus", os.environ.get("APP_URL", "")
        )
        sent = await send_email(to_email, f"{PLATFORM_NAME} — Test Email", html, db=db, user_id=user["user_id"], action="test_email")
        return {"sent": sent, "to": to_email, "provider": "resend"}

    # ============ Email Log ============

    @api_router.get("/email/log")
    async def get_email_log(request: Request, email_type: Optional[str] = None, limit: int = 50):
        await get_current_user(request)
        query = {}
        if email_type:
            query["type"] = email_type
        logs = await db.email_log.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"logs": logs}
