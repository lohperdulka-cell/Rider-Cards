"""Authentication and user account operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.security import hash_password, needs_rehash, verify_password


class AuthError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(func.lower(User.email) == email.lower().strip()))
    return result.scalar_one_or_none()


async def register(session: AsyncSession, *, name: str, email: str, password: str) -> User:
    email = email.lower().strip()
    if await get_by_email(session, email) is not None:
        raise AuthError("EMAIL_TAKEN")
    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        is_admin=False,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("BAD_CREDENTIALS")
    if not user.is_active:
        raise AuthError("ACCOUNT_BLOCKED")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


async def update_profile(session: AsyncSession, user: User, *, name: str, email: str, locale: str) -> User:
    email = email.lower().strip()
    if email != user.email:
        existing = await get_by_email(session, email)
        if existing is not None and existing.id != user.id:
            raise AuthError("EMAIL_TAKEN")
    user.name = name.strip()
    user.email = email
    user.locale = locale
    await session.flush()
    return user


async def change_password(session: AsyncSession, user: User, *, current: str, new: str, confirm: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AuthError("BAD_CURRENT_PASSWORD")
    if new != confirm:
        raise AuthError("PASSWORD_MISMATCH")
    user.password_hash = hash_password(new)
    await session.flush()


async def ensure_default_admin(session: AsyncSession) -> User | None:
    """Create the env-configured admin on first boot (idempotent)."""
    email = settings.admin_email.lower().strip()
    existing = await get_by_email(session, email)
    if existing is not None:
        if not existing.is_admin:
            existing.is_admin = True
            await session.flush()
        return existing
    admin = User(
        name="Administrator",
        email=email,
        password_hash=hash_password(settings.admin_password),
        is_admin=True,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    return admin
