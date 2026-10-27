"""Unicode-aware ``lower``/``upper``/``like`` for SQLite connections.

SQLite's built-in ``lower()`` only folds ASCII, so ``lower('Колода')`` stays
unchanged and case-insensitive search silently fails for Cyrillic. PostgreSQL
folds Unicode natively, which makes the two backends behave differently. These
replacements use Python's Unicode-aware implementations so search behaves the
same everywhere.
"""

from __future__ import annotations

import re
import sqlite3

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine


def _lower(value: object) -> str | None:
    if value is None:
        return None
    return str(value).lower()


def _upper(value: object) -> str | None:
    if value is None:
        return None
    return str(value).upper()


def _like(pattern: object, value: object) -> int | None:
    """SQLite-compatible LIKE: ``%`` any run, ``_`` one char, case-insensitive."""
    if pattern is None or value is None:
        return None
    regex = "".join(".*" if char == "%" else "." if char == "_" else re.escape(char) for char in str(pattern))
    return 1 if re.fullmatch(regex, str(value), flags=re.DOTALL | re.IGNORECASE) else 0


def _install(dbapi_connection) -> None:
    """Walk the DBAPI wrappers down to the raw sqlite3 connection.

    Layers: SQLAlchemy ``AsyncAdapt_aiosqlite_connection`` -> ``aiosqlite.Connection``
    -> ``sqlite3.Connection``. ``create_function`` must be called on the last one;
    the aiosqlite variant is a coroutine and cannot be used from this hook.
    """
    connection = dbapi_connection
    for _ in range(4):
        if isinstance(connection, sqlite3.Connection):
            break
        inner = getattr(connection, "_connection", None)
        if inner is None:
            return
        connection = inner

    if not isinstance(connection, sqlite3.Connection):
        return
    connection.create_function("lower", 1, _lower, deterministic=True)
    connection.create_function("upper", 1, _upper, deterministic=True)
    connection.create_function("like", 2, _like, deterministic=True)


def register(engine: AsyncEngine) -> None:
    """Install the Unicode-aware functions on every new pooled connection."""
    event.listen(engine.sync_engine, "connect", lambda conn, _record: _install(conn))
