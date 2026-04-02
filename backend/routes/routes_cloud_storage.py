"""Cloud Storage Connectors — Google Drive, OneDrive, Dropbox at Org + User level"""
import uuid
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import validate_external_url, now_iso

logger = logging.getLogger(__name__)

PROVIDERS = {
    "google_drive": {
        "name": "Google Drive", "icon": "google",
        "client_id_key": "GOOGLE_DRIVE_CLIENT_ID", "client_secret_key": "GOOGLE_DRIVE_CLIENT_SECRET",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive.readonly"],
        "api_base": "https://www.googleapis.com/drive/v3",
    },
    "onedrive": {
        "name": "OneDrive", "icon": "microsoft",
        "client_id_key": "MICROSOFT_CLIENT_ID", "client_secret_key": "MICROSOFT_CLIENT_SECRET",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": ["Files.Read", "Files.Read.All", "offline_access"],
        "api_base": "https://graph.microsoft.com/v1.0",
    },
    "dropbox": {
        "name": "Dropbox", "icon": "dropbox",
        "client_id_key": "DROPBOX_APP_KEY", "client_secret_key": "DROPBOX_APP_SECRET",
        "auth_url": "https://www.dropbox.com/oauth2/authorize",
        "token_url": "https://api.dropboxapi.com/oauth2/token",
        "scopes": ["files.metadata.read", "files.content.read"],
    },
    "box": {
        "name": "Box", "icon": "box",
        "client_id_key": "BOX_CLIENT_ID", "client_secret_key": "BOX_CLIENT_SECRET",
        "auth_url": "https://account.box.com/api/oauth2/authorize",
        "token_url": "https://api.box.com/oauth2/token",
        "scopes": ["root_readonly"],
    },
}



def register_cloud_storage_routes(api_router, db, get_current_user):

    async def _budget_guard(provider: str, user_id: str, org_id: str = None, workspace_id: str = None, call_count: int = 1, action: str = "cloud_storage"):
        try:
            from managed_keys import PLATFORM_KEY_PROVIDERS, check_usage_budget, estimate_integration_cost_usd, emit_budget_alert
            if provider not in PLATFORM_KEY_PROVIDERS:
                return {"cost": 0, "budget": {}}
            estimated_cost = estimate_integration_cost_usd(provider, call_count)
            budget = await check_usage_budget(provider, estimated_cost, workspace_id=workspace_id, org_id=org_id, user_id=user_id)
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                message = f"{scope_name} Nexus AI budget reached for {provider} during {action}."
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=message)
                raise HTTPException(429, message)
            return {"cost": estimated_cost, "budget": budget}
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug(f"Cloud budget guard skipped for {provider}: {exc}")
            return {"cost": 0, "budget": {}}

    async def _budget_log(provider: str, user_id: str, budget_ctx: dict, org_id: str = None, workspace_id: str = None, call_count: int = 1, action: str = "cloud_storage"):
        try:
            from managed_keys import PLATFORM_KEY_PROVIDERS, record_usage_event, emit_budget_alert
            if provider not in PLATFORM_KEY_PROVIDERS:
                return
            cost = budget_ctx.get("cost", 0)
            await record_usage_event(provider, cost, user_id=user_id, workspace_id=workspace_id, org_id=org_id, usage_type="integration", key_source="managed_or_override", call_count=call_count, metadata={"action": action})
            budget = budget_ctx.get("budget") or {}
            if budget.get("warn"):
                scope_name = (budget.get("scope_type") or "platform").capitalize()
                message = f"{scope_name} Nexus AI budget warning for {provider} during {action}."
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", cost), budget.get("warn_threshold_usd"), user_id=user_id, workspace_id=workspace_id, org_id=org_id, message=message)
        except Exception as exc:
            logger.debug(f"Cloud budget log skipped for {provider}: {exc}")

    async def _refresh_token_if_needed(conn):
        """Check if token is expired and refresh if needed. Returns valid access_token."""
        from encryption import get_fernet; fernet = get_fernet()
        expires_at = conn.get("token_expires_at", "")
        if expires_at and expires_at < datetime.now(timezone.utc).isoformat():
            # Token expired, try refresh
            refresh_enc = conn.get("refresh_token")
            if not refresh_enc:
                raise HTTPException(401, "Token expired and no refresh token. Please reconnect.")
            try:
                refresh_token = fernet.decrypt(refresh_enc.encode()).decode()
            except Exception:
                raise HTTPException(401, "Failed to decrypt refresh token. Please reconnect.")
            
            provider = conn["provider"]
            prov = PROVIDERS[provider]
            from key_resolver import get_integration_key
            client_id = await get_integration_key(db, prov["client_id_key"], conn.get("org_id"))
            client_secret = await get_integration_key(db, prov["client_secret_key"], conn.get("org_id"))
            
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(prov["token_url"], data={
                    "client_id": client_id, "client_secret": client_secret,
                    "refresh_token": refresh_token, "grant_type": "refresh_token",
                })
                if resp.status_code != 200:
                    raise HTTPException(401, f"Token refresh failed ({resp.status_code}). Please reconnect.")
                tokens = resp.json()
            
            new_access = tokens.get("access_token", "")
            new_refresh = tokens.get("refresh_token", refresh_token)
            expires_in = tokens.get("expires_in", 3600)
            enc_access = fernet.encrypt(new_access.encode()).decode()
            enc_refresh = fernet.encrypt(new_refresh.encode()).decode()
            
            await db.cloud_connections.update_one(
                {"connection_id": conn["connection_id"]},
                {"$set": {
                    "access_token": enc_access,
                    "refresh_token": enc_refresh,
                    "token_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat(),
                }}
            )
            return new_access
        
        # Token still valid
        enc = conn.get("access_token", "")
        if not enc:
            raise HTTPException(401, "No access token. Please reconnect.")
        try:
            return fernet.decrypt(enc.encode()).decode()
        except Exception:
            raise HTTPException(401, "Failed to decrypt token. Please reconnect.")

    # ============ Connection Management ============

    @api_router.post("/cloud-storage/connect")
    async def initiate_connection(request: Request):
        """Initiate OAuth connection to a cloud provider"""
        user = await get_current_user(request)
        body = await request.json()
        provider = body.get("provider", "")
        scope = body.get("scope", "user")  # user or org
        org_id = body.get("org_id")

        if provider not in PROVIDERS:
            raise HTTPException(400, f"Unknown provider. Use: {list(PROVIDERS.keys())}")
        if scope == "org" and not org_id:
            raise HTTPException(400, "org_id required for org-level connections")

        prov = PROVIDERS[provider]
        from key_resolver import get_integration_key
        client_id = await get_integration_key(db, prov["client_id_key"], org_id)

        if not client_id:
            raise HTTPException(501, f"{prov['name']} not configured. Add {prov['client_id_key']} to platform or org settings.")

        # Generate state token for OAuth
        import secrets
        state = secrets.token_urlsafe(24)
        conn_id = f"csc_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # Store pending connection
        await db.cloud_connections.insert_one({
            "connection_id": conn_id, "provider": provider,
            "scope": scope, "org_id": org_id,
            "user_id": user["user_id"], "user_name": user.get("name", ""),
            "status": "pending",  # pending, active, expired, revoked
            "oauth_state": state,
            "access_token": None, "refresh_token": None,
            "token_expires_at": None,
            "account_email": None, "account_name": None,
            "storage_quota": None,
            "created_at": now, "last_sync_at": None,
        })

        # Build OAuth URL
        from nexus_utils import validate_redirect_uri
        redirect_uri = validate_redirect_uri(
            body.get("redirect_uri", f"{os.environ.get('APP_URL', '')}/cloud-storage/callback"),
            os.environ.get("APP_URL", "")
        )
        auth_url = (
            f"{prov['auth_url']}?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code&state={state}"
            f"&scope={' '.join(prov['scopes'])}"
            f"&access_type=offline&prompt=consent"
        )

        return {"connection_id": conn_id, "auth_url": auth_url, "state": state, "provider": provider}

    @api_router.post("/cloud-storage/callback")
    async def oauth_callback(request: Request):
        """Handle OAuth callback with authorization code"""
        body = await request.json()
        code = body.get("code", "")
        state = body.get("state", "")

        if not code or not state:
            raise HTTPException(400, "code and state required")

        conn = await db.cloud_connections.find_one({"oauth_state": state, "status": "pending"})
        if not conn:
            raise HTTPException(404, "Connection not found or already processed")

        provider = conn["provider"]
        prov = PROVIDERS[provider]
        budget_ctx = await _budget_guard(provider, conn["user_id"], org_id=conn.get("org_id"), action="cloud_oauth_callback")

        # Exchange code for tokens
        from key_resolver import get_integration_key
        org_id = conn.get("org_id")
        client_id = await get_integration_key(db, prov["client_id_key"], org_id)
        client_secret = await get_integration_key(db, prov["client_secret_key"], org_id)

        try:
            import httpx
            redirect_uri = body.get("redirect_uri", f"{os.environ.get('APP_URL', '')}/cloud-storage/callback")
            async with httpx.AsyncClient() as client:
                resp = await client.post(prov["token_url"], data={
                    "client_id": client_id, "client_secret": client_secret,
                    "code": code, "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                })
                tokens = resp.json()

            if "access_token" not in tokens:
                raise HTTPException(400, f"Token exchange failed: {tokens.get('error_description', 'unknown')}")

            # Encrypt tokens
            from encryption import get_fernet; fernet = get_fernet()
            enc_access = fernet.encrypt(tokens["access_token"].encode()).decode()
            enc_refresh = fernet.encrypt(tokens.get("refresh_token", "").encode()).decode() if tokens.get("refresh_token") else None

            await db.cloud_connections.update_one(
                {"connection_id": conn["connection_id"]},
                {"$set": {
                    "status": "active",
                    "access_token": enc_access,
                    "refresh_token": enc_refresh,
                    "token_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))).isoformat(),
                    "last_sync_at": now_iso(),
                }}
            )

            await _budget_log(provider, conn["user_id"], budget_ctx, org_id=conn.get("org_id"), action="cloud_oauth_callback")

            return {"connection_id": conn["connection_id"], "status": "active", "provider": provider}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"OAuth failed: {str(e)[:200]}")

    @api_router.get("/cloud-storage/connections")
    async def list_connections(request: Request, scope: str = "user", org_id: Optional[str] = None):
        """List cloud storage connections"""
        user = await get_current_user(request)
        query = {"status": {"$ne": "revoked"}}
        if scope == "org" and org_id:
            query["org_id"] = org_id
            query["scope"] = "org"
        else:
            query["user_id"] = user["user_id"]
            query["scope"] = "user"

        conns = await db.cloud_connections.find(query, {"_id": 0, "access_token": 0, "refresh_token": 0, "oauth_state": 0}).to_list(10)
        return {"connections": conns}

    @api_router.delete("/cloud-storage/connections/{conn_id}")
    async def revoke_connection(conn_id: str, request: Request):
        """Revoke/disconnect a cloud storage connection"""
        await get_current_user(request)
        await db.cloud_connections.update_one({"connection_id": conn_id}, {"$set": {"status": "revoked"}})
        return {"message": "Disconnected"}

    @api_router.get("/cloud-storage/connections/{conn_id}/status")
    async def get_connection_status(conn_id: str, request: Request):
        await get_current_user(request)
        conn = await db.cloud_connections.find_one({"connection_id": conn_id}, {"_id": 0, "access_token": 0, "refresh_token": 0, "oauth_state": 0})
        if not conn:
            raise HTTPException(404, "Connection not found")
        return conn

    # ============ File Browsing ============

    @api_router.get("/cloud-storage/connections/{conn_id}/files")
    async def browse_files(conn_id: str, request: Request, path: str = "", search: str = "", page_token: str = ""):
        """Browse files in a connected cloud storage"""
        await get_current_user(request)
        conn = await db.cloud_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn:
            raise HTTPException(404, "Connection not found or inactive")

        from encryption import get_fernet; fernet = get_fernet()
        try:
            access_token = fernet.decrypt(conn["access_token"].encode()).decode()
        except Exception as _e:
            logger.warning(f"Caught exception: {_e}")
            raise HTTPException(401, "Token expired. Reconnect your cloud storage.")

        provider = conn["provider"]
        files = []
        budget_ctx = await _budget_guard(provider, conn["user_id"], org_id=conn.get("org_id"), action="cloud_browse")

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                if provider == "google_drive":
                    q = f"'{path or 'root'}' in parents and trashed=false"
                    if search:
                        q = f"name contains '{search}' and trashed=false"
                    params = {"q": q, "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,thumbnailLink)", "pageSize": 50}
                    if page_token:
                        params["pageToken"] = page_token
                    resp = await client.get(f"{PROVIDERS['google_drive']['api_base']}/files", headers={"Authorization": f"Bearer {access_token}"}, params=params)
                    data = resp.json()
                    for f in data.get("files") or []:
                        files.append({
                            "id": f["id"], "name": f["name"], "mime_type": f.get("mimeType", ""),
                            "size": int(f.get("size", 0)), "modified": f.get("modifiedTime"),
                            "is_folder": f.get("mimeType") == "application/vnd.google-apps.folder",
                            "thumbnail": f.get("thumbnailLink"),
                        })

                elif provider == "onedrive":
                    url = f"{PROVIDERS['onedrive']['api_base']}/me/drive/root/children" if not path else f"{PROVIDERS['onedrive']['api_base']}/me/drive/items/{path}/children"
                    if search:
                        url = f"{PROVIDERS['onedrive']['api_base']}/me/drive/root/search(q='{search}')"
                    resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
                    data = resp.json()
                    for f in data.get("value") or []:
                        files.append({
                            "id": f["id"], "name": f["name"], "mime_type": (f.get("file") or {}).get("mimeType", ""),
                            "size": f.get("size", 0), "modified": f.get("lastModifiedDateTime"),
                            "is_folder": "folder" in f, "thumbnail": None,
                        })

                elif provider == "dropbox":
                    resp = await client.post(f"{PROVIDERS['dropbox']['api_base']}/files/list_folder",
                        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                        json={"path": path or "", "limit": 50})
                    data = resp.json()
                    for f in data.get("entries") or []:
                        files.append({
                            "id": f.get("id", ""), "name": f["name"],
                            "mime_type": "", "size": f.get("size", 0),
                            "modified": f.get("server_modified"),
                            "is_folder": f[".tag"] == "folder", "thumbnail": None,
                        })

                elif provider == "box":
                    folder_id = path or "0"  # 0 = root folder in Box
                    resp = await client.get(f"{PROVIDERS['box']['api_base']}/folders/{folder_id}/items",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={"fields": "id,name,type,size,modified_at", "limit": 50})
                    data = resp.json()
                    for f in data.get("entries") or []:
                        files.append({
                            "id": f.get("id", ""), "name": f.get("name", ""),
                            "mime_type": "", "size": f.get("size", 0),
                            "modified": f.get("modified_at"),
                            "is_folder": f.get("type") == "folder", "thumbnail": None,
                        })

        except Exception as e:
            logger.error(f"Cloud browse failed: {e}")
            raise HTTPException(502, f"Failed to browse files: {str(e)[:200]}")

        await _budget_log(provider, conn["user_id"], budget_ctx, org_id=conn.get("org_id"), action="cloud_browse")

        return {"files": files, "provider": provider, "path": path}

    # ============ Import File to Repository ============

    @api_router.post("/cloud-storage/connections/{conn_id}/import")
    async def import_file(conn_id: str, request: Request):
        """Import a file from cloud storage into the org repository"""
        user = await get_current_user(request)
        body = await request.json()
        file_id = body.get("file_id", "")
        org_id = body.get("org_id", "")

        conn = await db.cloud_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn:
            raise HTTPException(404, "Connection not found")

        from encryption import get_fernet; fernet = get_fernet()
        access_token = fernet.decrypt(conn["access_token"].encode()).decode()
        provider = conn["provider"]
        budget_ctx = await _budget_guard(provider, user["user_id"], org_id=conn.get("org_id") or org_id, action="cloud_import")

        try:
            import httpx
            import base64
            content = b""
            filename = "imported_file"
            mime_type = "application/octet-stream"

            async with httpx.AsyncClient() as client:
                if provider == "google_drive":
                    # Get metadata
                    meta = await client.get(f"{PROVIDERS['google_drive']['api_base']}/files/{file_id}",
                        headers={"Authorization": f"Bearer {access_token}"}, params={"fields": "name,mimeType,size"})
                    meta_data = meta.json()
                    filename = meta_data.get("name", "file")
                    mime_type = meta_data.get("mimeType", "application/octet-stream")
                    # Download
                    if "google-apps" in mime_type:
                        export_mime = "application/pdf"
                        resp = await client.get(f"{PROVIDERS['google_drive']['api_base']}/files/{file_id}/export",
                            headers={"Authorization": f"Bearer {access_token}"}, params={"mimeType": export_mime})
                        mime_type = export_mime
                        filename += ".pdf"
                    else:
                        resp = await client.get(f"{PROVIDERS['google_drive']['api_base']}/files/{file_id}",
                            headers={"Authorization": f"Bearer {access_token}"}, params={"alt": "media"})
                    content = resp.content

                elif provider == "onedrive":
                    meta = await client.get(f"{PROVIDERS['onedrive']['api_base']}/me/drive/items/{file_id}",
                        headers={"Authorization": f"Bearer {access_token}"})
                    meta_data = meta.json()
                    filename = meta_data.get("name", "file")
                    download_url = meta_data.get("@microsoft.graph.downloadUrl", "")
                    if download_url:
                        resp = await client.get(download_url)
                        content = resp.content
                    mime_type = (meta_data.get("file") or {}).get("mimeType", "application/octet-stream")

                elif provider == "dropbox":
                    resp = await client.post("https://content.dropboxapi.com/2/files/download",
                        headers={"Authorization": f"Bearer {access_token}", "Dropbox-API-Arg": f'{{"path": "{file_id}"}}'},
                    )
                    content = resp.content
                    filename = file_id.split("/")[-1] if "/" in file_id else file_id

                elif provider == "box":
                    # Get file info
                    meta = await client.get(f"{PROVIDERS['box']['api_base']}/files/{file_id}",
                        headers={"Authorization": f"Bearer {access_token}"})
                    meta_data = meta.json()
                    filename = meta_data.get("name", "file")
                    # Download
                    resp = await client.get(f"{PROVIDERS['box']['api_base']}/files/{file_id}/content",
                        headers={"Authorization": f"Bearer {access_token}"}, follow_redirects=True)
                    content = resp.content

            if not content:
                raise HTTPException(422, "Failed to download file content")

            # Save to repository
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            preview_type = "image" if ext in ("png", "jpg", "jpeg", "gif", "webp") else "pdf" if ext == "pdf" else "text" if ext in ("txt", "md", "csv") else "document" if ext in ("doc", "docx") else "none"

            repo_id = f"rf_{uuid.uuid4().hex[:12]}"
            now = now_iso()
            b64 = base64.b64encode(content).decode("utf-8")

            await db.org_repository.insert_one({
                "file_id": repo_id, "org_id": org_id or conn.get("org_id", ""),
                "filename": filename, "ext": ext, "mime_type": mime_type,
                "size": len(content), "preview_type": preview_type,
                "folder": f"/imported/{provider}",
                "tags": ["imported", provider], "description": f"Imported from {PROVIDERS[provider]['name']}",
                "index_text": "", "source_provider": provider, "source_file_id": file_id,
                "uploaded_by": user["user_id"], "uploaded_by_name": user.get("name", ""),
                "created_at": now, "updated_at": now,
            })
            await db.repo_file_data.insert_one({"file_id": repo_id, "data": b64, "created_at": now})

            await _budget_log(provider, user["user_id"], budget_ctx, org_id=conn.get("org_id") or org_id, action="cloud_import")

            return {"file_id": repo_id, "filename": filename, "size": len(content), "provider": provider}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Import failed: {str(e)[:200]}")

    # ============ Provider Config ============

    @api_router.get("/cloud-storage/providers")
    async def get_providers(request: Request):
        await get_current_user(request)
        from key_resolver import get_integration_key
        result = []
        for key, prov in PROVIDERS.items():
            configured = bool(await get_integration_key(db, prov["client_id_key"]))
            result.append({
                "provider": key, "name": prov["name"], "icon": prov["icon"],
                "configured": configured,
                "setup_instructions": f"Add {prov['client_id_key']} and {prov['client_secret_key']} to platform or org integration settings." if not configured else "Ready to connect",
            })
        return {"providers": result}

    # ============ Sync Status ============

    @api_router.post("/cloud-storage/connections/{conn_id}/sync")
    async def sync_connection(conn_id: str, request: Request):
        """Refresh file list and update sync timestamp"""
        user = await get_current_user(request)
        conn = await db.cloud_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn:
            raise HTTPException(404, "Connection not found")
        budget_ctx = await _budget_guard(conn["provider"], user["user_id"], org_id=conn.get("org_id"), action="cloud_sync")
        await db.cloud_connections.update_one({"connection_id": conn_id}, {"$set": {"last_sync_at": now_iso()}})
        await _budget_log(conn["provider"], user["user_id"], budget_ctx, org_id=conn.get("org_id"), action="cloud_sync")
        return {"status": "synced", "last_sync_at": now_iso()}
