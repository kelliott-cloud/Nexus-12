"""Legal compliance routes — ToS, Privacy, AUP, GDPR, account deletion, data export"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

TOS_VERSION = "1.0"
TOS_EFFECTIVE_DATE = "2026-03-06"


def register_legal_routes(api_router, db, get_current_user):

    # ===== Legal Document Metadata =====
    @api_router.get("/legal/tos-version")
    async def get_tos_version(request: Request):
        return {"version": TOS_VERSION, "effective_date": TOS_EFFECTIVE_DATE}

    @api_router.post("/legal/accept-tos")
    async def accept_tos(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        now = datetime.now(timezone.utc).isoformat()
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "tos_version": TOS_VERSION,
                "tos_accepted_at": now,
                "beta_accepted_at": now if body.get("beta_accepted") else None,
            }}
        )
        return {"accepted": True, "version": TOS_VERSION, "timestamp": now}

    @api_router.get("/legal/tos-status")
    async def get_tos_status(request: Request):
        user = await get_current_user(request)
        return {
            "current_version": TOS_VERSION,
            "accepted_version": user.get("tos_version"),
            "accepted_at": user.get("tos_accepted_at"),
            "needs_acceptance": user.get("tos_version") != TOS_VERSION,
        }

    # ===== Cookie Consent =====
    @api_router.post("/legal/cookie-consent")
    async def save_cookie_consent(request: Request):
        body = await request.json()
        consent = body.get("consent", "essential")  # essential, all, custom
        now = datetime.now(timezone.utc).isoformat()
        # Try to get user, but cookie consent can happen before login
        try:
            user = await get_current_user(request)
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"cookie_consent": consent, "cookie_consent_at": now}}
            )
        except Exception as _e:
            logger.warning(f"Caught exception: {_e}")
        return {"consent": consent, "timestamp": now}

    # ===== GDPR: Data Export =====
    @api_router.post("/user/export-data")
    async def export_user_data(request: Request):
        """Export all user data as JSON (GDPR Article 20)"""
        user = await get_current_user(request)
        uid = user["user_id"]
        import json
        import io
        import zipfile

        data = {}
        # User profile
        profile = await db.users.find_one({"user_id": uid}, {"_id": 0, "password_hash": 0})
        data["profile"] = profile

        # Workspaces owned
        data["workspaces"] = await db.workspaces.find({"owner_id": uid}, {"_id": 0}).to_list(100)
        ws_ids = [w["workspace_id"] for w in data["workspaces"]]

        # Messages sent
        data["messages"] = await db.messages.find({"sender_id": uid}, {"_id": 0}).to_list(500)

        # Tasks created
        data["tasks"] = await db.tasks.find({"created_by": uid}, {"_id": 0}).limit(500).to_list(500)
        data["project_tasks"] = await db.project_tasks.find({"created_by": uid}, {"_id": 0}).limit(500).to_list(500)

        # Projects
        data["projects"] = await db.projects.find({"created_by": uid}, {"_id": 0}).to_list(100)

        # Wiki pages
        data["wiki_pages"] = await db.wiki_pages.find({"created_by": uid}, {"_id": 0}).to_list(500)

        # Repo files
        if ws_ids:
            data["repo_files"] = await db.repo_files.find(
                {"workspace_id": {"$in": ws_ids}}, {"_id": 0}
            ).to_list(500)

        # AI Keys (masked)
        keys = await db.ai_keys.find({"user_id": uid}, {"_id": 0}).to_list(20)
        for k in keys:
            for field in k:
                if field not in ("user_id", "workspace_id") and isinstance(k[field], str) and len(k[field]) > 8:
                    k[field] = k[field][:4] + "****"
        data["ai_keys"] = keys

        # Audit logs
        data["audit_logs"] = await db.audit_logs.find({"user_id": uid}, {"_id": 0}).limit(500).to_list(500)

        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("nexus_data_export.json", json.dumps(data, indent=2, default=str))
        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="nexus_data_export.zip"'}
        )

    # ===== GDPR: Account Deletion =====
    @api_router.post("/user/delete-account")
    async def delete_user_account(request: Request):
        """Delete user account and all associated data (GDPR Article 17)"""
        user = await get_current_user(request)
        body = await request.json()
        confirm = body.get("confirm", False)
        if not confirm:
            raise HTTPException(400, "Must confirm deletion")

        uid = user["user_id"]
        now = datetime.now(timezone.utc).isoformat()

        # Schedule deletion (30-day grace period)
        await db.users.update_one(
            {"user_id": uid},
            {"$set": {
                "deletion_requested": True,
                "deletion_requested_at": now,
                "deletion_scheduled_for": "30_days",
            }}
        )

        # Log the deletion request
        await db.audit_logs.insert_one({
            "audit_id": f"audit_{uuid.uuid4().hex[:12]}",
            "user_id": uid,
            "action": "account_deletion_requested",
            "details": {"scheduled_for": "30 days"},
            "timestamp": now,
        })

        # Immediate soft-delete: anonymize user data
        await db.users.update_one(
            {"user_id": uid},
            {"$set": {
                "name": "Deleted User",
                "email": f"deleted_{uid}@nexus.local",
                "status": "deleted",
            }}
        )

        return {
            "status": "deletion_scheduled",
            "message": "Your account has been scheduled for deletion. All data will be permanently removed in 30 days. You can contact support to cancel within this period.",
        }

    # ===== Content Flagging (Workflow Templates, etc.) =====
    @api_router.post("/content/flag")
    async def flag_content(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        content_type = body.get("type", "")  # template, message, media
        content_id = body.get("content_id", "")
        reason = body.get("reason", "")
        if not content_type or not content_id or not reason:
            raise HTTPException(400, "type, content_id, and reason required")

        flag_id = f"flag_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        await db.content_flags.insert_one({
            "flag_id": flag_id,
            "content_type": content_type,
            "content_id": content_id,
            "reason": reason,
            "details": body.get("details", ""),
            "reported_by": user["user_id"],
            "status": "pending",
            "created_at": now,
        })
        return {"flag_id": flag_id, "status": "reported"}

    @api_router.get("/admin/content-flags")
    async def get_content_flags(request: Request):
        user = await get_current_user(request)
        flags = await db.content_flags.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).limit(100).to_list(100)
        return {"flags": flags}

    @api_router.put("/admin/content-flags/{flag_id}")
    async def resolve_flag(flag_id: str, request: Request):
        user = await get_current_user(request)
        body = await request.json()
        action = body.get("action", "dismiss")  # dismiss, remove, suspend
        await db.content_flags.update_one(
            {"flag_id": flag_id},
            {"$set": {
                "status": "resolved",
                "resolution": action,
                "resolved_by": user["user_id"],
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        return {"resolved": True, "action": action}


    # ===== Subscription Cancellation =====
    @api_router.post("/billing/cancel")
    async def cancel_subscription(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        reason = body.get("reason", "")
        now = datetime.now(timezone.utc).isoformat()
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "plan": "free",
                "cancellation_requested_at": now,
                "cancellation_reason": reason,
                "previous_plan": user.get("plan", "free"),
            }}
        )
        await db.audit_logs.insert_one({
            "audit_id": f"audit_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "action": "subscription_cancelled",
            "details": {"reason": reason, "previous_plan": user.get("plan", "free")},
            "timestamp": now,
        })
        return {
            "status": "cancelled",
            "message": "Your subscription has been cancelled. You've been moved to the Free plan. Your data will be retained for 90 days.",
        }

    # ===== Voice Consent (ElevenLabs) =====
    @api_router.post("/legal/voice-consent")
    async def record_voice_consent(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        now = datetime.now(timezone.utc).isoformat()
        await db.audit_logs.insert_one({
            "audit_id": f"audit_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "action": "voice_consent_given",
            "details": {
                "consent_given": body.get("consent", False),
                "voice_owner_name": body.get("voice_owner_name", ""),
            },
            "timestamp": now,
        })
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"voice_consent": body.get("consent", False), "voice_consent_at": now}}
        )
        return {"consent_recorded": True, "timestamp": now}

    # ===== DPA Acceptance (Enterprise Orgs) =====
    @api_router.post("/orgs/{org_id}/accept-dpa")
    async def accept_dpa(org_id: str, request: Request):
        user = await get_current_user(request)
        now = datetime.now(timezone.utc).isoformat()
        await db.orgs.update_one(
            {"org_id": org_id},
            {"$set": {"dpa_accepted": True, "dpa_accepted_by": user["user_id"], "dpa_accepted_at": now}}
        )
        return {"dpa_accepted": True, "timestamp": now}
