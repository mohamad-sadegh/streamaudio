from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings
from app.password import hash_password

logger = logging.getLogger(__name__)

pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    global pool
    settings = get_settings()
    logger.info("Connecting to Postgres at %s", settings.db_target)
    conninfo = make_conninfo(**settings.psycopg_kwargs())
    pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=10,
        kwargs={
            "row_factory": dict_row,
            "autocommit": True,
        },
        open=False,
        timeout=10,
    )
    await pool.open(wait=True, timeout=60)
    return pool


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> AsyncConnectionPool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    return pool


async def wait_for_db(attempts: int = 30, delay_s: float = 2.0) -> None:
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            async with get_pool().connection() as conn:
                await conn.execute("SELECT 1")
            logger.info("Connected to Postgres")
            return
        except Exception as err:  # noqa: BLE001
            last_err = err
            logger.warning(
                "Postgres not ready (attempt %s/%s): %s", i, attempts, err
            )
            await asyncio.sleep(delay_s)
    assert last_err is not None
    raise last_err


async def migrate() -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
              id UUID PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS publishers (
              id UUID PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              label TEXT NOT NULL DEFAULT '',
              secret_hash TEXT NOT NULL,
              stream_path TEXT NOT NULL UNIQUE,
              enabled BOOLEAN NOT NULL DEFAULT TRUE,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS publishers_enabled_idx ON publishers (enabled);

            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS desired_mode TEXT NOT NULL DEFAULT 'idle';
            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS actual_mode TEXT NOT NULL DEFAULT 'idle';
            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS device_connected BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS device_last_seen_at TIMESTAMPTZ;
            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS device_last_error TEXT;
            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS selected_inputs JSONB NOT NULL DEFAULT '[]'::jsonb;
            ALTER TABLE publishers
              ADD COLUMN IF NOT EXISTS available_inputs JSONB NOT NULL DEFAULT '[]'::jsonb;
            """
        )
    logger.info("Migrations applied")


async def bootstrap_admin() -> None:
    settings = get_settings()
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT id FROM admins LIMIT 1")
        existing = await cur.fetchone()
        if existing:
            logger.info("Admin already exists — skip bootstrap")
            return

        if not settings.admin_bootstrap_password:
            raise RuntimeError(
                "No admin exists and ADMIN_BOOTSTRAP_PASSWORD is not set"
            )

        password_hash = hash_password(settings.admin_bootstrap_password)
        await conn.execute(
            """
            INSERT INTO admins (id, username, password_hash)
            VALUES (%s, %s, %s)
            """,
            (str(uuid.uuid4()), settings.admin_bootstrap_user, password_hash),
        )
        logger.info("Bootstrapped admin user: %s", settings.admin_bootstrap_user)


async def fetch_one(sql: str, params: tuple[Any, ...] | list[Any] = ()) -> dict | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute(sql, params)
        return await cur.fetchone()


async def fetch_all(sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        return list(rows)


async def execute(sql: str, params: tuple[Any, ...] | list[Any] = ()) -> int:
    async with get_pool().connection() as conn:
        cur = await conn.execute(sql, params)
        return cur.rowcount or 0


@asynccontextmanager
async def connection() -> AsyncIterator[Any]:
    async with get_pool().connection() as conn:
        yield conn
