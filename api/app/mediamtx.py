from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def list_paths() -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.mediamtx_api_url.rstrip('/')}/v3/paths/list"
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(url)
        res.raise_for_status()
        return res.json()


def path_online_map(list_payload: dict[str, Any] | None) -> dict[str, bool]:
    items = (list_payload or {}).get("items") or []
    return {item["name"]: bool(item.get("ready")) for item in items if "name" in item}
