"""Shared helpers for admin routers."""

from __future__ import annotations

import re
import secrets
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import UPLOAD_DIR, settings
from app.models.product import Product
from app.services import audit as audit_service

TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


class UploadError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def slugify(value: str) -> str:
    """Transliterate Cyrillic and normalise into a URL-safe slug."""
    value = unicodedata.normalize("NFKD", value or "")
    transliterated = "".join(TRANSLIT.get(ch, ch) for ch in value.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    return slug[:150] or "item"


async def unique_slug(session: AsyncSession, model, base: str, *, exclude_id: int | None = None) -> str:
    slug = slugify(base)
    candidate = slug
    counter = 2
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if (await session.execute(stmt)).first() is None:
            return candidate
        candidate = f"{slug}-{counter}"
        counter += 1


def as_upload(value: object) -> UploadFile | None:
    """FormData values are untyped; only real uploads carry a filename."""
    if isinstance(value, UploadFile) and value.filename:
        return value
    return None


async def save_upload(file: UploadFile | None, *, prefix: str = "img") -> str:
    """Validate and persist an uploaded image, returning its public URL path."""
    if file is None or not file.filename:
        return ""
    content_type = (file.content_type or "").lower()
    if content_type not in settings.allowed_image_types_list:
        raise UploadError("BAD_MIME")

    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(content_type)
    if not extension:
        raise UploadError("BAD_MIME")

    data = await file.read(settings.max_upload_size + 1)
    if len(data) > settings.max_upload_size:
        raise UploadError("TOO_LARGE")
    if not data:
        raise UploadError("EMPTY")

    stem = re.sub(r"[^a-z0-9]+", "-", Path(file.filename).stem.lower())[:40] or "image"
    filename = f"{prefix}-{stem}-{secrets.token_hex(6)}{extension}"
    target = (UPLOAD_DIR / filename).resolve()
    if target.parent != UPLOAD_DIR.resolve():
        raise UploadError("BAD_PATH")
    target.write_bytes(data)
    return f"/static/uploads/{filename}"


async def log_action(
    session: AsyncSession,
    request: Request,
    *,
    actor: Any,
    action: str,
    entity: str = "",
    entity_id: int | None = None,
    details: str = "",
) -> None:
    from app.deps import client_ip

    await audit_service.record(
        session,
        actor=actor,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        ip=client_ip(request),
    )


async def paginate(
    session: AsyncSession, stmt_base, *, page: int = 1, per_page: int = 20
) -> tuple[list[Any], int, int]:
    """Return (rows, total, pages) for a simple list screen."""
    page = max(1, page)
    count_stmt = select(func.count()).select_from(stmt_base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    rows = list(
        (await session.execute(stmt_base.limit(per_page).offset((page - 1) * per_page)))
        .scalars()
        .unique()
        .all()
    )
    return rows, total, pages


async def product_choices(session: AsyncSession) -> list[Product]:
    stmt = select(Product).where(Product.is_deleted.is_(False)).order_by(Product.name_ru).limit(500)
    return list((await session.execute(stmt)).scalars().unique().all())
