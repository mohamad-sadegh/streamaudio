"""Phone device WebSocket control channel."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import db
from app.control_hub import hub
from app.control_modes import normalize_mode
from app.password import verify_password

router = APIRouter(tags=["device"])
logger = logging.getLogger(__name__)

PUBLISHER_SELECT = """
    SELECT id, username, label, secret_hash, stream_path, enabled,
           desired_mode, actual_mode, device_connected,
           device_last_seen_at, device_last_error,
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
        # Some WS clients put auth in the first query param as fallback
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

    desired = normalize_mode(pub.get("desired_mode")) or "idle"
    try:
        await ws.send_text(
            json.dumps(
                {
                    "type": "desired",
                    "mode": desired,
                    "publisherId": publisher_id,
                },
                ensure_ascii=False,
            )
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
        # Only clear connected if this socket is no longer the active one
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
        row = await db.fetch_one(
            "SELECT desired_mode FROM publishers WHERE id = %s",
            (publisher_id,),
        )
        mode = normalize_mode(row["desired_mode"] if row else None) or "idle"
        await ws.send_text(
            json.dumps({"type": "desired", "mode": mode}, ensure_ascii=False)
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

    await ws.send_text(
        json.dumps({"type": "error", "error": "unknown_type"}, ensure_ascii=False)
    )


async def set_desired_mode(
    publisher_id: str, mode: str, *, push: bool = True
) -> dict[str, Any] | None:
    cleaned = normalize_mode(mode)
    if cleaned is None:
        return None
    row = await db.fetch_one(
        """
        UPDATE publishers
        SET desired_mode = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, username, label, stream_path, enabled,
                  desired_mode, actual_mode, device_connected,
                  device_last_seen_at, device_last_error,
                  created_at, updated_at
        """,
        (cleaned, publisher_id),
    )
    if not row:
        return None
    if push:
        await hub.push_desired(publisher_id, cleaned)
    return row
