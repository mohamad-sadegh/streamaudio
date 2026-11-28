"""Shared desired/actual mode helpers for remote device control."""

from __future__ import annotations

CONTROL_MODES = frozenset({"idle", "streaming", "recording"})


def normalize_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    cleaned = mode.strip().lower()
    if cleaned not in CONTROL_MODES:
        return None
    return cleaned
