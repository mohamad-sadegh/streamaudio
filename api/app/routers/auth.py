from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app import db
from app.password import verify_password
from app.security import (
    clear_session_cookies,
    client_ip,
    generate_csrf,
    is_ip_allowed,
    require_admin,
    set_session_cookies,
    sign_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_hits: dict[str, deque[float]] = defaultdict(deque)
_LOGIN_LIMIT = 10
_LOGIN_WINDOW = 60.0


class LoginBody(BaseModel):
    username: str
    password: str


def _rate_limit_login(ip: str) -> None:
    now = time.monotonic()
    q = _login_hits[ip]
    while q and now - q[0] > _LOGIN_WINDOW:
        q.popleft()
    if len(q) >= _LOGIN_LIMIT:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    q.append(now)


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    ip = client_ip(request)
    if not is_ip_allowed(ip):
        raise HTTPException(status_code=403, detail="Login not allowed from this IP")

    _rate_limit_login(ip)

    username = body.username.strip()
    password = body.password
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    admin = await db.fetch_one(
        "SELECT id, username, password_hash FROM admins WHERE username = %s",
        (username,),
    )
    if not admin or not verify_password(admin["password_hash"], password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_token = sign_session(
        {
            "typ": "admin",
            "sub": str(admin["id"]),
            "username": admin["username"],
        }
    )
    csrf = generate_csrf()
    set_session_cookies(response, session_token, csrf)
    return {
        "ok": True,
        "username": admin["username"],
        "id": str(admin["id"]),
    }


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(admin: dict = Depends(require_admin)):
    return {"username": admin.get("username"), "id": admin.get("sub")}
