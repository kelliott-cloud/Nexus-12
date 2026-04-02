"""Messaging & Meeting Platform Plugins — Slack, Discord, Teams, Mattermost, WhatsApp, Signal, Telegram, Zoom"""
import uuid
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from fastapi import HTTPException, Request
from nexus_utils import validate_external_url, now_iso

logger = logging.getLogger(__name__)


PLATFORM_CONFIGS = {
    "slack": {"name": "Slack", "auth_type": "oauth", "client_id_key": "SLACK_CLIENT_ID", "client_secret_key": "SLACK_CLIENT_SECRET", "auth_url": "https://slack.com/oauth/v2/authorize", "token_url": "https://slack.com/api/oauth.v2.access", "scopes": "chat:write,channels:read,channels:history,commands,incoming-webhook", "api_base": "https://slack.com/api"},
    "discord": {"name": "Discord", "auth_type": "bot_token", "token_key": "DISCORD_BOT_TOKEN", "api_base": "https://discord.com/api/v10"},
    "msteams": {"name": "Microsoft Teams", "auth_type": "oauth", "client_id_key": "MSTEAMS_CLIENT_ID", "client_secret_key": "MSTEAMS_CLIENT_SECRET", "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token", "scopes": "ChannelMessage.Send,Channel.ReadBasic.All,Chat.ReadWrite", "api_base": "https://graph.microsoft.com/v1.0"},
    "mattermost": {"name": "Mattermost", "auth_type": "webhook", "token_key": "MATTERMOST_BOT_TOKEN"},
    "whatsapp": {"name": "WhatsApp", "auth_type": "api_key", "token_key": "WHATSAPP_API_TOKEN", "api_base": "https://graph.facebook.com/v18.0"},
    "signal": {"name": "Signal", "auth_type": "api_key", "token_key": "SIGNAL_API_KEY"},
    "telegram": {"name": "Telegram", "auth_type": "bot_token", "token_key": "TELEGRAM_BOT_TOKEN", "api_base": "https://api.telegram.org"},
    "zoom": {"name": "Zoom", "auth_type": "oauth", "client_id_key": "ZOOM_CLIENT_ID", "client_secret_key": "ZOOM_CLIENT_SECRET", "auth_url": "https://zoom.us/oauth/authorize", "token_url": "https://zoom.us/oauth/token", "scopes": "meeting:write,meeting:read,user:read", "api_base": "https://api.zoom.us/v2"},
}



def _get_token(db_ref, platform, conn):
    """Get decrypted token from connection"""
    if conn.get("access_token"):
        from encryption import get_fernet; fernet = get_fernet()
        try:
            return fernet.decrypt(conn["access_token"].encode()).decode()
        except Exception as _e:
            logger.warning(f"Caught exception: {_e}")
    return None


def register_platform_plugin_routes(api_router, db, get_current_user):

    async def _budget_guard(provider: str, user_id: str = None, org_id: str = None, workspace_id: str = None, action: str = "plugin"):
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
            logger.debug(f"Plugin budget guard skipped for {provider}: {exc}")
            return {"cost": 0, "budget": {}}

    async def _budget_log(provider: str, budget_ctx: dict, user_id: str = None, org_id: str = None, workspace_id: str = None, action: str = "plugin"):
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
            logger.debug(f"Plugin budget log skipped for {provider}: {exc}")

    # ============ Platform Status & Config ============

    @api_router.get("/plugins/platforms")
    async def list_platforms(request: Request):
        await get_current_user(request)
        from key_resolver import get_integration_key
        result = []
        for key, cfg in PLATFORM_CONFIGS.items():
            token_key = cfg.get("client_id_key") or cfg.get("token_key", "")
            configured = bool(await get_integration_key(db, token_key) if token_key else "")
            result.append({
                "platform": key, "name": cfg["name"], "auth_type": cfg["auth_type"],
                "configured": configured,
                "required_key": token_key,
                "setup_url": f"Add {token_key} to integration settings" if not configured else "Ready",
            })
        return {"platforms": result}

    # ============ Connection Management (all platforms) ============

    @api_router.post("/plugins/{platform}/connect")
    async def connect_platform(platform: str, request: Request):
        user = await get_current_user(request)
        if platform not in PLATFORM_CONFIGS:
            raise HTTPException(400, f"Unknown platform. Use: {list(PLATFORM_CONFIGS.keys())}")
        cfg = PLATFORM_CONFIGS[platform]
        body = await request.json()
        scope = body.get("scope", "user")
        org_id = body.get("org_id")

        conn_id = f"plg_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        if cfg["auth_type"] == "oauth":
            from key_resolver import get_integration_key
            client_id = await get_integration_key(db, cfg.get("client_id_key", ""), org_id)
            if not client_id:
                raise HTTPException(501, f"{cfg['name']} not configured. Add {cfg.get('client_id_key', '')} to integration settings.")

            import secrets
            state = secrets.token_urlsafe(24)
            await db.plugin_connections.insert_one({
                "connection_id": conn_id, "platform": platform, "scope": scope,
                "org_id": org_id, "user_id": user["user_id"],
                "status": "pending", "oauth_state": state,
                "access_token": None, "created_at": now,
            })
            redirect_uri = body.get("redirect_uri", f"{os.environ.get('APP_URL', '')}/api/plugins/{platform}/callback")
            from nexus_utils import validate_redirect_uri
            redirect_uri = validate_redirect_uri(redirect_uri, os.environ.get("APP_URL", ""))
            auth_url = f"{cfg['auth_url']}?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={state}&scope={cfg.get('scopes', '')}"
            return {"connection_id": conn_id, "auth_url": auth_url, "state": state}

        elif cfg["auth_type"] in ("bot_token", "api_key", "webhook"):
            token = body.get("token", "")
            if not token:
                from key_resolver import get_integration_key
                env_token = await get_integration_key(db, cfg.get("token_key", ""))
                if not env_token:
                    raise HTTPException(501, f"{cfg['name']} not configured. Add {cfg.get('token_key', '')} or provide a token.")
                token = env_token
            from encryption import get_fernet; fernet = get_fernet()
            enc = fernet.encrypt(token.encode()).decode()
            await db.plugin_connections.insert_one({
                "connection_id": conn_id, "platform": platform, "scope": scope,
                "org_id": org_id, "user_id": user["user_id"],
                "status": "active", "access_token": enc,
                "webhook_url": body.get("webhook_url"),
                "server_url": body.get("server_url"),
                "created_at": now,
            })
            return {"connection_id": conn_id, "status": "active", "platform": platform}

    @api_router.post("/plugins/{platform}/callback")
    async def oauth_callback(platform: str, request: Request):
        body = await request.json()
        code = body.get("code", "")
        state = body.get("state", "")
        conn = await db.plugin_connections.find_one({"oauth_state": state, "status": "pending"})
        if not conn:
            raise HTTPException(404, "Connection not found")
        cfg = PLATFORM_CONFIGS[platform]
        budget_ctx = await _budget_guard(platform, user_id=conn.get("user_id"), org_id=conn.get("org_id"), action="plugin_oauth_callback")
        from key_resolver import get_integration_key
        org_id = conn.get("org_id")
        client_id = await get_integration_key(db, cfg.get("client_id_key", ""), org_id)
        client_secret = await get_integration_key(db, cfg.get("client_secret_key", ""), org_id)
        try:
            import httpx
            from nexus_utils import now_iso, validate_redirect_uri
            redirect_uri = validate_redirect_uri(
                body.get("redirect_uri", f"{os.environ.get('APP_URL', '')}/api/plugins/{platform}/callback"),
                os.environ.get("APP_URL", "")
            )
            async with httpx.AsyncClient() as client:
                resp = await client.post(cfg["token_url"], data={
                    "client_id": client_id, "client_secret": client_secret,
                    "code": code, "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                })
                tokens = resp.json()
            if "access_token" not in tokens:
                raise HTTPException(400, f"Auth failed: {tokens.get('error', 'unknown')}")
            from encryption import get_fernet; fernet = get_fernet()
            enc = fernet.encrypt(tokens["access_token"].encode()).decode()
            await db.plugin_connections.update_one({"connection_id": conn["connection_id"]}, {"$set": {"status": "active", "access_token": enc}})
            await _budget_log(platform, budget_ctx, user_id=conn.get("user_id"), org_id=conn.get("org_id"), action="plugin_oauth_callback")
            return {"connection_id": conn["connection_id"], "status": "active"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"OAuth failed: {str(e)[:200]}")

    @api_router.get("/plugins/connections")
    async def list_connections(request: Request, platform: Optional[str] = None, scope: str = "user", org_id: Optional[str] = None):
        user = await get_current_user(request)
        query = {"status": {"$ne": "revoked"}}
        if platform:
            query["platform"] = platform
        if scope == "org" and org_id:
            query["org_id"] = org_id
        else:
            query["user_id"] = user["user_id"]
        conns = await db.plugin_connections.find(query, {"_id": 0, "access_token": 0, "oauth_state": 0}).to_list(20)
        return {"connections": conns}

    @api_router.delete("/plugins/connections/{conn_id}")
    async def disconnect_platform(conn_id: str, request: Request):
        await get_current_user(request)
        await db.plugin_connections.update_one({"connection_id": conn_id}, {"$set": {"status": "revoked"}})
        return {"message": "Disconnected"}

    # ============ Channel Mapping ============

    @api_router.post("/plugins/{platform}/map-channel")
    async def map_channel(platform: str, request: Request):
        """Map an external platform channel to a Nexus channel"""
        user = await get_current_user(request)
        body = await request.json()
        mapping_id = f"cmap_{uuid.uuid4().hex[:12]}"
        mapping = {
            "mapping_id": mapping_id,
            "platform": platform,
            "connection_id": body.get("connection_id", ""),
            "nexus_channel_id": body.get("nexus_channel_id", ""),
            "external_channel_id": body.get("external_channel_id", ""),
            "external_channel_name": body.get("external_channel_name", ""),
            "sync_direction": body.get("sync_direction", "bidirectional"),  # to_nexus, from_nexus, bidirectional
            "enabled": True,
            "created_by": user["user_id"], "created_at": now_iso(),
        }
        await db.channel_mappings.insert_one(mapping)
        return {k: v for k, v in mapping.items() if k != "_id"}

    @api_router.get("/plugins/channel-mappings")
    async def list_channel_mappings(request: Request, nexus_channel_id: Optional[str] = None):
        await get_current_user(request)
        query = {"enabled": True}
        if nexus_channel_id:
            query["nexus_channel_id"] = nexus_channel_id
        mappings = await db.channel_mappings.find(query, {"_id": 0}).to_list(50)
        return {"mappings": mappings}

    @api_router.delete("/plugins/channel-mappings/{mapping_id}")
    async def remove_channel_mapping(mapping_id: str, request: Request):
        await get_current_user(request)
        await db.channel_mappings.delete_one({"mapping_id": mapping_id})
        return {"message": "Mapping removed"}

    # ============ Send Message (Nexus → Platform) ============

    @api_router.post("/plugins/{platform}/send")
    async def send_to_platform(platform: str, request: Request):
        """Send a message from Nexus to an external platform"""
        user = await get_current_user(request)
        body = await request.json()
        conn_id = body.get("connection_id", "")
        channel_id = body.get("external_channel_id", "")
        message = body.get("message", "")

        if not message:
            raise HTTPException(400, "Message required")

        conn = await db.plugin_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn:
            raise HTTPException(404, "Connection not found")
        budget_ctx = await _budget_guard(platform, user_id=user["user_id"], org_id=conn.get("org_id"), action="plugin_send")

        token = _get_token(db, platform, conn)
        if not token:
            raise HTTPException(401, "Invalid token")

        cfg = PLATFORM_CONFIGS[platform]
        result = {"sent": False, "platform": platform}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                if platform == "slack":
                    resp = await client.post(f"{cfg['api_base']}/chat.postMessage", headers={"Authorization": f"Bearer {token}"}, json={"channel": channel_id, "text": message})
                    result = {"sent": resp.json().get("ok", False), "ts": resp.json().get("ts")}

                elif platform == "discord":
                    resp = await client.post(f"{cfg['api_base']}/channels/{channel_id}/messages", headers={"Authorization": f"Bot {token}"}, json={"content": message})
                    result = {"sent": resp.status_code == 200, "message_id": resp.json().get("id")}

                elif platform == "msteams":
                    resp = await client.post(f"{cfg['api_base']}/teams/{body.get('team_id')}/channels/{channel_id}/messages", headers={"Authorization": f"Bearer {token}"}, json={"body": {"content": message}})
                    result = {"sent": resp.status_code in (200, 201)}

                elif platform == "telegram":
                    resp = await client.post(f"{cfg['api_base']}/bot{token}/sendMessage", json={"chat_id": channel_id, "text": message, "parse_mode": "Markdown"})
                    result = {"sent": resp.json().get("ok", False)}

                elif platform == "mattermost":
                    server_url = conn.get("server_url", "")
                    resp = await client.post(f"{server_url}/api/v4/posts", headers={"Authorization": f"Bearer {token}"}, json={"channel_id": channel_id, "message": message})
                    result = {"sent": resp.status_code in (200, 201)}

                elif platform == "whatsapp":
                    phone_id = body.get("phone_number_id", "")
                    resp = await client.post(f"{cfg['api_base']}/{phone_id}/messages", headers={"Authorization": f"Bearer {token}"}, json={"messaging_product": "whatsapp", "to": channel_id, "type": "text", "text": {"body": message}})
                    result = {"sent": resp.status_code in (200, 201)}

                else:
                    result = {"sent": False, "error": f"Send not implemented for {platform}"}

        except Exception as e:
            result = {"sent": False, "error": str(e)[:200]}

        # Log
        await db.plugin_messages.insert_one({
            "message_id": f"pm_{uuid.uuid4().hex[:8]}", "platform": platform,
            "direction": "outbound", "connection_id": conn_id,
            "external_channel_id": channel_id, "content": message[:500],
            "result": result, "timestamp": now_iso(),
        })

        if result.get("sent"):
            await _budget_log(platform, budget_ctx, user_id=user["user_id"], org_id=conn.get("org_id"), action="plugin_send")

        return result

    # ============ Incoming Webhooks (Platform → Nexus) ============

    @api_router.post("/plugins/{platform}/webhook")
    async def receive_webhook(platform: str, request: Request):
        """Public endpoint — receives messages from external platforms and relays to Nexus"""
        body = await request.json()

        # Platform-specific event parsing
        nexus_message = None
        external_channel = ""
        sender_name = ""

        if platform == "slack":
            # Slack URL verification challenge
            if body.get("type") == "url_verification":
                return {"challenge": body.get("challenge", "")}
            event = body.get("event") or {}
            if event.get("type") == "message" and not event.get("bot_id"):
                external_channel = event.get("channel", "")
                sender_name = event.get("user", "slack_user")
                nexus_message = event.get("text", "")

        elif platform == "discord":
            if body.get("type") == 1:  # PING
                return {"type": 1}
            if body.get("t") == "MESSAGE_CREATE":
                d = body.get("d") or {}
                external_channel = d.get("channel_id", "")
                sender_name = (d.get("author") or {}).get("username", "discord_user")
                nexus_message = d.get("content", "")

        elif platform == "telegram":
            msg = body.get("message") or {}
            external_channel = str((msg.get("chat") or {}).get("id", ""))
            sender_name = (msg.get("from") or {}).get("first_name", "telegram_user")
            nexus_message = msg.get("text", "")

        elif platform == "mattermost":
            external_channel = body.get("channel_id", "")
            sender_name = body.get("user_name", "mm_user")
            nexus_message = body.get("text", "")

        elif platform == "msteams":
            external_channel = body.get("channelId", "")
            sender_name = (body.get("from") or {}).get("name", "teams_user")
            nexus_message = body.get("text", "")

        elif platform == "whatsapp":
            entries = body.get("entry", [{}])
            for entry in entries:
                for change in entry.get("changes") or []:
                    msgs = (change.get("value") or {}).get("messages") or []
                    if msgs:
                        nexus_message = (msgs[0].get("text") or {}).get("body", "")
                        sender_name = msgs[0].get("from", "whatsapp_user")

        # Relay to mapped Nexus channel
        relayed = False
        if nexus_message and external_channel:
            mapping = await db.channel_mappings.find_one({
                "platform": platform, "external_channel_id": external_channel,
                "enabled": True, "sync_direction": {"$in": ["to_nexus", "bidirectional"]}
            })
            if mapping:
                msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                await db.messages.insert_one({
                    "message_id": msg_id, "channel_id": mapping["nexus_channel_id"],
                    "sender_type": "external", "sender_id": f"{platform}:{sender_name}",
                    "sender_name": f"{sender_name} ({PLATFORM_CONFIGS[platform]['name']})",
                    "content": nexus_message, "source_platform": platform,
                    "created_at": now_iso(),
                })
                relayed = True

        # Log
        await db.plugin_messages.insert_one({
            "message_id": f"pm_{uuid.uuid4().hex[:8]}", "platform": platform,
            "direction": "inbound", "external_channel_id": external_channel,
            "sender": sender_name, "content": (nexus_message or "")[:500],
            "relayed": relayed, "timestamp": now_iso(),
        })

        return {"processed": True, "relayed": relayed}

    # ============ Zoom Meetings ============

    @api_router.post("/plugins/zoom/create-meeting")
    async def create_zoom_meeting(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        conn = await db.plugin_connections.find_one({"platform": "zoom", "user_id": user["user_id"], "status": "active"})
        if not conn:
            raise HTTPException(404, "No Zoom connection. Connect Zoom first.")
        budget_ctx = await _budget_guard("zoom", user_id=user["user_id"], org_id=conn.get("org_id"), action="zoom_meeting_create")
        token = _get_token(db, "zoom", conn)
        if not token:
            raise HTTPException(401, "Token expired. Reconnect Zoom.")

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{PLATFORM_CONFIGS['zoom']['api_base']}/users/me/meetings",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "topic": body.get("topic", "Nexus AI Meeting"),
                        "type": 2,
                        "duration": body.get("duration", 60),
                        "settings": {"join_before_host": True, "auto_recording": body.get("auto_record", "none")},
                    })
                meeting = resp.json()
            await _budget_log("zoom", budget_ctx, user_id=user["user_id"], org_id=conn.get("org_id"), action="zoom_meeting_create")
            return {"meeting_id": meeting.get("id"), "join_url": meeting.get("join_url"), "start_url": meeting.get("start_url"), "password": meeting.get("password")}
        except Exception as e:
            raise HTTPException(500, f"Failed to create meeting: {str(e)[:200]}")

    @api_router.post("/plugins/zoom/webhook")
    async def zoom_webhook(request: Request):
        """Receive Zoom meeting events (recording complete, transcript ready)"""
        body = await request.json()
        event = body.get("event", "")
        payload = body.get("payload") or {}

        if event == "recording.completed":
            recording_files = (payload.get("object") or {}).get("recording_files") or []
            for rf in recording_files:
                if rf.get("file_type") == "TRANSCRIPT":
                    await db.zoom_transcripts.insert_one({
                        "meeting_id": (payload.get("object") or {}).get("id"),
                        "download_url": rf.get("download_url", ""),
                        "file_type": rf.get("file_type"),
                        "timestamp": now_iso(),
                    })

        return {"processed": True, "event": event}

    # ============ Plugin Message History ============

    @api_router.get("/plugins/messages")
    async def list_plugin_messages(request: Request, platform: Optional[str] = None, direction: Optional[str] = None, limit: int = 50):
        await get_current_user(request)
        query = {}
        if platform:
            query["platform"] = platform
        if direction:
            query["direction"] = direction
        msgs = await db.plugin_messages.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"messages": msgs}

    # ============ Plugin Status Monitor ============

    @api_router.get("/plugins/status")
    async def get_plugin_status(request: Request):
        """Get status of all connected plugins"""
        user = await get_current_user(request)
        conns = await db.plugin_connections.find({"user_id": user["user_id"], "status": "active"}, {"_id": 0, "access_token": 0}).to_list(20)
        by_platform = {}
        for c in conns:
            by_platform[c["platform"]] = {"connection_id": c["connection_id"], "status": "active", "connected_at": c.get("created_at")}
        # Add unconfigured platforms
        for key in PLATFORM_CONFIGS:
            if key not in by_platform:
                by_platform[key] = {"status": "not_connected"}
        return {"plugins": by_platform}
