import asyncio
import logging
from contextlib import suppress
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from homelab_monitor.realtime.events import build_event

logger = logging.getLogger("homelab_monitor.realtime")

HEARTBEAT_INTERVAL_SECONDS = 20


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients[client_id] = websocket
        await websocket.send_json(build_event("connection", reason="connected", status="connected"))

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            websocket = self._clients.pop(client_id, None)
        if websocket is None:
            return
        if websocket.client_state == WebSocketState.CONNECTED:
            with suppress(WebSocketDisconnect, RuntimeError, OSError):
                await websocket.close()

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients.items())
        stale: list[str] = []
        for client_id, websocket in clients:
            try:
                await websocket.send_json(message)
            except Exception:
                logger.debug("realtime_broadcast_failed", extra={"client_id": client_id})
                stale.append(client_id)
        for client_id in stale:
            await self.disconnect(client_id)

    async def heartbeat(self) -> None:
        await self.broadcast(build_event("connection", reason="heartbeat", status="heartbeat"))

    @property
    def client_count(self) -> int:
        return len(self._clients)
