"""Connection-string handling for managed Postgres providers.

Neon and Render hand out URLs that asyncpg cannot consume verbatim, so the
normalisation in ``Settings`` is what stands between a copied URL and a
working deploy. These tests pin that behaviour.
"""

from __future__ import annotations

import pytest

from app.config import Settings

NEON_DIRECT = (
    "postgresql://user:pw@ep-x.c-14.us-east-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_POOLED = (
    "postgresql://user:pw@ep-x-pooler.c-14.us-east-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


def _settings(**kwargs: str) -> Settings:
    base = {"secret_key": "test-secret-key-0123456789abcdefghij", "env": "test"}
    return Settings(**{**base, **kwargs})


def test_sslmode_becomes_ssl_and_channel_binding_is_dropped() -> None:
    # asyncpg rejects both as unexpected keyword arguments, so passing the URL
    # through untouched raises TypeError at connect time.
    s = _settings(database_url=NEON_DIRECT)
    assert s.database_url == (
        "postgresql+asyncpg://user:pw@ep-x.c-14.us-east-1.aws.neon.tech/neondb?ssl=require"
    )
    assert "sslmode" not in s.database_url
    assert "channel_binding" not in s.database_url


def test_bare_scheme_is_upgraded_to_asyncpg() -> None:
    s = _settings(database_url="postgres://user:pw@host/db")
    assert s.database_url == "postgresql+asyncpg://user:pw@host/db"


def test_unrelated_query_params_are_preserved() -> None:
    s = _settings(database_url="postgresql://user:pw@host/db?application_name=rc&sslmode=require")
    assert "application_name=rc" in s.database_url
    assert "ssl=require" in s.database_url


def test_engine_url_prefers_pooled_and_migration_url_prefers_direct() -> None:
    # The request path wants PgBouncer; DDL wants the direct endpoint.
    s = _settings(
        database_url=NEON_DIRECT,
        database_url_pooled=NEON_POOLED,
        database_url_unpooled=NEON_DIRECT,
    )
    assert "-pooler" in s.engine_url
    assert "-pooler" not in s.migration_url


def test_engine_url_falls_back_to_database_url() -> None:
    # A single DATABASE_URL (Render, local Postgres) must keep working.
    s = _settings(database_url=NEON_DIRECT)
    assert s.engine_url == s.database_url
    assert s.migration_url == s.database_url


def test_sqlite_urls_are_left_alone() -> None:
    s = _settings(database_url="sqlite+aiosqlite:///./data/x.db")
    assert s.is_sqlite is True
    assert s.engine_url == "sqlite+aiosqlite:///./data/x.db"


@pytest.mark.parametrize("url", [NEON_DIRECT, NEON_POOLED])
def test_neon_urls_are_not_sqlite(url: str) -> None:
    assert _settings(database_url=url).is_sqlite is False
