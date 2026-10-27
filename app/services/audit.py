"""Audit log writer used by every mutating admin action."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def record(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity: str = "",
    entity_id: int | None = None,
    details: str = "",
    ip: str = "",
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else "",
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details[:2000],
        ip=ip[:64],
    )
    session.add(entry)
    await session.flush()
    return entry


async def recent(session: AsyncSession, limit: int = 50) -> list[AuditLog]:
    from sqlalchemy import select

    result = await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
    return list(result.scalars().all())


def diff_details(before: dict[str, Any], after: dict[str, Any]) -> str:
    changes = [f"{k}: {before.get(k)!r} -> {after.get(k)!r}" for k in after if before.get(k) != after.get(k)]
    return "; ".join(changes)[:2000]
