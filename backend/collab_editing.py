"""Multi-Cursor Collaborative Editing — Real-time cursor tracking and edit synchronization.

Multiple users and AI agents can edit the same file simultaneously.
Cursor positions are broadcast via WebSocket, and edits are synced through MongoDB.
"""
import uuid
import json
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Active editor sessions: file_id -> {participants: {user_id: {cursor, name, color}}, connections: [ws]}
_editor_sessions = {}

CURSOR_COLORS = [
    "#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#8b5cf6", "#ec4899",
    "#06b6d4", "#f97316", "#84cc16", "#14b8a6", "#a855f7", "#e11d48",
]


def get_cursor_color(index):
    return CURSOR_COLORS[index % len(CURSOR_COLORS)]


def register_collab_editing_routes(app, api_router, db, get_current_user):
    """Register WebSocket and REST endpoints for collaborative editing."""
    from fastapi import Request

    @app.websocket("/api/ws/editor/{file_id}")
    async def editor_websocket(websocket: WebSocket, file_id: str):
        """WebSocket for real-time collaborative editing — requires auth."""
        await websocket.accept()
        
        # Authenticate: first message must be session_token
        import asyncio as _aio
        try:
            auth_msg = await _aio.wait_for(websocket.receive_text(), timeout=10)
            auth_data = json.loads(auth_msg)
            token = auth_data.get("session_token", auth_msg.strip())
            session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0, "user_id": 1})
            if not session_doc:
                await websocket.send_text(json.dumps({"type": "error", "message": "Auth failed"}))
                await websocket.close(code=4001)
                return
        except (_aio.TimeoutError, Exception):
            await websocket.close(code=4001)
            return
        
        # Initialize session if needed
        if file_id not in _editor_sessions:
            _editor_sessions[file_id] = {"participants": {}, "connections": []}
        
        session = _editor_sessions[file_id]
        session["connections"].append(websocket)
        participant_id = None
        
        try:
            while True:
                raw = await websocket.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")
                
                if msg_type == "join":
                    participant_id = data.get("user_id", f"anon_{uuid.uuid4().hex[:6]}")
                    name = data.get("name", "Anonymous")
                    color_idx = len(session["participants"])
                    session["participants"][participant_id] = {
                        "name": name,
                        "color": get_cursor_color(color_idx),
                        "cursor": {"line": 0, "ch": 0},
                        "selection": None,
                        "is_agent": data.get("is_agent", False),
                        "joined_at": datetime.now(timezone.utc).isoformat(),
                    }
                    # Broadcast participant list
                    await _broadcast_to_session(file_id, {
                        "type": "participants",
                        "participants": {k: {kk: vv for kk, vv in v.items() if kk != "joined_at"} 
                                        for k, v in session["participants"].items()},
                    }, exclude=None)
                    logger.info(f"Editor join: {name} → {file_id}")
                
                elif msg_type == "cursor":
                    if participant_id and participant_id in session["participants"]:
                        session["participants"][participant_id]["cursor"] = data.get("cursor", {"line": 0, "ch": 0})
                        session["participants"][participant_id]["selection"] = data.get("selection")
                        await _broadcast_to_session(file_id, {
                            "type": "cursor",
                            "user_id": participant_id,
                            "name": session["participants"][participant_id]["name"],
                            "color": session["participants"][participant_id]["color"],
                            "cursor": data.get("cursor"),
                            "selection": data.get("selection"),
                        }, exclude=websocket)
                
                elif msg_type == "edit":
                    # Broadcast edit operation to all other participants
                    await _broadcast_to_session(file_id, {
                        "type": "edit",
                        "user_id": participant_id,
                        "name": session["participants"].get(participant_id, {}).get("name", "?"),
                        "changes": data.get("changes"),
                        "content": data.get("content"),
                        "version": data.get("version"),
                    }, exclude=websocket)
                    
                    # Save to MongoDB periodically (debounced by frontend)
                    if data.get("save") and data.get("content") is not None:
                        await db.repo_files.update_one(
                            {"file_id": file_id},
                            {"$set": {
                                "content": data["content"],
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "updated_by": participant_id,
                                "version": data.get("version", 1),
                            }}
                        )
                
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"Editor WS error: {e}")
        finally:
            # Clean up
            if file_id in _editor_sessions:
                session = _editor_sessions[file_id]
                session["connections"] = [c for c in session["connections"] if c != websocket]
                if participant_id:
                    session["participants"].pop(participant_id, None)
                # Broadcast updated participant list
                if session["connections"]:
                    await _broadcast_to_session(file_id, {
                        "type": "participants",
                        "participants": {k: {kk: vv for kk, vv in v.items() if kk != "joined_at"}
                                        for k, v in session["participants"].items()},
                    }, exclude=None)
                else:
                    _editor_sessions.pop(file_id, None)

    @api_router.get("/editor/{file_id}/participants")
    async def get_editor_participants(file_id: str, request: Request):
        """Get current participants in an editor session."""
        await get_current_user(request)
        session = _editor_sessions.get(file_id, {})
        participants = session.get("participants") or {}
        return {
            "file_id": file_id,
            "active": bool(participants),
            "participants": {k: {"name": v["name"], "color": v["color"], "cursor": v["cursor"], "is_agent": v.get("is_agent", False)}
                           for k, v in participants.items()},
            "count": len(participants),
        }


async def _broadcast_to_session(file_id: str, data: dict, exclude=None):
    """Broadcast a message to all WebSocket connections in an editor session."""
    session = _editor_sessions.get(file_id, {})
    msg = json.dumps(data)
    dead = []
    for ws in session.get("connections") or []:
        if ws == exclude:
            continue
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        session["connections"] = [c for c in session.get("connections") or [] if c != ws]


async def agent_edit_file(db, file_id: str, agent_name: str, content: str, version: int = None):
    """Called by AI agents to edit a file collaboratively.
    Broadcasts the edit to all connected editor sessions."""
    # Update file in DB
    updates = {
        "content": content,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": f"ai:{agent_name}",
    }
    if version:
        updates["version"] = version
    await db.repo_files.update_one({"file_id": file_id}, {"$set": updates})
    
    # Broadcast to active editor sessions
    if file_id in _editor_sessions:
        await _broadcast_to_session(file_id, {
            "type": "edit",
            "user_id": f"ai:{agent_name}",
            "name": agent_name,
            "content": content,
            "version": version,
            "is_agent_edit": True,
        }, exclude=None)
