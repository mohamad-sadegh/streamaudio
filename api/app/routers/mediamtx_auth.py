from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import db
from app.password import verify_password
from app.security import verify_listen_token

router = APIRouter(tags=["mediamtx"])
logger = logging.getLogger(__name__)


class MediaMtxAuthBody(BaseModel):
    user: str | None = ""
    password: str | None = ""
    token: str | None = ""
    ip: str | None = None
    action: str | None = None
    path: str | None = ""
    protocol: str | None = None
    id: str | None = None
    query: str | None = None
    userAgent: str | None = None


@router.post("/api/mediamtx/auth")
async def mediamtx_auth(body: MediaMtxAuthBody, request: Request):
    action = body.action or ""
    path = body.path or ""
    user = body.user or ""
    password = body.password or ""
    token = body.token or ""

    if not user and not password and not token:
        return JSONResponse({"error": "credentials required"}, status_code=401)

    auth_user = user
    auth_pass = password
    if not auth_user and ":" in token:
        idx = token.index(":")
        auth_user = token[:idx]
        auth_pass = token[idx + 1 :]
    elif not auth_user and token:
        auth_user = "__listen__"
        auth_pass = token

    try:
        if action == "publish":
            return await _handle_publish(path, auth_user, auth_pass)
        if action in {"read", "playback"}:
            return await _handle_read(path, auth_user, auth_pass)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    except Exception as err:  # noqa: BLE001
        logger.warning("mediamtx auth error: %s", err)
        return JSONResponse({"error": "forbidden"}, status_code=403)


async def _handle_publish(path: str, username: str, secret: str) -> Response:
    if not username or not secret or not path.startswith("live/"):
        return JSONResponse({"error": "forbidden"}, status_code=403)

    pub = await db.fetch_one(
        """
        SELECT id, secret_hash, stream_path, enabled
        FROM publishers WHERE username = %s
        """,
        (username,),
    )
    if not pub or not pub["enabled"]:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if pub["stream_path"] != path:
        return JSONResponse({"error": "path mismatch"}, status_code=403)
    if not verify_password(pub["secret_hash"], secret):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse({})


async def _handle_read(path: str, username: str, secret: str) -> Response:
    if username != "__listen__" or not secret:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    payload = verify_listen_token(secret)
    if payload.get("streamPath") != path:
        return JSONResponse({"error": "path mismatch"}, status_code=403)

    pub = await db.fetch_one(
        "SELECT enabled FROM publishers WHERE id = %s",
        (payload["publisherId"],),
    )
    if not pub or not pub["enabled"]:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    exp = payload.get("exp")
    expire_at = (
        datetime.fromtimestamp(exp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        if exp
        else None
    )
    return JSONResponse({"expireAt": expire_at} if expire_at else {})
