"""Nexus WebSocket — Connection manager for real-time channel updates.
Extracted from server.py for modularity.
"""
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, channel_id: str, ws: WebSocket):
        await ws.accept()
        if channel_id not in self.connections:
            self.connections[channel_id] = []
        self.connections[channel_id].append(ws)

    def disconnect(self, channel_id: str, ws: WebSocket):
        if channel_id in self.connections:
            self.connections[channel_id] = [c for c in self.connections[channel_id] if c != ws]

    async def broadcast(self, channel_id: str, data: dict):
        for ws in self.connections.get(channel_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(channel_id, ws)
