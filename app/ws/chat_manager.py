"""In-process WebSocket connection registry for order chats."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("ridercards.chat")


class ChatManager:
    """Tracks websocket connections per chat and broadcasts JSON payloads."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._admin_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, chat_id: int, websocket: WebSocket, is_admin: bool = False) -> None:
        async with self._lock:
            self._connections[chat_id].add(websocket)
            if is_admin:
                self._admin_connections.add(websocket)

    async def disconnect(self, chat_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.get(chat_id, set()).discard(websocket)
            self._admin_connections.discard(websocket)
            if chat_id in self._connections and not self._connections[chat_id]:
                self._connections.pop(chat_id, None)

    async def broadcast(self, chat_id: int, payload: dict[str, Any]) -> None:
        targets = set(self._connections.get(chat_id, set())) | set(self._admin_connections)
        if not targets:
            return
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - a broken socket must not stop the broadcast
                dead.append(ws)
        for ws in dead:
            await self.disconnect(chat_id, ws)

    async def broadcast_global(self, payload: dict[str, Any]) -> None:
        """Notify admin sockets (e.g. new unread counter updates)."""
        dead: list[WebSocket] = []
        for ws in set(self._admin_connections):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self._admin_connections.discard(ws)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())

    def is_tracking(self, chat_id: int) -> bool:
        return bool(self._connections.get(chat_id))


chat_manager = ChatManager()
