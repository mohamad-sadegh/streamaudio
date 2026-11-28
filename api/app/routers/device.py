"""Phone device WebSocket control channel."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import db
from app.control_hub import hub
from app.control_modes import normalize_mode
from app.device_state import device_state
from app.password import verify_password
from app.publisher_inputs import (
    parse_selected_inputs,
    rollup_mode,
    selected_inputs_json,
)

router = APIRouter(tags=["device"])
logger = logging.getLogger(__name__)

PUBLISHER_SELECT = """
    SELECT id, username, label, secret_hash, stream_path, enabled,
           desired_mode, actual_mode, device_connected,
           device_last_seen_at, device_last_error, selected_inputs,
           available_inputs,
           created_at, updated_at
    FROM publishers
"""


def _parse_bearer(header: str | None) -> tuple[str, str] | None:
    if not header:
        return None
    raw = header.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    if ":" not in raw:
        return None
    user, secret = raw.split(":", 1)
    user = user.strip()
    secret = secret.strip()
    if not user or not secret:
        return None
    return user, secret


async def _authenticate_publisher(ws: WebSocket) -> dict[str, Any] | None:
    creds = _parse_bearer(ws.headers.get("authorization"))
    if creds is None:
        token = ws.query_params.get("token") or ""
        if ":" in token:
            user, secret = token.split(":", 1)
            creds = (user.strip(), secret.strip()) if user.strip() and secret.strip() else None
    if creds is None:
        await ws.close(code=4401)
        return None

    username, secret = creds
    pub = await db.fetch_one(
        PUBLISHER_SELECT + " WHERE username = %s",
        (username,),
    )
    if not pub or not pub["enabled"]:
        await ws.close(code=4403)
        return None
    if not verify_password(pub["secret_hash"], secret):
        await ws.close(code=4403)
        return None
    return pub


async def _send_desired_bundle(ws: WebSocket, publisher_id: str) -> None:
    row = await db.fetch_one(
        "SELECT desired_mode, selected_inputs FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    mode = normalize_mode(row["desired_mode"] if row else None) or "idle"
    selected = parse_selected_inputs(row.get("selected_inputs") if row else None)
    await ws.send_text(
        json.dumps(
            {
                "type": "desired",
                "mode": mode,
                "publisherId": publisher_id,
            },
            ensure_ascii=False,
        )
    )
    await ws.send_text(
        json.dumps(
            {
                "type": "desired_inputs",
                "inputs": [
                    {
                        "slot": i["slot"],
                        "deviceId": i["deviceId"],
                        "desiredMode": i["desiredMode"],
                        "label": i.get("label") or "",
                    }
                    for i in selected
                ],
            },
            ensure_ascii=False,
        )
    )


@router.websocket("/api/device/ws")
async def device_ws(ws: WebSocket) -> None:
    await ws.accept()
    pub = await _authenticate_publisher(ws)
    if pub is None:
        return

    publisher_id = str(pub["id"])
    await hub.connect(publisher_id, ws)
    await db.execute(
        """
        UPDATE publishers
        SET device_connected = TRUE,
            device_last_seen_at = NOW(),
            device_last_error = NULL
        WHERE id = %s
        """,
        (publisher_id,),
    )
    # Warm in-memory cache from DB so the admin panel has inputs immediately
    cached_available = pub.get("available_inputs")
    if isinstance(cached_available, list) and cached_available:
        device_state.set_available(publisher_id, cached_available)
    elif isinstance(cached_available, str):
        try:
            parsed = json.loads(cached_available)
            if isinstance(parsed, list) and parsed:
                device_state.set_available(publisher_id, parsed)
        except json.JSONDecodeError:
            pass

    try:
        await _send_desired_bundle(ws, publisher_id)
        await ws.send_text(
            json.dumps({"type": "request_inventory"}, ensure_ascii=False)
        )

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(
                    json.dumps({"type": "error", "error": "invalid_json"}, ensure_ascii=False)
                )
                continue
            await _handle_device_message(ws, publisher_id, msg)
    except WebSocketDisconnect:
        logger.info("Device disconnected publisher=%s", publisher_id)
    except Exception as err:  # noqa: BLE001
        logger.warning("Device WS error publisher=%s: %s", publisher_id, err)
    finally:
        await hub.disconnect(publisher_id, ws)
        if not hub.is_connected(publisher_id):
            await db.execute(
                """
                UPDATE publishers
                SET device_connected = FALSE,
                    device_last_seen_at = NOW()
                WHERE id = %s
                """,
                (publisher_id,),
            )


async def _handle_device_message(
    ws: WebSocket, publisher_id: str, msg: dict[str, Any]
) -> None:
    msg_type = str(msg.get("type") or "").strip().lower()

    if msg_type == "ping":
        await db.execute(
            """
            UPDATE publishers
            SET device_last_seen_at = NOW(), device_connected = TRUE
            WHERE id = %s
            """,
            (publisher_id,),
        )
        await ws.send_text(json.dumps({"type": "pong"}, ensure_ascii=False))
        return

    if msg_type == "hello":
        await db.execute(
            """
            UPDATE publishers
            SET device_last_seen_at = NOW(), device_connected = TRUE
            WHERE id = %s
            """,
            (publisher_id,),
        )
        await _send_desired_bundle(ws, publisher_id)
        await ws.send_text(
            json.dumps({"type": "request_inventory"}, ensure_ascii=False)
        )
        return

    if msg_type == "set_desired":
        mode = normalize_mode(str(msg.get("mode") or ""))
        if mode is None:
            await ws.send_text(
                json.dumps({"type": "error", "error": "invalid_mode"}, ensure_ascii=False)
            )
            return
        await set_desired_mode(publisher_id, mode, push=False)
        await ws.send_text(
            json.dumps({"type": "desired", "mode": mode}, ensure_ascii=False)
        )
        return

    if msg_type == "actual":
        mode = normalize_mode(str(msg.get("mode") or ""))
        if mode is None:
            await ws.send_text(
                json.dumps({"type": "error", "error": "invalid_mode"}, ensure_ascii=False)
            )
            return
        error = msg.get("error")
        error_text = None
        if error is not None:
            error_text = str(error).strip()[:500] or None
        await db.execute(
            """
            UPDATE publishers
            SET actual_mode = %s,
                device_last_error = %s,
                device_last_seen_at = NOW(),
                device_connected = TRUE
            WHERE id = %s
            """,
            (mode, error_text, publisher_id),
        )
        return

    if msg_type == "available_inputs":
        devices = msg.get("devices")
        if not isinstance(devices, list):
            await ws.send_text(
                json.dumps({"type": "error", "error": "invalid_devices"}, ensure_ascii=False)
            )
            return
        device_state.set_available(publisher_id, devices)
        cleaned = device_state.get_available(publisher_id)
        await db.execute(
            """
            UPDATE publishers
            SET available_inputs = %s::jsonb,
                device_last_seen_at = NOW(),
                device_connected = TRUE
            WHERE id = %s
            """,
            (json.dumps(cleaned, ensure_ascii=False), publisher_id),
        )
        return

    if msg_type == "actual_inputs":
        inputs = msg.get("inputs")
        if not isinstance(inputs, list):
            await ws.send_text(
                json.dumps({"type": "error", "error": "invalid_inputs"}, ensure_ascii=False)
            )
            return
        device_state.set_actual(publisher_id, inputs)
        actual_list = device_state.get_actual(publisher_id)
        rolled = rollup_mode(
            [{"desiredMode": i.get("mode")} for i in actual_list],
            key="desiredMode",
        )
        errors = [i.get("error") for i in actual_list if i.get("error")]
        error_text = errors[0] if errors else None
        await db.execute(
            """
            UPDATE publishers
            SET actual_mode = %s,
                device_last_error = %s,
                device_last_seen_at = NOW(),
                device_connected = TRUE
            WHERE id = %s
            """,
            (rolled, error_text, publisher_id),
        )
        return

    if msg_type == "telemetry":
        device_state.add_telemetry(publisher_id, msg)
        await db.execute(
            """
            UPDATE publishers
            SET device_last_seen_at = NOW(), device_connected = TRUE
            WHERE id = %s
            """,
            (publisher_id,),
        )
        return

    await ws.send_text(
        json.dumps({"type": "error", "error": "unknown_type"}, ensure_ascii=False)
    )


async def set_desired_mode(
    publisher_id: str, mode: str, *, push: bool = True
) -> dict[str, Any] | None:
    """Legacy global mode: apply mode to every selected input (or idle clears all)."""
    cleaned = normalize_mode(mode)
    if cleaned is None:
        return None

    row = await db.fetch_one(
        "SELECT selected_inputs FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not row:
        return None

    selected = parse_selected_inputs(row.get("selected_inputs"))
    if selected:
        for item in selected:
            item["desiredMode"] = cleaned
    else:
        # No inputs selected: still store rollup for list UI
        pass

    updated = await db.fetch_one(
        """
        UPDATE publishers
        SET desired_mode = %s,
            selected_inputs = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, username, label, stream_path, enabled,
                  desired_mode, actual_mode, device_connected,
                  device_last_seen_at, device_last_error, selected_inputs,
                  available_inputs,
                  created_at, updated_at
        """,
        (cleaned, selected_inputs_json(selected), publisher_id),
    )
    if not updated:
        return None
    if push:
        await hub.push_desired_inputs(publisher_id, selected)
        await hub.push_desired(publisher_id, cleaned)
    return updated


async def set_selected_inputs(
    publisher_id: str,
    selected: list[dict[str, Any]],
    *,
    push: bool = True,
) -> dict[str, Any] | None:
    rolled = rollup_mode(selected)
    updated = await db.fetch_one(
        """
        UPDATE publishers
        SET selected_inputs = %s::jsonb,
            desired_mode = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, username, label, stream_path, enabled,
                  desired_mode, actual_mode, device_connected,
                  device_last_seen_at, device_last_error, selected_inputs,
                  available_inputs,
                  created_at, updated_at
        """,
        (selected_inputs_json(selected), rolled, publisher_id),
    )
    if not updated:
        return None
    if push:
        # desired_inputs first so phones apply slots before seeing rollup desired
        await hub.push_desired_inputs(publisher_id, selected)
        await hub.push_desired(publisher_id, rolled)
    return updated


async def set_slot_desired_mode(
    publisher_id: str, slot: int, mode: str, *, push: bool = True
) -> dict[str, Any] | None:
    cleaned = normalize_mode(mode)
    if cleaned is None:
        return None
    row = await db.fetch_one(
        "SELECT selected_inputs FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not row:
        return None
    selected = parse_selected_inputs(row.get("selected_inputs"))
    found = False
    for item in selected:
        if item["slot"] == slot:
            item["desiredMode"] = cleaned
            found = True
            break
    if not found:
        return None
    return await set_selected_inputs(publisher_id, selected, push=push)
