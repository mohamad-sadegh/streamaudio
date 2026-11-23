from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, Request, Response

from app.config import Settings, get_settings


def generate_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_csrf() -> str:
    return secrets.token_urlsafe(24)


def sign_session(payload: dict[str, Any], settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    body = {
        **payload,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=settings.session_ttl_seconds),
    }
    return jwt.encode(body, settings.jwt_secret, algorithm="HS256")


def verify_session(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def sign_listen_token(
    *,
    publisher_id: str,
    stream_path: str,
    admin_id: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    body = {
        "typ": "listen",
        "publisherId": publisher_id,
        "streamPath": stream_path,
        "adminId": admin_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=settings.listen_token_ttl_seconds),
    }
    return jwt.encode(body, settings.jwt_secret, algorithm="HS256")


def verify_listen_token(
    token: str, settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("typ") != "listen":
        raise ValueError("Invalid listen token type")
    return payload


def client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def is_ip_allowed(ip: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    allowlist = settings.ip_allowlist
    if not allowlist:
        return True
    return ip in allowlist


def set_session_cookies(
    response: Response, session_token: str, csrf: str, settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    common = {
        "path": "/",
        "secure": settings.cookie_secure,
        "samesite": "strict",
        "max_age": settings.session_ttl_seconds,
    }
    response.set_cookie(
        settings.cookie_name,
        session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        httponly=False,
        **common,
    )


def clear_session_cookies(
    response: Response, settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def require_admin(request: Request) -> dict[str, Any]:
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = verify_session(token, settings)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Unauthorized") from None

    if payload.get("typ") != "admin":
        raise HTTPException(status_code=401, detail="Unauthorized")

    method = request.method.upper()
    if method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_header = request.headers.get("x-csrf-token")
        csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
        if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
            raise HTTPException(status_code=403, detail="CSRF validation failed")

    return payload
