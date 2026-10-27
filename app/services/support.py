"""Support ticket operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support import SupportTicket, TicketStatus
from app.models.user import User


async def create(
    session: AsyncSession,
    *,
    user: User | None,
    name: str,
    email: str,
    subject: str,
    message: str,
) -> SupportTicket:
    ticket = SupportTicket(
        user_id=user.id if user else None,
        name=name.strip(),
        email=email.lower().strip(),
        subject=subject.strip(),
        message=message.strip(),
        status=TicketStatus.new,
    )
    session.add(ticket)
    await session.flush()
    return ticket


async def list_for_user(session: AsyncSession, user_id: int) -> list[SupportTicket]:
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_all(session: AsyncSession, *, limit: int = 100) -> list[SupportTicket]:
    stmt = select(SupportTicket).order_by(SupportTicket.id.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get(session: AsyncSession, ticket_id: int) -> SupportTicket | None:
    return await session.get(SupportTicket, ticket_id)


async def set_status(session: AsyncSession, ticket: SupportTicket, status: TicketStatus) -> None:
    ticket.status = status
    await session.flush()
