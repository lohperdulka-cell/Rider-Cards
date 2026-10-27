"""Flash messages carried between requests in a short-lived cookie.

The payload is base64url-encoded because cookie values are restricted to
latin-1, while our messages are frequently Cyrillic.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import Request, Response

FLASH_COOKIE = "rc_flash"
MAX_FLASH_BYTES = 3500
MAX_FLASH_ITEMS = 8


def _encode(items: list[dict[str, str]]) -> str:
    payload = json.dumps(items, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode(raw: str) -> list[dict[str, str]]:
    try:
        data: Any = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
    except (ValueError, TypeError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)][:MAX_FLASH_ITEMS]


def _read(request: Request) -> list[dict[str, str]]:
    raw = request.cookies.get(FLASH_COOKIE)
    return _decode(raw) if raw else []


def add(response: Response, message: str, category: str = "success") -> None:
    """Append a flash message; must be called before the response is returned."""
    pending: list[dict[str, str]] = list(getattr(response, "_rc_flash", []))
    pending.append({"message": str(message)[:500], "category": category})

    encoded = _encode(pending)
    while len(encoded) > MAX_FLASH_BYTES and len(pending) > 1:
        pending = pending[-3:]
        encoded = _encode(pending)

    response._rc_flash = pending  # type: ignore[attr-defined]
    response.set_cookie(
        FLASH_COOKIE,
        encoded,
        max_age=120,
        httponly=True,
        samesite="lax",
        path="/",
    )


def take(request: Request, response: Response) -> list[dict[str, str]]:
    """Return pending flashes and clear the cookie."""
    messages = _read(request)
    if messages:
        response.delete_cookie(FLASH_COOKIE, path="/")
    return messages
