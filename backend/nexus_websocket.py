"""Nexus WebSocket — Connection manager with Redis Pub/Sub for cross-instance fan-out.

On a single instance, broadcasts go directly to local WebSocket connections.
When Redis is available, messages are also published to a Redis channel so that
other Cloud Run instances can relay them to their local clients.
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_PUBSUB_PREFIX = "nexus:ws:"
_INSTANCE_ID = os.environ.get("HOSTNAME", "") or os.urandom(8).hex()


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}
        self._subscriber_task: asyncio.Task | None = None
        self._pubsub = None

    async def connect(self, channel_id: str, ws: WebSocket):
        await ws.accept()
        if channel_id not in self.connections:
            self.connections[channel_id] = []
        self.connections[channel_id].append(ws)

    def disconnect(self, channel_id: str, ws: WebSocket):
        if channel_id in self.connections:
            self.connections[channel_id] = [c for c in self.connections[channel_id] if c != ws]

    async def _local_broadcast(self, channel_id: str, data: dict):
        """Send to all local WebSocket connections for a channel."""
        for ws in self.connections.get(channel_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(channel_id, ws)

    async def broadcast(self, channel_id: str, data: dict):
        """Broadcast to local clients and publish to Redis for cross-instance delivery."""
        await self._local_broadcast(channel_id, data)
        try:
            from redis_client import get_redis
            r = await get_redis()
            if r:
                envelope = json.dumps({
                    "src": _INSTANCE_ID,
                    "channel_id": channel_id,
                    "data": data,
                }, default=str)
                await r.publish(f"{_PUBSUB_PREFIX}{channel_id}", envelope)
        except Exception as e:
            logger.debug(f"Redis publish failed (local-only broadcast): {e}")

    async def start_subscriber(self):
        """Start a background task that subscribes to Redis Pub/Sub for all channels."""
        if self._subscriber_task and not self._subscriber_task.done():
            return
        self._subscriber_task = asyncio.create_task(self._subscribe_loop())

    async def _subscribe_loop(self):
        """Listen for messages from other instances via Redis Pub/Sub."""
        while True:
            try:
                from redis_client import get_redis
                r = await get_redis()
                if not r:
                    await asyncio.sleep(5)
                    continue
                self._pubsub = r.pubsub()
                await self._pubsub.psubscribe(f"{_PUBSUB_PREFIX}*")
                logger.info("WebSocket Redis Pub/Sub subscriber started")
                async for message in self._pubsub.listen():
                    if message["type"] not in ("pmessage",):
                        continue
                    try:
                        envelope = json.loads(message["data"])
                        if envelope.get("src") == _INSTANCE_ID:
                            continue
                        channel_id = envelope.get("channel_id", "")
                        data = envelope.get("data", {})
                        if channel_id and self.connections.get(channel_id):
                            await self._local_broadcast(channel_id, data)
                    except Exception as e:
                        logger.debug(f"Pub/Sub message parse error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Pub/Sub subscriber error, reconnecting in 5s: {e}")
                await asyncio.sleep(5)
            finally:
                if self._pubsub:
                    try:
                        await self._pubsub.punsubscribe()
                        await self._pubsub.close()
                    except Exception:
                        pass
                    self._pubsub = None
