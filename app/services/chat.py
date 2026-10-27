"""Chat operations: access checks, message posting, read tracking, rate limiting."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Chat, Message, SenderRole
from app.models.order import Order
from app.models.user import User

RATE_LIMIT_SECONDS = 2.0
MAX_MESSAGE_LEN = 2000


class ChatError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# Simple in-process throttle: user_id -> last send monotonic timestamp.
_last_send: dict[int, float] = {}


def check_rate_limit(user_id: int, now: float | None = None) -> bool:
    """Return True when the user may send; also records the attempt."""
    current = time.monotonic() if now is None else now
    previous = _last_send.get(user_id, 0.0)
    if current - previous < RATE_LIMIT_SECONDS:
        return False
    _last_send[user_id] = current
    return True


def reset_rate_limit() -> None:
    _last_send.clear()


async def get_chat(session: AsyncSession, chat_id: int) -> Chat | None:
    stmt = (
        select(Chat).options(selectinload(Chat.messages), selectinload(Chat.order)).where(Chat.id == chat_id)
    )
    return (await session.execute(stmt)).scalars().first()


async def get_chat_for_order(session: AsyncSession, order_id: int) -> Chat | None:
    stmt = select(Chat).options(selectinload(Chat.messages)).where(Chat.order_id == order_id)
    return (await session.execute(stmt)).scalars().first()


async def get_chat_for_user(session: AsyncSession, chat_id: int, user_id: int) -> Chat | None:
    stmt = (
        select(Chat)
        .options(selectinload(Chat.messages), selectinload(Chat.order))
        .where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    return (await session.execute(stmt)).scalars().first()


def can_access(chat: Chat, user: User | None) -> bool:
    if user is None:
        return False
    if user.is_admin:
        return True
    return chat.user_id == user.id


async def post_message(
    session: AsyncSession,
    *,
    chat: Chat,
    sender: User | None,
    role: SenderRole,
    text: str,
    enforce_rate_limit: bool = True,
) -> Message:
    text = text.replace("\x00", "").strip()
    if not text:
        raise ChatError("EMPTY_MESSAGE")
    if len(text) > MAX_MESSAGE_LEN:
        raise ChatError("MESSAGE_TOO_LONG")
    if chat.is_closed:
        raise ChatError("CHAT_CLOSED")
    if (
        enforce_rate_limit
        and sender is not None
        and role == SenderRole.user
        and not check_rate_limit(sender.id)
    ):
        raise ChatError("RATE_LIMITED")

    message = Message(
        chat_id=chat.id,
        sender_id=sender.id if sender else None,
        sender_role=role,
        text=text,
    )
    session.add(message)
    await session.flush()
    return message


async def mark_read(session: AsyncSession, chat: Chat, *, reader_role: SenderRole) -> int:
    """Mark messages of the counterpart role as read."""
    target_role = SenderRole.admin if reader_role == SenderRole.user else SenderRole.user
    now = datetime.now(UTC)
    updated = 0
    for message in chat.messages:
        if message.sender_role == target_role and message.read_at is None:
            message.read_at = now
            updated += 1
    if updated:
        await session.flush()
    return updated


async def unread_count_for_user(session: AsyncSession, user_id: int) -> int:
    stmt = (
        select(func.count(Message.id))
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Chat.user_id == user_id,
            Message.sender_role == SenderRole.admin,
            Message.read_at.is_(None),
        )
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def unread_count_for_admin(session: AsyncSession) -> int:
    stmt = select(func.count(Message.id)).where(
        Message.sender_role == SenderRole.user, Message.read_at.is_(None)
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def list_for_user(session: AsyncSession, user_id: int) -> list[Chat]:
    stmt = (
        select(Chat)
        .options(selectinload(Chat.messages), selectinload(Chat.order))
        .where(Chat.user_id == user_id)
        .order_by(Chat.id.desc())
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def list_for_admin(
    session: AsyncSession,
    *,
    only_unread: bool = False,
    query: str = "",
    limit: int = 100,
) -> list[Chat]:
    stmt = select(Chat).options(
        selectinload(Chat.messages),
        selectinload(Chat.order),
        selectinload(Chat.user),
    )
    if query:
        needle = f"%{query.strip().lower()}%"
        stmt = stmt.join(User, Chat.user_id == User.id).join(Order, Chat.order_id == Order.id)
        if query.strip().isdigit():
            stmt = stmt.where(Order.id == int(query.strip()))
        else:
            stmt = stmt.where(func.lower(User.email).like(needle) | func.lower(User.name).like(needle))
    stmt = stmt.order_by(Chat.id.desc()).limit(limit)
    chats = list((await session.execute(stmt)).scalars().unique().all())
    if only_unread:
        chats = [c for c in chats if c.unread_for_admin > 0]
    return chats


def message_payload(message: Message, *, viewer_is_admin: bool = False) -> dict[str, Any]:
    """Serialisable message for WebSocket/HTMX transports."""
    return {
        "id": message.id,
        "chat_id": message.chat_id,
        "text": message.text,
        "role": message.sender_role.value,
        "sender": (message.sender.display_name if message.sender else "RiderCards"),
        "initials": (message.sender.initials if message.sender else "RC"),
        "created_at": message.created_at.strftime("%H:%M") if message.created_at else "",
        "created_full": message.created_at.strftime("%d.%m.%Y %H:%M") if message.created_at else "",
        "is_system": message.is_system,
        "own": bool(message.sender_id is None) if viewer_is_admin is None else False,
    }
