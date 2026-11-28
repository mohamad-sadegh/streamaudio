from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation

from app import db
from app.config import get_settings
from app.control_modes import normalize_mode
from app.control_hub import hub
from app.device_state import device_state
from app.mediamtx import list_paths, path_online_map
from app.password import hash_password
from app.publisher_inputs import (
    MAX_INPUTS,
    parse_selected_inputs,
    slot_stream_path,
    validate_selected_inputs,
)
from app.routers.device import set_desired_mode, set_selected_inputs, set_slot_desired_mode
from app.security import generate_secret, require_admin, sign_listen_token

router = APIRouter(tags=["publishers"])
logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")

PUBLISHER_COLUMNS = """
    id, username, label, stream_path, enabled,
    desired_mode, actual_mode, device_connected,
    device_last_seen_at, device_last_error, selected_inputs,
    available_inputs,
    created_at, updated_at
"""


class CreatePublisherBody(BaseModel):
    username: str
    label: str | None = None


class PatchPublisherBody(BaseModel):
    label: str | None = None
    enabled: bool | None = None


class DesiredModeBody(BaseModel):
    mode: str


class SelectedInputBody(BaseModel):
    deviceId: int
    label: str | None = None
    slot: int | None = None
    desiredMode: str | None = None


class SetInputsBody(BaseModel):
    inputs: list[SelectedInputBody] = Field(default_factory=list)


class ListenTokenBody(BaseModel):
    slot: int | None = None


def _any_slot_online(stream_path: str, online: dict[str, bool]) -> bool:
    if online.get(stream_path):
        return True
    prefix = stream_path.rstrip("/") + "/s"
    return any(
        name.startswith(prefix) and online.get(name)
        for name in online
    )


def public_publisher(
    row: dict[str, Any],
    secret_plain: str | None = None,
    online: bool = False,
    *,
    include_detail: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    stream_path = row["stream_path"]
    selected = parse_selected_inputs(row.get("selected_inputs"))
    out: dict[str, Any] = {
        "id": str(row["id"]),
        "username": row["username"],
        "label": row["label"],
        "streamPath": stream_path,
        "enabled": row["enabled"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "online": online,
        "desiredMode": normalize_mode(row.get("desired_mode")) or "idle",
        "actualMode": normalize_mode(row.get("actual_mode")) or "idle",
        "deviceConnected": bool(row.get("device_connected")),
        "deviceLastError": row.get("device_last_error"),
        "deviceLastSeenAt": row.get("device_last_seen_at"),
        "selectedInputs": selected,
        "whipUrl": f"https://{settings.domain}/{stream_path}/whip",
        "whepUrl": f"https://{settings.domain}/{stream_path}/whep",
        "maxInputs": MAX_INPUTS,
    }
    if secret_plain is not None:
        out["secret"] = secret_plain
    if include_detail:
        pub_id = str(row["id"])
        live_available = device_state.get_available(pub_id)
        if live_available:
            out["availableInputs"] = live_available
        else:
            raw_available = row.get("available_inputs")
            if isinstance(raw_available, list):
                out["availableInputs"] = raw_available
            elif isinstance(raw_available, str):
                try:
                    parsed = json.loads(raw_available)
                    out["availableInputs"] = parsed if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    out["availableInputs"] = []
            else:
                out["availableInputs"] = []
        out["actualInputs"] = device_state.get_actual(pub_id)
        out["telemetry"] = device_state.get_telemetry(pub_id)
        out["slotPaths"] = {
            str(item["slot"]): slot_stream_path(stream_path, item["slot"])
            for item in selected
        }
    return out


@router.get("/api/publishers")
async def list_publishers(_admin: dict = Depends(require_admin)):
    rows = await db.fetch_all(
        f"""
        SELECT {PUBLISHER_COLUMNS}
        FROM publishers
        ORDER BY created_at DESC
        """
    )
    online: dict[str, bool] = {}
    try:
        online = path_online_map(await list_paths())
    except Exception as err:  # noqa: BLE001
        logger.warning("MediaMTX path list failed: %s", err)

    return {
        "publishers": [
            public_publisher(
                r,
                online=_any_slot_online(r["stream_path"], online),
            )
            for r in rows
        ]
    }


@router.get("/api/publishers/{publisher_id}")
async def get_publisher(publisher_id: str, _admin: dict = Depends(require_admin)):
    row = await db.fetch_one(
        f"SELECT {PUBLISHER_COLUMNS} FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")

    online: dict[str, bool] = {}
    try:
        online = path_online_map(await list_paths())
    except Exception as err:  # noqa: BLE001
        logger.warning("MediaMTX path list failed: %s", err)

    return {
        "publisher": public_publisher(
            row,
            online=_any_slot_online(row["stream_path"], online),
            include_detail=True,
        )
    }


@router.post("/api/publishers", status_code=201)
async def create_publisher(
    body: CreatePublisherBody, _admin: dict = Depends(require_admin)
):
    clean_user = body.username.strip().lower()
    if not clean_user:
        raise HTTPException(status_code=400, detail="نام کاربری الزامی است")
    if not USERNAME_RE.match(clean_user):
        raise HTTPException(
            status_code=400,
            detail="نام کاربری باید ۲ تا ۳۲ کاراکتر باشد: حروف کوچک، رقم، _ یا -",
        )

    pub_id = str(uuid.uuid4())
    stream_path = f"live/{pub_id}"
    secret = generate_secret(32)
    secret_hash = hash_password(secret)
    label_text = (body.label or "").strip()[:120]

    try:
        async with db.connection() as conn:
            cur = await conn.execute(
                f"""
                INSERT INTO publishers (id, username, label, secret_hash, stream_path)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING {PUBLISHER_COLUMNS}
                """,
                (pub_id, clean_user, label_text, secret_hash, stream_path),
            )
            row = await cur.fetchone()
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="این نام کاربری از قبل وجود دارد") from None

    return {"publisher": public_publisher(row, secret, False)}


@router.patch("/api/publishers/{publisher_id}")
async def patch_publisher(
    publisher_id: str,
    body: PatchPublisherBody,
    _admin: dict = Depends(require_admin),
):
    fields: list[str] = []
    values: list[Any] = []

    if body.label is not None:
        fields.append("label = %s")
        values.append(body.label.strip()[:120])
    if body.enabled is not None:
        fields.append("enabled = %s")
        values.append(body.enabled)

    if not fields:
        raise HTTPException(status_code=400, detail="تغییری نیست")

    fields.append("updated_at = NOW()")
    values.append(publisher_id)

    row = await db.fetch_one(
        f"""
        UPDATE publishers SET {", ".join(fields)}
        WHERE id = %s
        RETURNING {PUBLISHER_COLUMNS}
        """,
        tuple(values),
    )
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    if body.enabled is False:
        await set_desired_mode(publisher_id, "idle", push=True)
        refreshed = await db.fetch_one(
            f"SELECT {PUBLISHER_COLUMNS} FROM publishers WHERE id = %s",
            (publisher_id,),
        )
        if refreshed:
            row = refreshed
    return {"publisher": public_publisher(row)}


@router.put("/api/publishers/{publisher_id}/inputs")
async def put_publisher_inputs(
    publisher_id: str,
    body: SetInputsBody,
    _admin: dict = Depends(require_admin),
):
    existing = await db.fetch_one(
        f"SELECT {PUBLISHER_COLUMNS} FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    try:
        payload = []
        for item in body.inputs:
            entry = item.model_dump()
            # Treat omitted desiredMode as "keep previous" via None
            if "desiredMode" not in item.model_fields_set:
                entry["desiredMode"] = None
            payload.append(entry)
        selected = validate_selected_inputs(
            [
                {
                    **entry,
                    "desiredMode": entry["desiredMode"]
                    if entry.get("desiredMode") is not None
                    else "idle",
                }
                for entry in payload
            ]
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    prev_by_device = {
        item["deviceId"]: item["desiredMode"]
        for item in parse_selected_inputs(existing.get("selected_inputs"))
    }
    for item, raw in zip(selected, payload):
        if raw.get("desiredMode") is None and item["deviceId"] in prev_by_device:
            item["desiredMode"] = prev_by_device[item["deviceId"]]

    row = await set_selected_inputs(publisher_id, selected, push=True)
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    return {
        "publisher": public_publisher(row, include_detail=True),
    }


@router.post("/api/publishers/{publisher_id}/inputs/{slot}/desired-mode")
async def set_input_desired_mode(
    publisher_id: str,
    slot: int,
    body: DesiredModeBody,
    _admin: dict = Depends(require_admin),
):
    if slot < 0 or slot >= MAX_INPUTS:
        raise HTTPException(status_code=400, detail="اسلات نامعتبر است")
    mode = normalize_mode(body.mode)
    if mode is None:
        raise HTTPException(
            status_code=400,
            detail="حالت نامعتبر است — idle، streaming یا recording",
        )
    existing = await db.fetch_one(
        f"SELECT {PUBLISHER_COLUMNS} FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    if mode != "idle" and not existing["enabled"]:
        raise HTTPException(status_code=403, detail="ناشر غیرفعال است")
    row = await set_slot_desired_mode(publisher_id, slot, mode, push=True)
    if not row:
        raise HTTPException(status_code=404, detail="ورودی انتخاب‌شده پیدا نشد")
    return {"publisher": public_publisher(row, include_detail=True)}


@router.post("/api/publishers/{publisher_id}/desired-mode")
async def set_publisher_desired_mode(
    publisher_id: str,
    body: DesiredModeBody,
    _admin: dict = Depends(require_admin),
):
    mode = normalize_mode(body.mode)
    if mode is None:
        raise HTTPException(
            status_code=400,
            detail="حالت نامعتبر است — idle، streaming یا recording",
        )
    existing = await db.fetch_one(
        f"SELECT {PUBLISHER_COLUMNS} FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    if mode != "idle" and not existing["enabled"]:
        raise HTTPException(status_code=403, detail="ناشر غیرفعال است")
    row = await set_desired_mode(publisher_id, mode, push=True)
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    return {"publisher": public_publisher(row, include_detail=True)}


@router.post("/api/publishers/{publisher_id}/rotate-secret")
async def rotate_secret(publisher_id: str, _admin: dict = Depends(require_admin)):
    secret = generate_secret(32)
    secret_hash = hash_password(secret)
    existing = await db.fetch_one(
        f"SELECT {PUBLISHER_COLUMNS} FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="پیدا نشد")

    # Keep channel selection across re-pair; only force idle modes
    preserved = parse_selected_inputs(existing.get("selected_inputs"))
    for item in preserved:
        item["desiredMode"] = "idle"

    row = await db.fetch_one(
        f"""
        UPDATE publishers SET secret_hash = %s, updated_at = NOW(),
          desired_mode = 'idle',
          selected_inputs = %s::jsonb,
          device_connected = FALSE
        WHERE id = %s
        RETURNING {PUBLISHER_COLUMNS}
        """,
        (
            secret_hash,
            json.dumps(preserved, ensure_ascii=False),
            publisher_id,
        ),
    )
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    # Drop live telemetry/actual; available_inputs stay in DB for the panel
    device_state.clear(publisher_id)
    await hub.push_desired(publisher_id, "idle")
    await hub.push_desired_inputs(publisher_id, preserved)
    return {"publisher": public_publisher(row, secret, include_detail=True)}


@router.delete("/api/publishers/{publisher_id}")
async def delete_publisher(publisher_id: str, _admin: dict = Depends(require_admin)):
    count = await db.execute("DELETE FROM publishers WHERE id = %s", (publisher_id,))
    if count == 0:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    device_state.clear(publisher_id)
    return {"ok": True}


@router.post("/api/streams/{publisher_id}/listen-token")
async def listen_token(
    publisher_id: str,
    admin: dict = Depends(require_admin),
    body: ListenTokenBody = ListenTokenBody(),
):
    settings = get_settings()
    pub = await db.fetch_one(
        "SELECT id, stream_path, enabled, selected_inputs FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not pub:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    if not pub["enabled"]:
        raise HTTPException(status_code=403, detail="ناشر غیرفعال است")

    slot = body.slot
    if slot is not None:
        if slot < 0 or slot >= MAX_INPUTS:
            raise HTTPException(status_code=400, detail="اسلات نامعتبر است")
        selected = parse_selected_inputs(pub.get("selected_inputs"))
        if not any(item["slot"] == slot for item in selected):
            raise HTTPException(status_code=404, detail="اسلات در ورودی‌های انتخاب‌شده نیست")
        stream_path = slot_stream_path(pub["stream_path"], slot)
    else:
        # Prefer first selected slot if present; else legacy base path
        selected = parse_selected_inputs(pub.get("selected_inputs"))
        if selected:
            stream_path = slot_stream_path(pub["stream_path"], selected[0]["slot"])
            slot = selected[0]["slot"]
        else:
            stream_path = pub["stream_path"]

    token = sign_listen_token(
        publisher_id=str(pub["id"]),
        stream_path=stream_path,
        admin_id=str(admin.get("sub")),
    )
    return {
        "token": token,
        "expiresIn": settings.listen_token_ttl_seconds,
        "slot": slot,
        "streamPath": stream_path,
        "whepUrl": f"https://{settings.domain}/{stream_path}/whep",
        "authorization": f"Bearer __listen__:{token}",
    }
