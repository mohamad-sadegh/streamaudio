from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from psycopg.errors import UniqueViolation

from app import db
from app.password import hash_password
from app.security import require_admin

router = APIRouter(tags=["users"])

USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,31}$")
MIN_PASSWORD_LEN = 8

FIXED_ROLES = [
    {
        "id": "admin",
        "name": "Admin",
        "description": "Panel login account. Can manage publishers, users, and listen to streams.",
    },
    {
        "id": "publisher",
        "name": "Publisher",
        "description": "Device credential for WHIP publish. Not a panel login — create via Publishers.",
    },
]


class CreateUserBody(BaseModel):
    username: str
    password: str


class PatchUserBody(BaseModel):
    username: str | None = None
    password: str | None = None


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "role": "admin",
        "createdAt": row["created_at"],
    }


def _validate_username(raw: str) -> str:
    clean = raw.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="username is required")
    if not USERNAME_RE.match(clean):
        raise HTTPException(
            status_code=400,
            detail="username must be 2-32 chars: letters, digits, _, ., or -",
        )
    return clean


def _validate_password(password: str) -> str:
    if not password or len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"password must be at least {MIN_PASSWORD_LEN} characters",
        )
    return password


@router.get("/api/roles")
async def list_roles(_admin: dict = Depends(require_admin)):
    return {"roles": FIXED_ROLES}


@router.get("/api/users")
async def list_users(_admin: dict = Depends(require_admin)):
    rows = await db.fetch_all(
        """
        SELECT id, username, created_at
        FROM admins
        ORDER BY created_at ASC
        """
    )
    return {"users": [public_user(r) for r in rows]}


@router.post("/api/users", status_code=201)
async def create_user(body: CreateUserBody, _admin: dict = Depends(require_admin)):
    username = _validate_username(body.username)
    password = _validate_password(body.password)
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())

    try:
        async with db.connection() as conn:
            cur = await conn.execute(
                """
                INSERT INTO admins (id, username, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, created_at
                """,
                (user_id, username, password_hash),
            )
            row = await cur.fetchone()
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Username already exists") from None

    return {"user": public_user(row)}


@router.patch("/api/users/{user_id}")
async def patch_user(
    user_id: str,
    body: PatchUserBody,
    _admin: dict = Depends(require_admin),
):
    fields: list[str] = []
    values: list[Any] = []

    if body.username is not None:
        fields.append("username = %s")
        values.append(_validate_username(body.username))
    if body.password is not None:
        fields.append("password_hash = %s")
        values.append(hash_password(_validate_password(body.password)))

    if not fields:
        raise HTTPException(status_code=400, detail="No changes")

    values.append(user_id)

    try:
        row = await db.fetch_one(
            f"""
            UPDATE admins SET {", ".join(fields)}
            WHERE id = %s
            RETURNING id, username, created_at
            """,
            tuple(values),
        )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Username already exists") from None

    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {"user": public_user(row)}


@router.delete("/api/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if str(admin.get("sub")) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    count_row = await db.fetch_one("SELECT COUNT(*)::int AS n FROM admins")
    if count_row and count_row["n"] <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    deleted = await db.execute("DELETE FROM admins WHERE id = %s", (user_id,))
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
