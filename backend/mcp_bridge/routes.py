from nexus_utils import now_iso
"""MCP Desktop Bridge — Connects Nexus AI agents to user desktop tools.

Users install a lightweight bridge agent on their desktop. The bridge connects
to Nexus via WebSocket. AI agents can then invoke tools on the user's machine:
- Read/write files
- Run terminal commands
- Interact with browser
- Access local apps

All write/destructive actions require user approval through the bridge UI.
"""
import uuid
import json
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Active bridge connections: user_id -> {"ws": WebSocket, "capabilities": [...], "status": "connected"}
_bridge_connections = {}
# Pending tool calls waiting for response: call_id -> asyncio.Future
_pending_calls = {}



def register_bridge_routes(app, api_router, db, get_current_user):

    # ============ WebSocket: Desktop Bridge Connection ============

    async def _handle_bridge_ws(websocket: WebSocket, user_id: str, bridge_token: str):
        """WebSocket handler for the desktop bridge agent."""
        # Validate bridge token
        import hashlib
        token_hash = hashlib.sha256(bridge_token.encode()).hexdigest()
        token_doc = await db.bridge_tokens.find_one(
            {"user_id": user_id, "token_hash": token_hash, "revoked": {"$ne": True}}, {"_id": 0}
        )
        if not token_doc:
            # Fallback to plaintext match for old tokens
            token_doc = await db.bridge_tokens.find_one(
                {"user_id": user_id, "token": bridge_token, "revoked": {"$ne": True}}, {"_id": 0}
            )
        if not token_doc:
            await websocket.close(code=4001, reason="Invalid bridge token")
            return

        await websocket.accept()
        _bridge_connections[user_id] = {
            "ws": websocket,
            "capabilities": [],
            "status": "connected",
            "connected_at": now_iso(),
            "machine_name": "",
            "os": "",
            "token_doc": token_doc,
        }
        # Track for kill switch
        from mcp_bridge.nexus_bridge_state import set_bridge_ws, remove_bridge_ws
        set_bridge_ws(user_id, websocket)
        logger.info(f"Bridge connected for user {user_id}")

        # Update DB status
        await db.bridge_tokens.update_one(
            {"token": bridge_token},
            {"$set": {"status": "connected", "last_connected": now_iso()}}
        )

        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "capabilities":
                    # Bridge reports available tools
                    _bridge_connections[user_id]["capabilities"] = msg.get("tools") or []
                    _bridge_connections[user_id]["machine_name"] = msg.get("machine_name", "")
                    _bridge_connections[user_id]["os"] = msg.get("os", "")
                    logger.info(f"Bridge {user_id}: {len(msg.get('tools', []))} tools available on {msg.get('machine_name', '?')}")

                elif msg_type == "tool_result":
                    # Response to a tool call
                    call_id = msg.get("call_id", "")
                    if call_id in _pending_calls:
                        _pending_calls[call_id].set_result(msg.get("result") or {})

                elif msg_type == "tool_error":
                    call_id = msg.get("call_id", "")
                    if call_id in _pending_calls:
                        _pending_calls[call_id].set_result({"error": msg.get("error", "Unknown error")})

                elif msg_type == "approval_response":
                    call_id = msg.get("call_id", "")
                    if call_id in _pending_calls:
                        if msg.get("approved"):
                            # User approved — bridge will execute and send tool_result
                            pass
                        else:
                            _pending_calls[call_id].set_result({"error": "User denied the action", "denied": True})

                elif msg_type == "heartbeat":
                    await websocket.send_text(json.dumps({"type": "heartbeat_ack"}))

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"Bridge WS error: {e}")
        finally:
            _bridge_connections.pop(user_id, None)
            remove_bridge_ws(user_id)
            await db.bridge_tokens.update_one(
                {"token": bridge_token},
                {"$set": {"status": "disconnected", "last_disconnected": now_iso()}}
            )
            logger.info(f"Bridge disconnected for user {user_id}")

    # ============ Bridge Token Management ============

    @api_router.post("/bridge/tokens")
    async def create_bridge_token(request: Request):
        """Generate a bridge connection token for the desktop agent."""
        user = await get_current_user(request)
        body = await request.json()
        import secrets
        token = secrets.token_urlsafe(48)
        allowed_agents = body.get("allowed_agents") or []  # e.g. ["claude", "chatgpt", "nxa_abc123"]
        allowed_tools = body.get("allowed_tools") or []  # empty = all tools allowed
        workspace_id = body.get("workspace_id", "")  # bind to specific workspace
        doc = {
            "token_id": f"bt_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "workspace_id": workspace_id,
            "token": token,
            "name": body.get("name", "Desktop Bridge"),
            "allowed_agents": allowed_agents,
            "allowed_tools": allowed_tools,
            "status": "created",
            "revoked": False,
            "created_at": now_iso(),
            "last_connected": None,
        }
        await db.bridge_tokens.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @api_router.get("/bridge/tokens")
    async def list_bridge_tokens(request: Request):
        user = await get_current_user(request)
        tokens = await db.bridge_tokens.find(
            {"user_id": user["user_id"], "revoked": {"$ne": True}},
            {"_id": 0}
        ).to_list(10)
        # Mask full token, show last 8 chars
        for t in tokens:
            t["token_preview"] = f"...{t['token'][-8:]}"
            t.pop("token", None)
        return tokens

    @api_router.delete("/bridge/tokens/{token_id}")
    async def revoke_bridge_token(token_id: str, request: Request):
        user = await get_current_user(request)
        await db.bridge_tokens.update_one(
            {"token_id": token_id, "user_id": user["user_id"]},
            {"$set": {"revoked": True}}
        )
        return {"message": "Token revoked"}

    @api_router.put("/bridge/tokens/{token_id}")
    async def update_bridge_token(token_id: str, request: Request):
        """Update allowed agents/tools for a bridge token."""
        user = await get_current_user(request)
        body = await request.json()
        updates = {}
        if "allowed_agents" in body:
            updates["allowed_agents"] = body["allowed_agents"]
        if "allowed_tools" in body:
            updates["allowed_tools"] = body["allowed_tools"]
        if "name" in body:
            updates["name"] = body["name"]
        if updates:
            await db.bridge_tokens.update_one(
                {"token_id": token_id, "user_id": user["user_id"]},
                {"$set": updates}
            )
        token = await db.bridge_tokens.find_one({"token_id": token_id}, {"_id": 0, "token": 0})
        return token or {"error": "Token not found"}

    # ============ Bridge Status ============

    @api_router.get("/bridge/status")
    async def bridge_status(request: Request):
        user = await get_current_user(request)
        conn = _bridge_connections.get(user["user_id"])
        if not conn:
            return {"connected": False, "capabilities": []}
        return {
            "connected": True,
            "machine_name": conn.get("machine_name", ""),
            "os": conn.get("os", ""),
            "capabilities": conn.get("capabilities") or [],
            "connected_at": conn.get("connected_at", ""),
        }

    # Register WebSocket on BOTH paths for backwards compatibility
    @app.websocket("/api/ws/bridge/{user_id}/{bridge_token}")
    async def bridge_ws_api(websocket: WebSocket, user_id: str, bridge_token: str):
        await _handle_bridge_ws(websocket, user_id, bridge_token)

    @app.websocket("/ws/bridge/{user_id}/{bridge_token}")
    async def bridge_ws_legacy(websocket: WebSocket, user_id: str, bridge_token: str):
        await _handle_bridge_ws(websocket, user_id, bridge_token)

    # ============ Tool Invocation (AI agents call this) ============

    @api_router.post("/bridge/invoke")
    async def invoke_bridge_tool(request: Request):
        """AI agent invokes a tool on the user's desktop via the bridge."""
        user = await get_current_user(request)
        body = await request.json()
        tool_name = body.get("tool", "")
        params = body.get("params") or {}
        target_user = body.get("target_user_id", user["user_id"])

        conn = _bridge_connections.get(target_user)
        if not conn:
            raise HTTPException(400, "Desktop bridge not connected. User must install and run the bridge agent.")

        # Enforce agent allowlist from token
        invoking_agent = body.get("invoked_by_agent", body.get("invoked_by", ""))
        token_doc = conn.get("token_doc") or {}
        allowed_agents = token_doc.get("allowed_agents") or []
        if allowed_agents and invoking_agent and invoking_agent not in allowed_agents:
            raise HTTPException(403, f"Agent '{invoking_agent}' is not authorized for this bridge. Allowed: {', '.join(allowed_agents)}")

        # Enforce workspace binding
        token_ws = token_doc.get("workspace_id", "")
        invoke_ws = body.get("workspace_id", "")
        if token_ws and invoke_ws and token_ws != invoke_ws:
            raise HTTPException(403, f"Bridge token is bound to workspace {token_ws}, not {invoke_ws}")

        # Enforce tool allowlist from token
        allowed_tools = token_doc.get("allowed_tools") or []
        if allowed_tools and tool_name not in allowed_tools:
            raise HTTPException(403, f"Tool '{tool_name}' is not authorized for this bridge token.")

        # Check tool is available on the connected bridge
        available_tools = [t["name"] for t in conn.get("capabilities") or []]
        if tool_name not in available_tools:
            raise HTTPException(400, f"Tool '{tool_name}' not available on user's desktop. Available: {', '.join(available_tools)}")

        call_id = f"call_{uuid.uuid4().hex[:12]}"
        future = asyncio.get_event_loop().create_future()
        _pending_calls[call_id] = future

        # Validate params
        if not isinstance(params, dict):
            _pending_calls.pop(call_id, None)
            raise HTTPException(400, "params must be a JSON object")
        MAX_PARAM_SIZE = 50000
        params_str = json.dumps(params)
        if len(params_str) > MAX_PARAM_SIZE:
            _pending_calls.pop(call_id, None)
            raise HTTPException(400, f"params too large ({len(params_str)} > {MAX_PARAM_SIZE})")

        # Determine if this needs user approval
        tool_meta = next((t for t in conn["capabilities"] if t["name"] == tool_name), {})
        needs_approval = tool_meta.get("requires_approval", False)

        # Send tool call to bridge
        try:
            await conn["ws"].send_text(json.dumps({
                "type": "tool_call",
                "call_id": call_id,
                "tool": tool_name,
                "params": params,
                "needs_approval": needs_approval,
            }))
        except Exception as e:
            _pending_calls.pop(call_id, None)
            raise HTTPException(502, f"Failed to reach desktop bridge: {e}")

        # Wait for response (with timeout)
        try:
            result = await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            _pending_calls.pop(call_id, None)
            raise HTTPException(504, "Desktop bridge tool call timed out (60s)")
        finally:
            _pending_calls.pop(call_id, None)

        # Log the invocation
        await db.bridge_audit_log.insert_one({
            "log_id": f"bal_{uuid.uuid4().hex[:12]}",
            "user_id": target_user,
            "tool": tool_name,
            "params": {k: str(v)[:200] for k, v in params.items()},
            "result_summary": str(result)[:500] if not result.get("error") else f"ERROR: {result['error']}",
            "success": not result.get("error"),
            "call_id": call_id,
            "invoked_by": body.get("invoked_by", "api"),
            "created_at": now_iso(),
        })

        if result.get("error"):
            return {"success": False, "error": result["error"], "denied": result.get("denied", False)}
        return {"success": True, "result": result}

    # ============ Audit Log ============

    @api_router.get("/bridge/audit-log")
    async def bridge_audit_log(request: Request, limit: int = 50):
        user = await get_current_user(request)
        logs = await db.bridge_audit_log.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return logs

    @api_router.get("/bridge/download-agent")
    async def download_bridge_agent():
        """Download the nexus_bridge.py desktop agent script."""
        from fastapi.responses import FileResponse
        import os
        agent_path = os.path.join(os.path.dirname(__file__), "nexus_bridge.py")
        return FileResponse(agent_path, filename="nexus_bridge.py", media_type="text/x-python")


    @api_router.post("/bridge/kill-switch")
    async def bridge_kill_switch(request: Request):
        """Emergency disconnect — sends kill signal to the connected bridge."""
        user = await get_current_user(request)
        user_id = user["user_id"]
        from mcp_bridge.nexus_bridge_state import get_bridge_ws
        ws = get_bridge_ws(user_id)
        if ws:
            try:
                import json as _json
                await ws.send_text(_json.dumps({"type": "kill_switch"}))
                return {"killed": True, "user_id": user_id}
            except Exception as e:
                return {"killed": False, "error": str(e)}
        return {"killed": False, "error": "No active bridge connection"}
