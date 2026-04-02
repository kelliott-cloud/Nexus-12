"""Training Progress WebSocket — Real-time notifications during agent training.

Uses Redis-backed state (via state.py) with in-memory fallback for progress tracking.
"""
import logging
import asyncio
import json
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# In-memory fallback (also used by state.py namespace)
_training_progress = {}


async def update_training_progress_async(session_id: str, data: dict):
    """Update progress using Redis-backed state (async version)."""
    progress = {
        **data,
        "session_id": session_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _training_progress[session_id] = progress
    try:
        from state import state_set
        await state_set("training:progress", session_id, progress, ttl=3600)
    except Exception as e:
        logger.debug(f"Redis state_set failed for training progress: {e}")


def update_training_progress(session_id: str, data: dict):
    """Update progress synchronously (in-memory only, for sync callers)."""
    _training_progress[session_id] = {
        **data,
        "session_id": session_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_training_progress(session_id: str) -> dict:
    """Get current progress for a training session."""
    return _training_progress.get(session_id, {})


async def get_training_progress_async(session_id: str) -> dict:
    """Get progress from Redis-backed state (async version)."""
    # Try in-memory first (fastest)
    mem = _training_progress.get(session_id)
    if mem:
        return mem
    # Try Redis
    try:
        from state import state_get
        val = await state_get("training:progress", session_id)
        if val:
            _training_progress[session_id] = val
            return val
    except Exception as e:
        logger.debug(f"Redis state_get failed for training progress: {e}")
    return {}


def clear_training_progress(session_id: str):
    """Clear progress after training completes."""
    _training_progress.pop(session_id, None)
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            from state import state_delete
            asyncio.create_task(state_delete("training:progress", session_id))
    except Exception as _e:
        logger.debug(f"Non-critical: {_e}")


def register_training_ws_routes(app, db, get_current_user):

    @app.websocket("/api/ws/training/{session_id}")
    async def training_progress_ws(websocket: WebSocket, session_id: str):
        """WebSocket for real-time training progress updates."""
        await websocket.accept()
        try:
            last_sent = None
            while True:
                progress = await get_training_progress_async(session_id)
                if progress and progress != last_sent:
                    await websocket.send_json(progress)
                    last_sent = progress
                    if progress.get("status") in ("completed", "failed"):
                        break
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"Training WS error: {e}")
        finally:
            clear_training_progress(session_id)
