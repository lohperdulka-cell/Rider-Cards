"""Security-focused tests for the admin surface: uploads, 403s and audit log."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.product import Product
from app.routers.admin._common import UploadError, save_upload
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, USER_EMAIL, USER_PASSWORD, csrf_token


class _FakeUpload:
    """Minimal UploadFile stand-in: only what ``save_upload`` touches."""

    def __init__(self, buffer: io.BytesIO, content_type: str, filename: str) -> None:
        self.file = buffer
        self.content_type = content_type
        self.filename = filename

    async def read(self, size: int = -1) -> bytes:
        return self.file.read(size)


async def _login(client, email: str, password: str) -> None:
    page = await client.get("/login")
    response = await client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf_token(page.text)},
    )
    assert response.status_code == 303, response.text


async def test_upload_rejects_disallowed_mime():
    with pytest.raises(UploadError) as exc:
        await save_upload(_FakeUpload(io.BytesIO(b"<?php echo 1; ?>"), "text/x-php", "payload.php"))
    assert exc.value.code == "BAD_MIME"


async def test_upload_rejects_oversized_payload(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_size", 16)
    big = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    with pytest.raises(UploadError) as exc:
        await save_upload(_FakeUpload(big, "image/png", "big.png"))
    assert exc.value.code == "TOO_LARGE"


async def test_upload_renames_and_keeps_path_inside_uploads_dir():
    from app.config import UPLOAD_DIR

    data = b"\x89PNG\r\n\x1a\n" + b"payload"
    url = await save_upload(_FakeUpload(io.BytesIO(data), "image/png", "../../etc/passwd.png"))
    # The traversal path is discarded; only a sanitized stem plus a random token survive.
    assert url.startswith("/static/uploads/img-passwd-")
    assert ".." not in url and "/etc/" not in url
    stored = UPLOAD_DIR / url.rsplit("/", 1)[-1]
    assert stored.resolve().parent == UPLOAD_DIR.resolve()
    stored.unlink()


async def test_admin_route_forbidden_for_regular_user(client):
    await _login(client, USER_EMAIL, USER_PASSWORD)
    response = await client.get("/admin/products/new")
    assert response.status_code == 403


async def test_admin_create_product_writes_audit_log(client):
    await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    page = await client.get("/admin/products/new")
    response = await client.post(
        "/admin/products/new",
        data={
            "csrf_token": csrf_token(page.text),
            "slug": "audit-probe",
            "name_ru": "Тестовая колода",
            "name_en": "Audit probe",
            "brand": "RiderCards",
            "price": "1990.00",
            "stock": "5",
            "rarity": "common",
            "is_active": "on",
        },
    )
    assert response.status_code == 303, response.text

    async with SessionLocal() as session:
        product = (
            await session.execute(select(Product).where(Product.slug == "audit-probe"))
        ).scalar_one_or_none()
        assert product is not None, "product form did not create the product"
        entries = (await session.execute(select(AuditLog))).scalars().all()
    assert any(entry.entity == "product" for entry in entries), [
        (entry.entity, entry.action) for entry in entries
    ]
