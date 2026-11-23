from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from psycopg.errors import UniqueViolation

from app import db
from app.config import get_settings
from app.mediamtx import list_paths, path_online_map
from app.password import hash_password
from app.security import generate_secret, require_admin, sign_listen_token

router = APIRouter(tags=["publishers"])
logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")


class CreatePublisherBody(BaseModel):
    username: str
    label: str | None = None


class PatchPublisherBody(BaseModel):
    label: str | None = None
    enabled: bool | None = None


def public_publisher(
    row: dict[str, Any],
    secret_plain: str | None = None,
    online: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    stream_path = row["stream_path"]
    out: dict[str, Any] = {
        "id": str(row["id"]),
        "username": row["username"],
        "label": row["label"],
        "streamPath": stream_path,
        "enabled": row["enabled"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "online": online,
        "whipUrl": f"https://{settings.domain}/{stream_path}/whip",
        "whepUrl": f"https://{settings.domain}/{stream_path}/whep",
    }
    if secret_plain is not None:
        out["secret"] = secret_plain
    return out


@router.get("/api/publishers")
async def list_publishers(_admin: dict = Depends(require_admin)):
    rows = await db.fetch_all(
        """
        SELECT id, username, label, stream_path, enabled, created_at, updated_at
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
            public_publisher(r, online=bool(online.get(r["stream_path"])))
            for r in rows
        ]
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
                """
                INSERT INTO publishers (id, username, label, secret_hash, stream_path)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, username, label, stream_path, enabled, created_at, updated_at
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
        RETURNING id, username, label, stream_path, enabled, created_at, updated_at
        """,
        tuple(values),
    )
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    return {"publisher": public_publisher(row)}


@router.post("/api/publishers/{publisher_id}/rotate-secret")
async def rotate_secret(publisher_id: str, _admin: dict = Depends(require_admin)):
    secret = generate_secret(32)
    secret_hash = hash_password(secret)
    row = await db.fetch_one(
        """
        UPDATE publishers SET secret_hash = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, username, label, stream_path, enabled, created_at, updated_at
        """,
        (secret_hash, publisher_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    return {"publisher": public_publisher(row, secret)}


@router.delete("/api/publishers/{publisher_id}")
async def delete_publisher(publisher_id: str, _admin: dict = Depends(require_admin)):
    count = await db.execute("DELETE FROM publishers WHERE id = %s", (publisher_id,))
    if count == 0:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    return {"ok": True}


@router.post("/api/streams/{publisher_id}/listen-token")
async def listen_token(publisher_id: str, admin: dict = Depends(require_admin)):
    settings = get_settings()
    pub = await db.fetch_one(
        "SELECT id, stream_path, enabled FROM publishers WHERE id = %s",
        (publisher_id,),
    )
    if not pub:
        raise HTTPException(status_code=404, detail="پیدا نشد")
    if not pub["enabled"]:
        raise HTTPException(status_code=403, detail="ناشر غیرفعال است")

    token = sign_listen_token(
        publisher_id=str(pub["id"]),
        stream_path=pub["stream_path"],
        admin_id=str(admin.get("sub")),
    )
    return {
        "token": token,
        "expiresIn": settings.listen_token_ttl_seconds,
        "whepUrl": f"https://{settings.domain}/{pub['stream_path']}/whep",
        "authorization": f"Bearer __listen__:{token}",
    }
