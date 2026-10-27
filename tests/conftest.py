"""Shared pytest fixtures: isolated SQLite database and an HTTP client.

Every test module gets a fresh temporary database file, so tests never touch
``data/ridercards.db`` and can run in parallel.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="ridercards-tests-")
_DB_PATH = Path(_TMP_DIR) / "test.db"

os.environ["ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdefghij"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"
os.environ["COOKIE_SECURE"] = "false"
os.environ["ADMIN_LOGIN"] = "admin"
os.environ["ADMIN_PASSWORD"] = "AdminTestPassw0rd!"
os.environ["ADMIN_EMAIL"] = "admin@ridercards.dev"

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.category import Category  # noqa: E402
from app.models.product import Product, Rarity  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.auth import ensure_default_admin  # noqa: E402

ADMIN_EMAIL = settings.admin_email
ADMIN_PASSWORD = settings.admin_password
USER_EMAIL = "buyer@example.dev"
USER_PASSWORD = "BuyerPassw0rd1"


@pytest.fixture(scope="session", autouse=True)
async def _database() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        category = Category(
            slug="classic",
            name_ru="Классические",
            name_en="Classic",
            description_ru="Классика",
            description_en="Classics",
            icon="♦",
            is_active=True,
        )
        session.add(category)
        await session.flush()

        session.add_all(
            [
                Product(
                    slug="test-deck",
                    name_ru="Тестовая колода",
                    name_en="Test deck",
                    brand="RiderCards",
                    category_id=category.id,
                    price=1000,
                    stock=10,
                    rarity=Rarity.common,
                    is_active=True,
                    description_ru="Описание",
                    description_en="Description",
                ),
                Product(
                    slug="cheap-deck",
                    name_ru="Дешёвая колода",
                    name_en="Cheap deck",
                    brand="RiderCards",
                    category_id=category.id,
                    price=500,
                    stock=0,
                    rarity=Rarity.rare,
                    is_active=True,
                    description_ru="Описание",
                    description_en="Description",
                ),
            ]
        )
        await ensure_default_admin(session)
        session.add(
            User(
                name="Buyer",
                email=USER_EMAIL,
                password_hash=hash_password(USER_PASSWORD),
                is_active=True,
            )
        )
        await session.commit()

    yield

    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_chat_rate_limit():
    """The chat throttle keeps in-process state; reset it between tests."""
    from app.services import chat as chat_service

    chat_service.reset_rate_limit()
    yield
    chat_service.reset_rate_limit()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
            # Mimic a browser so auth failures render a redirect instead of JSON.
            headers={"accept": "text/html,application/xhtml+xml"},
        ) as http,
    ):
        yield http


def csrf_token(html: str) -> str:
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return match.group(1) if match else ""


async def login(
    client: httpx.AsyncClient, email: str = USER_EMAIL, password: str = USER_PASSWORD
) -> httpx.Response:
    page = await client.get("/login")
    return await client.post(
        "/login",
        data={
            "csrf_token": csrf_token(page.text),
            "email": email,
            "password": password,
            "next": "/",
        },
    )


async def register(
    client: httpx.AsyncClient, email: str, password: str = "NewUserPassw0rd1"
) -> httpx.Response:
    page = await client.get("/register")
    return await client.post(
        "/register",
        data={
            "csrf_token": csrf_token(page.text),
            "name": "New User",
            "email": email,
            "password": password,
            "password_confirm": password,
            "next": "/",
        },
    )
