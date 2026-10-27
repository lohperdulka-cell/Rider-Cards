"""WebSocket endpoint for order chats with per-chat authorisation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.models.chat import Chat, SenderRole
from app.models.user import User
from app.security import load_session
from app.services import chat as chat_service
from app.ws.chat_manager import chat_manager

logger = logging.getLogger("ridercards.ws")

router = APIRouter()


async def _authenticate(websocket: WebSocket) -> User | None:
    token = websocket.cookies.get(settings.session_cookie_name, "")
    data = load_session(token)
    if not data or not data.get("uid"):
        return None
    async with SessionLocal() as session:
        user = await session.get(User, int(data["uid"]))
        if user is None or not user.is_active:
            return None
        return user


async def _can_access(chat_id: int, user: User) -> bool:
    async with SessionLocal() as session:
        chat = (await session.execute(select(Chat).where(Chat.id == chat_id))).scalars().first()
        if chat is None:
            return False
        return chat_service.can_access(chat, user)


@router.websocket("/ws/chat/{chat_id}")
async def chat_socket(websocket: WebSocket, chat_id: int):
    user = await _authenticate(websocket)
    if user is None:
        await websocket.close(code=4401, reason="unauthorised")
        return
    if not await _can_access(chat_id, user):
        await websocket.close(code=4403, reason="forbidden")
        return

    await websocket.accept()
    await chat_manager.connect(chat_id, websocket, is_admin=user.is_admin)

    async with SessionLocal() as session:
        chat = await chat_service.get_chat(session, chat_id)
        if chat is not None:
            await websocket.send_json(
                {
                    "type": "history",
                    "messages": [
                        chat_service.message_payload(m, viewer_is_admin=user.is_admin) for m in chat.messages
                    ],
                }
            )

    try:
        while True:
            payload = await websocket.receive_json()
            kind = str(payload.get("type", "message"))

            if kind == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if kind == "read":
                async with SessionLocal() as session:
                    chat = await chat_service.get_chat(session, chat_id)
                    if chat is not None:
                        role = SenderRole.admin if user.is_admin else SenderRole.user
                        await chat_service.mark_read(session, chat, reader_role=role)
                        await session.commit()
                continue

            if kind != "message":
                continue

            text = str(payload.get("text", ""))
            async with SessionLocal() as session:
                chat = await chat_service.get_chat(session, chat_id)
                if chat is None:
                    await websocket.send_json({"type": "error", "detail": "CHAT_NOT_FOUND"})
                    continue
                if not chat_service.can_access(chat, user):
                    await websocket.close(code=4403, reason="forbidden")
                    return
                try:
                    message = await chat_service.post_message(
                        session,
                        chat=chat,
                        sender=user,
                        role=SenderRole.admin if user.is_admin else SenderRole.user,
                        text=text,
                    )
                except chat_service.ChatError as exc:
                    await session.rollback()
                    await websocket.send_json({"type": "error", "detail": exc.code})
                    continue
                await session.commit()
                message_payload = chat_service.message_payload(message, viewer_is_admin=user.is_admin)

            await chat_manager.broadcast(chat_id, {"type": "message", "message": message_payload})
            if not user.is_admin:
                await chat_manager.broadcast_global({"type": "unread", "chat_id": chat_id})

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - never crash the worker on a bad frame
        logger.exception("chat socket error chat_id=%s", chat_id)
    finally:
        await chat_manager.disconnect(chat_id, websocket)
