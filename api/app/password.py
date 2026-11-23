"""Scrypt password hashing — compatible with the previous Node API format.

Stored form: scrypt$N$r$p$salt_b64url$key_b64url
The salt field is the base64url string itself; scrypt uses UTF-8 bytes of that string
(matching Node crypto.scrypt when salt is a string).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def hash_password(password: str) -> str:
    salt_str = _b64url_encode(secrets.token_bytes(16))
    n, r, p = 16384, 8, 1
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt_str.encode("utf-8"),
        n=n,
        r=r,
        p=p,
        dklen=32,
    )
    return f"scrypt${n}${r}${p}${salt_str}${_b64url_encode(key)}"


def verify_password(stored: str, password: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt_str = parts[4]
        expected = _b64url_decode(parts[5])
    except (ValueError, TypeError):
        return False

    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt_str.encode("utf-8"),
        n=n,
        r=r,
        p=p,
        dklen=len(expected),
    )
    return hmac.compare_digest(expected, actual)
