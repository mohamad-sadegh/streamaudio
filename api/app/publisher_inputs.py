"""Selected input slots (max 8) for multi-device publisher control."""

from __future__ import annotations

import json
from typing import Any

from app.control_modes import normalize_mode

MAX_INPUTS = 8


def parse_selected_inputs(raw: Any) -> list[dict[str, Any]]:
    """Normalize DB JSON / list into [{slot, deviceId, label, desiredMode}]."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    used_slots: set[int] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            slot = int(item.get("slot"))
            device_id = int(item.get("deviceId"))
        except (TypeError, ValueError):
            continue
        if slot < 0 or slot >= MAX_INPUTS or slot in used_slots:
            continue
        mode = normalize_mode(str(item.get("desiredMode") or "idle")) or "idle"
        label = str(item.get("label") or "").strip()[:120]
        used_slots.add(slot)
        out.append(
            {
                "slot": slot,
                "deviceId": device_id,
                "label": label,
                "desiredMode": mode,
            }
        )
        if len(out) >= MAX_INPUTS:
            break
    out.sort(key=lambda x: x["slot"])
    return out


def validate_selected_inputs(items: list[Any]) -> list[dict[str, Any]]:
    """Validate admin PUT body; assigns slots 0..n-1 if missing."""
    if not isinstance(items, list):
        raise ValueError("inputs must be a list")
    if len(items) > MAX_INPUTS:
        raise ValueError(f"maximum {MAX_INPUTS} inputs")

    out: list[dict[str, Any]] = []
    used_slots: set[int] = set()
    used_devices: set[int] = set()

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("each input must be an object")
        try:
            device_id = int(item.get("deviceId"))
        except (TypeError, ValueError) as err:
            raise ValueError("deviceId required") from err
        if device_id in used_devices:
            raise ValueError("duplicate deviceId")
        used_devices.add(device_id)

        if "slot" in item and item.get("slot") is not None:
            try:
                slot = int(item["slot"])
            except (TypeError, ValueError) as err:
                raise ValueError("invalid slot") from err
        else:
            slot = index
        if slot < 0 or slot >= MAX_INPUTS:
            raise ValueError("slot out of range")
        if slot in used_slots:
            raise ValueError("duplicate slot")
        used_slots.add(slot)

        mode = normalize_mode(str(item.get("desiredMode") or "idle")) or "idle"
        label = str(item.get("label") or "").strip()[:120]
        out.append(
            {
                "slot": slot,
                "deviceId": device_id,
                "label": label,
                "desiredMode": mode,
            }
        )

    out.sort(key=lambda x: x["slot"])
    return out


def rollup_mode(inputs: list[dict[str, Any]], key: str = "desiredMode") -> str:
    modes = [normalize_mode(str(i.get(key) or "")) or "idle" for i in inputs]
    if any(m == "streaming" for m in modes):
        return "streaming"
    if any(m == "recording" for m in modes):
        return "recording"
    return "idle"


def slot_stream_path(base_path: str, slot: int) -> str:
    return f"{base_path.rstrip('/')}/s{int(slot)}"


def match_publisher_path(base_path: str, request_path: str) -> int | None:
    """
    Return slot index if request_path is base or base/sN.
    Legacy exact base path maps to slot None (treated as legacy).
    For slot paths returns 0..7; for exact base returns -1.
    """
    base = (base_path or "").rstrip("/")
    path = (request_path or "").rstrip("/")
    if not base or not path:
        return None
    if path == base:
        return -1
    prefix = base + "/s"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest.isdigit():
        return None
    slot = int(rest)
    if slot < 0 or slot >= MAX_INPUTS:
        return None
    return slot


def desired_inputs_wire(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "slot": item["slot"],
            "deviceId": item["deviceId"],
            "desiredMode": item["desiredMode"],
            "label": item.get("label") or "",
        }
        for item in selected
    ]


def selected_inputs_json(selected: list[dict[str, Any]]) -> str:
    return json.dumps(selected, ensure_ascii=False)
