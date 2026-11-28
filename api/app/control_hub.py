"""In-memory WebSocket hub for paired publisher phones."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ControlHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sockets: dict[str, WebSocket] = {}

    async def connect(self, publisher_id: str, ws: WebSocket) -> None:
        async with self._lock:
            previous = self._sockets.get(publisher_id)
            self._sockets[publisher_id] = ws
        if previous is not None and previous is not ws:
            try:
                await previous.close(code=4000)
            except Exception:  # noqa: BLE001
                logger.debug("Failed closing previous device socket for %s", publisher_id)

    async def disconnect(self, publisher_id: str, ws: WebSocket) -> None:
        async with self._lock:
            current = self._sockets.get(publisher_id)
            if current is ws:
                self._sockets.pop(publisher_id, None)

    def is_connected(self, publisher_id: str) -> bool:
        return publisher_id in self._sockets

    async def send_json(self, publisher_id: str, payload: dict[str, Any]) -> bool:
        async with self._lock:
            ws = self._sockets.get(publisher_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as err:  # noqa: BLE001
            logger.warning("Device send failed for %s: %s", publisher_id, err)
            async with self._lock:
                if self._sockets.get(publisher_id) is ws:
                    self._sockets.pop(publisher_id, None)
            return False

    async def push_desired(self, publisher_id: str, mode: str) -> bool:
        return await self.send_json(
            publisher_id,
            {"type": "desired", "mode": mode},
        )


hub = ControlHub()
