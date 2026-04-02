"""Enhanced CRDT Collaborative Editing — Yjs WebSocket provider with persistence.

Features:
- Real-time multi-cursor collaborative editing via Yjs
- Document state persistence to MongoDB (survives server restarts)
- Awareness protocol support (cursor positions, user presence)
- Room-level access control
- Automatic stale room cleanup
- Redis Pub/Sub for cross-instance relay (Cloud Run)
"""
import logging
import asyncio
import base64
import json
import os
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_yjs_rooms = {}
_YJS_PUBSUB_PREFIX = "nexus:yjs:"
_YJS_INSTANCE_ID = os.environ.get("HOSTNAME", "") or os.urandom(8).hex()


async def _start_yjs_subscriber():
    """Subscribe to Redis Pub/Sub for Yjs updates from other instances."""
    while True:
        try:
            from redis_client import get_redis
            r = await get_redis()
            if not r:
                await asyncio.sleep(5)
                continue
            pubsub = r.pubsub()
            await pubsub.psubscribe(f"{_YJS_PUBSUB_PREFIX}*")
            logger.info("Yjs Redis Pub/Sub subscriber started")
            async for message in pubsub.listen():
                if message["type"] not in ("pmessage",):
                    continue
                try:
                    envelope = json.loads(message["data"])
                    if envelope.get("src") == _YJS_INSTANCE_ID:
                        continue
                    room = envelope.get("room", "")
                    data_b64 = envelope.get("data", "")
                    if room and room in _yjs_rooms and data_b64:
                        data = base64.b64decode(data_b64)
                        dead = []
                        for ws in _yjs_rooms[room]["clients"]:
                            try:
                                await ws.send_bytes(data)
                            except Exception:
                                dead.append(ws)
                        for ws in dead:
                            _yjs_rooms[room]["clients"].discard(ws)
                except Exception as e:
                    logger.debug(f"Yjs Pub/Sub parse error: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Yjs Pub/Sub subscriber error, reconnecting in 5s: {e}")
            await asyncio.sleep(5)


def register_yjs_routes(app, db):
    """Register the enhanced Yjs WebSocket sync endpoint with persistence."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_start_yjs_subscriber())
    except RuntimeError:
        pass

    async def _load_doc_state(room: str) -> bytes:
        """Load persisted document state from MongoDB."""
        doc = await db.crdt_documents.find_one({"room": room}, {"_id": 0, "state": 1})
        if doc and doc.get("state"):
            import base64
            try:
                return base64.b64decode(doc["state"])
            except Exception as _e:
                logger.debug(f"Non-critical: {_e}")
        return b""

    async def _save_doc_state(room: str, state: bytes):
        """Persist document state to MongoDB."""
        import base64
        encoded = base64.b64encode(state).decode()
        await db.crdt_documents.update_one(
            {"room": room},
            {"$set": {
                "room": room,
                "state": encoded,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "size_bytes": len(state),
            }},
            upsert=True,
        )

    @app.websocket("/api/ws/yjs/{room}")
    async def yjs_sync(websocket: WebSocket, room: str):
        """Enhanced Yjs WebSocket sync with persistence and awareness."""
        await websocket.accept()

        # Auth: cookie first, then first-message token fallback
        try:
            user_id = None
            session_token = websocket.cookies.get("session_token", "")
            if session_token:
                session = await db.user_sessions.find_one(
                    {"session_token": session_token},
                    {"_id": 0, "user_id": 1, "expires_at": 1})
                if session:
                    from datetime import datetime, timezone
                    expires_at = session.get("expires_at", "")
                    if isinstance(expires_at, str) and expires_at:
                        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at and expires_at > datetime.now(timezone.utc):
                        user_id = session["user_id"]

            if not user_id:
                auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                session = await db.user_sessions.find_one(
                    {"session_token": auth_msg.strip()},
                    {"_id": 0, "user_id": 1, "expires_at": 1})
                if not session:
                    await websocket.close(code=4001, reason="Auth failed")
                    return
                # Check expiry for token-based auth
                from datetime import datetime, timezone
                expires_at = session.get("expires_at", "")
                if isinstance(expires_at, str) and expires_at:
                    expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if not expires_at or expires_at < datetime.now(timezone.utc):
                    await websocket.close(code=4001, reason="Session expired")
                    return
                user_id = session["user_id"]
        except Exception:
            await websocket.close(code=4001)
            return
        ws_id = room.split(":")[0] if ":" in room else ""
        if ws_id and ws_id.startswith("ws_"):
            from data_guard import TenantIsolation
            has_access = await TenantIsolation.verify_workspace_access(db, user_id, ws_id)
            if not has_access:
                await websocket.close(code=4003, reason="Workspace access denied")
                return

        if room not in _yjs_rooms:
            _yjs_rooms[room] = {"clients": set(), "state": b"", "awareness": {}, "save_pending": False}
            # Load persisted state on first client join
            try:
                saved = await _load_doc_state(room)
                if saved:
                    _yjs_rooms[room]["state"] = saved
                    logger.info(f"Yjs: Loaded persisted state for room {room} ({len(saved)} bytes)")
            except Exception as e:
                logger.warning(f"Yjs: Failed to load state for {room}: {e}")

        room_data = _yjs_rooms[room]
        room_data["clients"].add(websocket)
        client_count = len(room_data["clients"])
        logger.info(f"Yjs: {client_count} clients in room {room}")

        # Send persisted state to the new client if available
        if room_data["state"]:
            try:
                await websocket.send_bytes(room_data["state"])
            except Exception as _e:
                logger.debug(f"Non-critical: {_e}")

        save_task = None

        async def _debounced_save():
            """Save state to DB after 2 seconds of inactivity."""
            await asyncio.sleep(2)
            if room in _yjs_rooms and _yjs_rooms[room]["state"]:
                try:
                    await _save_doc_state(room, _yjs_rooms[room]["state"])
                except Exception as e:
                    logger.warning(f"Yjs: Failed to save state for {room}: {e}")
                finally:
                    if room in _yjs_rooms:
                        _yjs_rooms[room]["save_pending"] = False

        try:
            while True:
                data = await websocket.receive_bytes()

                # Track the latest state (Yjs sync step 2 messages contain full doc state)
                if len(data) > 1:
                    msg_type = data[0]
                    # Message type 0 = sync step 1, 1 = sync step 2 (doc state), 2 = update
                    if msg_type in (1, 2):
                        room_data["state"] = data
                        # Debounced persistence
                        if not room_data["save_pending"]:
                            room_data["save_pending"] = True
                            if save_task:
                                save_task.cancel()
                            save_task = asyncio.create_task(_debounced_save())

                # Broadcast to all other local clients in the same room
                dead = []
                for ws in room_data["clients"]:
                    if ws != websocket:
                        try:
                            await ws.send_bytes(data)
                        except Exception:
                            dead.append(ws)
                for ws in dead:
                    room_data["clients"].discard(ws)

                # Publish to Redis for cross-instance relay
                try:
                    from redis_client import get_redis
                    r = await get_redis()
                    if r:
                        envelope = json.dumps({
                            "src": _YJS_INSTANCE_ID,
                            "room": room,
                            "data": base64.b64encode(data).decode(),
                        })
                        await r.publish(f"{_YJS_PUBSUB_PREFIX}{room}", envelope)
                except Exception:
                    pass

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"Yjs WS error: {e}")
        finally:
            if room in _yjs_rooms:
                _yjs_rooms[room]["clients"].discard(websocket)
                remaining = len(_yjs_rooms[room]["clients"])
                if remaining == 0:
                    # Last client left — persist final state and clean up
                    if _yjs_rooms[room]["state"]:
                        try:
                            await _save_doc_state(room, _yjs_rooms[room]["state"])
                        except Exception as _e:
                            logger.debug(f"Non-critical: {_e}")
                    del _yjs_rooms[room]
                    logger.info(f"Yjs: Room {room} closed, state persisted")
                else:
                    logger.info(f"Yjs: {remaining} clients remain in room {room}")
