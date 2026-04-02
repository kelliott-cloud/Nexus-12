"""External Integration Stubs — Email, Microsoft/Meta OAuth, PayPal
These are ready to activate once API keys/credentials are provided.
Fixed: Now uses key_resolver for platform_settings DB lookup."""
import os
import logging
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def register_integration_routes(api_router, db, get_current_user):

    async def _resolve(key_name):
        from key_resolver import get_integration_key
        return await get_integration_key(db, key_name)

    async def _budget_guard(provider: str, user_id: str = None, org_id: str = None, workspace_id: str = None, action: str = "integration"):
        try:
            from managed_keys import PLATFORM_KEY_PROVIDERS, check_usage_budget, estimate_integration_cost_usd, emit_budget_alert
            if provider not in PLATFORM_KEY_PROVIDERS:
                return {"cost": 0, "budget": {}}
            cost = estimate_integration_cost_usd(provider, 1)
            budget = await check_usage_budget(provider, cost, workspace_id=workspace_id, org_id=org_id, user_id=user_id)
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", cost), budget.get("hard_cap_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget reached for {provider} during {action}.")
                raise HTTPException(429, f"{scope_name} Nexus AI budget reached for {provider}")
            return {"cost": cost, "budget": budget}
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug(f"Integration budget guard skipped for {provider}: {exc}")
            return {"cost": 0, "budget": {}}

    async def _budget_log(provider: str, budget_ctx: dict, user_id: str = None, org_id: str = None, workspace_id: str = None, action: str = "integration"):
        try:
            from managed_keys import PLATFORM_KEY_PROVIDERS, record_usage_event, emit_budget_alert
            if provider not in PLATFORM_KEY_PROVIDERS:
                return
            cost = budget_ctx.get("cost", 0)
            await record_usage_event(provider, cost, user_id=user_id, workspace_id=workspace_id, org_id=org_id, usage_type="integration", key_source="managed_or_override", call_count=1, metadata={"action": action})
            budget = budget_ctx.get("budget") or {}
            if budget.get("warn"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", cost), budget.get("warn_threshold_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget warning for {provider} during {action}.")
        except Exception as exc:
            logger.debug(f"Integration budget log skipped for {provider}: {exc}")

    # ============ Email Service (SendGrid/Resend) ============

    @api_router.get("/integrations/email/status")
    async def email_status(request: Request):
        await get_current_user(request)
        sg = await _resolve("SENDGRID_API_KEY")
        re = await _resolve("RESEND_API_KEY")
        key = sg or re
        return {
            "configured": bool(key),
            "provider": "sendgrid" if sg else "resend" if re else None,
            "message": "Email service active" if key else "Add SENDGRID_API_KEY or RESEND_API_KEY in Integration Settings.",
        }

    # ============ Microsoft OAuth ============

    @api_router.get("/integrations/microsoft/status")
    async def microsoft_status(request: Request):
        await get_current_user(request)
        client_id = await _resolve("MICROSOFT_CLIENT_ID")
        return {
            "configured": bool(client_id),
            "message": "Microsoft OAuth active" if client_id else "Add MICROSOFT_CLIENT_ID in Integration Settings.",
        }

    @api_router.post("/auth/microsoft")
    async def microsoft_auth(request: Request):
        client_id = await _resolve("MICROSOFT_CLIENT_ID")
        if not client_id:
            raise HTTPException(501, "Microsoft OAuth not configured. Add MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET in Integration Settings.")
        base = os.environ.get('APP_URL') or str(request.base_url).rstrip('/')
        redirect_uri = f"{base}/api/auth/microsoft/callback"
        import urllib.parse
        auth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id={client_id}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}&scope=openid+profile+email"
        return {"auth_url": auth_url}

    # ============ Meta OAuth ============

    @api_router.get("/integrations/meta/status")
    async def meta_status(request: Request):
        await get_current_user(request)
        app_id = await _resolve("META_APP_ID")
        return {
            "configured": bool(app_id),
            "message": "Meta OAuth active" if app_id else "Add META_APP_ID in Integration Settings.",
        }

    @api_router.post("/auth/meta")
    async def meta_auth(request: Request):
        app_id = await _resolve("META_APP_ID")
        if not app_id:
            raise HTTPException(501, "Meta OAuth not configured. Add META_APP_ID and META_APP_SECRET in Integration Settings.")
        base = os.environ.get('APP_URL') or str(request.base_url).rstrip('/')
        redirect_uri = f"{base}/api/auth/meta/callback"
        import urllib.parse
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={app_id}&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}&scope=email,public_profile"
        return {"auth_url": auth_url}

    # ============ Microsoft OAuth Callback ============

    @api_router.get("/auth/microsoft/callback")
    async def microsoft_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if error:
            raise HTTPException(400, f"Microsoft auth error: {error}")
        if not code:
            raise HTTPException(400, "Missing authorization code")

        import httpx
        import uuid
        import secrets
        from datetime import datetime, timezone, timedelta

        client_id = await _resolve("MICROSOFT_CLIENT_ID")
        client_secret = await _resolve("MICROSOFT_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(500, "Microsoft OAuth not configured")

        base = os.environ.get('APP_URL') or str(request.base_url).rstrip('/')
        redirect_uri = f"{base}/api/auth/microsoft/callback"
        budget_ctx = await _budget_guard("microsoft", action="microsoft_oauth_callback")

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://login.microsoftonline.com/common/oauth2/v2.0/token", data={
                "code": code, "client_id": client_id, "client_secret": client_secret,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code",
                "scope": "openid profile email",
            })
        if token_resp.status_code != 200:
            logger.error(f"Microsoft token exchange failed: {token_resp.text[:200]}")
            raise HTTPException(401, "Microsoft authentication failed")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(401, "No access token from Microsoft")

        # Get user info from Microsoft Graph
        async with httpx.AsyncClient() as client:
            user_resp = await client.get("https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"})
        if user_resp.status_code != 200:
            raise HTTPException(401, "Failed to get user info from Microsoft")

        ms_user = user_resp.json()
        email = ms_user.get("mail") or ms_user.get("userPrincipalName", "")
        name = ms_user.get("displayName", email.split("@")[0])

        if not email:
            raise HTTPException(401, "No email in Microsoft profile")

        # Create or update user
        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            user_id = existing["user_id"]
            await db.users.update_one({"email": email}, {"$set": {"name": name}})
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id, "email": email, "name": name, "picture": "",
                "auth_type": "microsoft", "email_verified": True, "platform_role": "user",
                "language": "en", "plan": "free",
                "usage": {"ai_collaboration": 0, "reset_date": datetime.now(timezone.utc).isoformat()},
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "session_token": session_token, "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        })

        from fastapi.responses import RedirectResponse
        redirect = RedirectResponse(url=f"{base}/dashboard", status_code=302)
        redirect.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)
        await _budget_log("microsoft", budget_ctx, user_id=user_id, action="microsoft_oauth_callback")
        return redirect

    # ============ Meta OAuth Callback ============

    @api_router.get("/auth/meta/callback")
    async def meta_callback(request: Request, code: str = "", error: str = ""):
        if error:
            raise HTTPException(400, f"Meta auth error: {error}")
        if not code:
            raise HTTPException(400, "Missing authorization code")

        import httpx
        import uuid
        import secrets
        from datetime import datetime, timezone, timedelta

        app_id = await _resolve("META_APP_ID")
        app_secret = await _resolve("META_APP_SECRET")
        if not app_id or not app_secret:
            raise HTTPException(500, "Meta OAuth not configured")

        base = os.environ.get('APP_URL') or str(request.base_url).rstrip('/')
        redirect_uri = f"{base}/api/auth/meta/callback"
        budget_ctx = await _budget_guard("meta", action="meta_oauth_callback")

        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_resp = await client.get("https://graph.facebook.com/v18.0/oauth/access_token", params={
                "code": code, "client_id": app_id, "client_secret": app_secret,
                "redirect_uri": redirect_uri,
            })
        if token_resp.status_code != 200:
            logger.error(f"Meta token exchange failed: {token_resp.text[:200]}")
            raise HTTPException(401, "Meta authentication failed")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(401, "No access token from Meta")

        # Get user info
        async with httpx.AsyncClient() as client:
            user_resp = await client.get("https://graph.facebook.com/v18.0/me",
                params={"fields": "id,name,email,picture", "access_token": access_token})
        if user_resp.status_code != 200:
            raise HTTPException(401, "Failed to get user info from Meta")

        fb_user = user_resp.json()
        email = fb_user.get("email", "")
        name = fb_user.get("name", "Facebook User")
        picture = ((fb_user.get("picture") or {}).get("data") or {}).get("url", "")

        if not email:
            raise HTTPException(401, "No email in Meta profile. Ensure email permission is granted.")

        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            user_id = existing["user_id"]
            await db.users.update_one({"email": email}, {"$set": {"name": name, "picture": picture}})
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id, "email": email, "name": name, "picture": picture,
                "auth_type": "meta", "email_verified": True, "platform_role": "user",
                "language": "en", "plan": "free",
                "usage": {"ai_collaboration": 0, "reset_date": datetime.now(timezone.utc).isoformat()},
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "session_token": session_token, "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        })

        from fastapi.responses import RedirectResponse
        redirect = RedirectResponse(url=f"{base}/dashboard", status_code=302)
        redirect.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)
        await _budget_log("meta", budget_ctx, user_id=user_id, action="meta_oauth_callback")
        return redirect

    # ============ PayPal Payments ============

    @api_router.get("/integrations/paypal/status")
    async def paypal_status(request: Request):
        await get_current_user(request)
        client_id = await _resolve("PAYPAL_CLIENT_ID")
        return {
            "configured": bool(client_id),
            "message": "PayPal active" if client_id else "Add PAYPAL_CLIENT_ID in Integration Settings.",
        }

    @api_router.post("/billing/paypal/create-order")
    async def paypal_create_order(request: Request):
        await get_current_user(request)
        client_id = await _resolve("PAYPAL_CLIENT_ID")
        client_secret = await _resolve("PAYPAL_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(501, "PayPal not configured. Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in Integration Settings.")
        raise HTTPException(501, "PayPal payments not yet available. Use Stripe for payment processing.")

    # ============ Integration Status Overview ============

    @api_router.get("/integrations/status")
    async def all_integrations_status(request: Request):
        await get_current_user(request)
        sg = await _resolve("SENDGRID_API_KEY")
        re = await _resolve("RESEND_API_KEY")
        return {
            "email": {"configured": bool(sg or re), "provider": "sendgrid" if sg else "resend" if re else None},
            "microsoft_oauth": {"configured": bool(await _resolve("MICROSOFT_CLIENT_ID"))},
            "meta_oauth": {"configured": bool(await _resolve("META_APP_ID"))},
            "paypal": {"configured": bool(await _resolve("PAYPAL_CLIENT_ID"))},
            "stripe": {"configured": bool(await _resolve("STRIPE_API_KEY"))},
            "google_oauth": {"configured": True, "provider": "native"},
        }
