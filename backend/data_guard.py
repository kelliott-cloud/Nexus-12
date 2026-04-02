"""Data Guard & Tenant Isolation — Protects intellectual property and enforces data boundaries"""
import re
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class DataGuard:
    """Abstraction layer that sanitizes data before it reaches AI providers.
    Strips identifiable info, adds no-train headers, logs transmissions."""

    # Patterns to redact from AI-bound content
    REDACT_PATTERNS = [
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
        (re.compile(r'\b(?:api[_-]?key|secret|password|token|bearer)\s*[=:]\s*["\']?[\w\-\.]{8,}["\']?', re.IGNORECASE), '[CREDENTIAL_REDACTED]'),
        (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), '[PHONE_REDACTED]'),
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
        (re.compile(r'\b(?:sk-|pk_|rk_|whsec_|sk_live_|sk_test_)[\w\-]{10,}\b'), '[API_KEY_REDACTED]'),
    ]

    @staticmethod
    def sanitize_for_ai(text: str, workspace_id: Optional[str] = None) -> str:
        """Remove sensitive data patterns before sending to AI providers"""
        if not text or not isinstance(text, str):
            return text or ""

        sanitized = text
        for pattern, replacement in DataGuard.REDACT_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        return sanitized

    @staticmethod
    def get_no_train_headers(provider: str, workspace_id: Optional[str] = None) -> Dict[str, str]:
        """Get provider-specific headers to prevent training on user data"""
        headers = {}
        if provider == "anthropic":
            pass  # Anthropic doesn't train on API data by default
        elif provider in ("openai", "chatgpt"):
            headers["X-No-Train"] = "true"
            # OpenAI: API data not used for training by default since March 2023
        elif provider == "google" or provider == "gemini":
            # Google: API data not used for training with paid API
            pass
        # All providers: add custom header for audit
        headers["X-Nexus-DataGuard"] = "active"
        headers["X-Nexus-Workspace"] = hashlib.sha256((workspace_id or "").encode()).hexdigest()[:12]
        return headers

    @staticmethod
    async def log_transmission(db, workspace_id, agent_key, provider, char_count, channel_id=None):
        """Audit log every data transmission to external AI providers"""
        try:
            await db.data_transmissions.insert_one({
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "agent": agent_key,
                "provider": provider,
                "chars_sent": char_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_guard": "active",
            })
        except Exception as _e:
            import logging; logging.getLogger("data_guard").warning(f"Suppressed: {_e}")  # Don't let audit logging break the flow


class TenantIsolation:
    """Enforces strict workspace/org data boundaries.
    Prevents cross-tenant data access at the query level."""

    @staticmethod
    async def verify_workspace_access(db, user_id, workspace_id):
        """Verify a user has access to a workspace. Returns True/False."""
        if not workspace_id or not user_id:
            return False

        # Check ownership
        ws = await db.workspaces.find_one(
            {"workspace_id": workspace_id},
            {"_id": 0, "owner_id": 1, "members": 1, "org_id": 1, "disabled": 1}
        )
        if not ws:
            return False
        if ws.get("disabled"):
            return False

        # Owner always has access
        if ws.get("owner_id") == user_id:
            return True

        # Direct member
        if user_id in (ws.get("members") or []):
            return True

        # Workspace member via workspace_members collection
        member = await db.workspace_members.find_one(
            {"workspace_id": workspace_id, "user_id": user_id}
        )
        if member:
            return True

        # Org membership grants access to org workspaces
        org_id = ws.get("org_id")
        if org_id:
            org_member = await db.org_memberships.find_one(
                {"org_id": org_id, "user_id": user_id}
            )
            if org_member:
                return True

        # Super admin has access to everything
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "platform_role": 1})
        if user:
            import os
            super_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
            if user.get("email") == super_email or user.get("platform_role") in ("super_admin", "platform_support"):
                return True

        return False

    @staticmethod
    async def verify_channel_access(db, user_id, channel_id):
        """Verify a user has access to a channel via its workspace."""
        channel = await db.channels.find_one(
            {"channel_id": channel_id},
            {"_id": 0, "workspace_id": 1}
        )
        if not channel:
            return False
        return await TenantIsolation.verify_workspace_access(db, user_id, channel.get("workspace_id", ""))

    @staticmethod
    def enforce_workspace_filter(query, workspace_id):
        """Ensure every DB query includes workspace_id filter.
        Call this before any find/aggregate to prevent cross-tenant leaks."""
        if not workspace_id:
            raise ValueError("workspace_id is required for tenant isolation")
        if isinstance(query, dict):
            query["workspace_id"] = workspace_id
        return query
