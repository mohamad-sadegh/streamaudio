"""In-memory available inputs, actual inputs, and telemetry for publishers."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

TELEMETRY_MAX = 120


class DeviceStateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._available: dict[str, list[dict[str, Any]]] = {}
        self._actual: dict[str, list[dict[str, Any]]] = {}
        self._telemetry: dict[str, deque[dict[str, Any]]] = {}

    def set_available(self, publisher_id: str, devices: list[dict[str, Any]]) -> None:
        cleaned: list[dict[str, Any]] = []
        for item in devices:
            if not isinstance(item, dict):
                continue
            try:
                device_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            cleaned.append(
                {
                    "id": device_id,
                    "label": str(item.get("label") or "").strip()[:120],
                    "type": int(item.get("type") or 0),
                }
            )
        with self._lock:
            self._available[publisher_id] = cleaned

    def get_available(self, publisher_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._available.get(publisher_id) or [])

    def set_actual(self, publisher_id: str, inputs: list[dict[str, Any]]) -> None:
        cleaned: list[dict[str, Any]] = []
        for item in inputs:
            if not isinstance(item, dict):
                continue
            try:
                slot = int(item.get("slot"))
                device_id = int(item.get("deviceId"))
            except (TypeError, ValueError):
                continue
            mode = str(item.get("mode") or "idle").strip().lower()
            error = item.get("error")
            error_text = None
            if error is not None:
                error_text = str(error).strip()[:500] or None
            cleaned.append(
                {
                    "slot": slot,
                    "deviceId": device_id,
                    "mode": mode,
                    "error": error_text,
                }
            )
        with self._lock:
            self._actual[publisher_id] = cleaned

    def get_actual(self, publisher_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._actual.get(publisher_id) or [])

    def clear(self, publisher_id: str) -> None:
        with self._lock:
            self._available.pop(publisher_id, None)
            self._actual.pop(publisher_id, None)
            self._telemetry.pop(publisher_id, None)

    def add_telemetry(self, publisher_id: str, sample: dict[str, Any]) -> None:
        point = {
            "slot": int(sample.get("slot", 0)),
            "bitrateKbps": float(sample.get("bitrateKbps") or 0),
            "rttMs": float(sample.get("rttMs") or 0),
            "packetsLost": int(sample.get("packetsLost") or 0),
            "bytesSent": int(sample.get("bytesSent") or 0),
            "ts": float(sample.get("ts") or time.time() * 1000),
        }
        with self._lock:
            buf = self._telemetry.get(publisher_id)
            if buf is None:
                buf = deque(maxlen=TELEMETRY_MAX)
                self._telemetry[publisher_id] = buf
            buf.append(point)

    def get_telemetry(self, publisher_id: str) -> list[dict[str, Any]]:
        with self._lock:
            buf = self._telemetry.get(publisher_id)
            if not buf:
                return []
            return list(buf)


device_state = DeviceStateStore()
