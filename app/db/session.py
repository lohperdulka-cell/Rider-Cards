"""Async engine and session factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine_url = settings.engine_url
_connect_args: dict[str, object] = {}

if not settings.is_sqlite and "pooler" in _engine_url:
    # Neon's pooler is PgBouncer in transaction mode, which hands a backend to
    # whoever needs it next. A prepared statement made on one transaction may
    # not exist in the next, so the cache is switched off. Direct connections
    # keep it, and with it the performance benefit.
    _connect_args["prepared_statement_cache_size"] = 0

engine = create_async_engine(
    _engine_url,
    echo=False,
    future=True,
    pool_pre_ping=not settings.is_sqlite,
    connect_args=_connect_args,
)

if settings.is_sqlite:  # pragma: no cover - import side effect
    from app.db import sqlite as _sqlite_functions

    _sqlite_functions.register(engine)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session.

    ``HTTPException`` is deliberately not rolled back: auth/not-found errors are
    raised before any write, and a rollback would expire the loaded ``User``
    instance that the 403/404 templates render after the session is closed.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except HTTPException:
            raise
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager for background tasks and scripts."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
