"""Create or reset the default admin account from the environment.

Usage: ``python -m app.scripts.create_admin`` (or ``make create-admin``).
Idempotent: re-running resets the password to ``ADMIN_PASSWORD``.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.config import settings
from app.db.base import Base
from app.db.session import engine, session_scope
from app.models.user import User
from app.security import hash_password


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    email = settings.admin_email.lower().strip()
    async with session_scope() as session:
        existing = (await session.execute(select(User).where(User.email == email))).scalars().first()
        if existing is None:
            session.add(
                User(
                    name="Administrator",
                    email=email,
                    password_hash=hash_password(settings.admin_password),
                    is_admin=True,
                    is_active=True,
                )
            )
            action = "created"
        else:
            existing.is_admin = True
            existing.is_active = True
            existing.password_hash = hash_password(settings.admin_password)
            action = "updated"

    print(f"admin {action}: {email} (login: {settings.admin_login})")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
