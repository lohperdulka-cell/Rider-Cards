"""Order chats: list, thread view, message posting, read marking, polling API."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.deps import CsrfDep, PageContext, SessionDep
from app.i18n import translate
from app.models.chat import SenderRole
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.templating import render

router = APIRouter(prefix="/chats")


@router.get("", name="chats_list")
async def chats_list(request: Request, session: SessionDep, ctx: PageContext):
    locale = request.state.locale
    user = request.state.user
    if user is None:
        return RedirectResponse("/login?next=/chats", status_code=303)
    if user.is_admin:
        return RedirectResponse("/admin/chats", status_code=303)
    chats = await chat_service.list_for_user(session, user.id)
    return await render(
        request,
        "chat/list.html",
        chats=chats,
        crumbs=[(translate(locale, "chat.list_title"), None)],
    )


@router.get("/{chat_id}", name="chat_thread")
async def chat_thread(request: Request, chat_id: int, session: SessionDep, ctx: PageContext):
    locale = request.state.locale
    user = request.state.user
    if user is None:
        return RedirectResponse(f"/login?next=/chats/{chat_id}", status_code=303)

    chat = await chat_service.get_chat(session, chat_id)
    if chat is None or not chat_service.can_access(chat, user):
        raise HTTPException(status_code=403, detail="CHAT_FORBIDDEN")

    order = await orders_service.get_any(session, chat.order_id)
    if not user.is_admin:
        await chat_service.mark_read(session, chat, reader_role=SenderRole.user)
        await session.commit()

    return await render(
        request,
        "chat/thread.html",
        chat=chat,
        order=order,
        is_admin=user.is_admin,
        crumbs=[
            (translate(locale, "chat.list_title"), "/chats"),
            (translate(locale, "orders.detail.title", id=chat.order_id), None),
        ],
    )


@router.get("/{chat_id}/messages", name="chat_messages")
async def chat_messages(request: Request, chat_id: int, session: SessionDep, ctx: PageContext):
    """Polling fallback used when the WebSocket is unavailable."""
    user = request.state.user
    if user is None:
        return JSONResponse({"detail": "AUTH_REQUIRED"}, status_code=401)
    chat = await chat_service.get_chat(session, chat_id)
    if chat is None or not chat_service.can_access(chat, user):
        return JSONResponse({"detail": "CHAT_FORBIDDEN"}, status_code=403)
    return JSONResponse(
        {
            "messages": [
                chat_service.message_payload(message, viewer_is_admin=user.is_admin)
                for message in chat.messages
            ]
        }
    )


@router.post("/{chat_id}/messages", name="chat_send")
async def chat_send(request: Request, chat_id: int, session: SessionDep, ctx: PageContext, _csrf: CsrfDep):
    locale = request.state.locale
    user = request.state.user
    if user is None:
        return JSONResponse({"detail": "AUTH_REQUIRED"}, status_code=401)

    chat = await chat_service.get_chat(session, chat_id)
    if chat is None or not chat_service.can_access(chat, user):
        return JSONResponse({"detail": "CHAT_FORBIDDEN"}, status_code=403)

    text = await _extract_text(request)
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
        key = {
            "RATE_LIMITED": "chat.rate_limited",
            "CHAT_CLOSED": "chat.closed",
        }.get(exc.code, "chat.rate_limited")
        return JSONResponse(
            {"detail": translate(locale, key)}, status_code=429 if exc.code == "RATE_LIMITED" else 400
        )

    await session.commit()
    payload = chat_service.message_payload(message, viewer_is_admin=user.is_admin)

    from app.ws import chat_manager

    await chat_manager.broadcast(chat.id, {"type": "message", "message": payload})
    if not user.is_admin:
        await chat_manager.broadcast_global({"type": "unread", "chat_id": chat.id})

    return JSONResponse({"ok": True, "message": payload})


@router.post("/{chat_id}/read", name="chat_read")
async def chat_read(request: Request, chat_id: int, session: SessionDep, ctx: PageContext, _csrf: CsrfDep):
    user = request.state.user
    if user is None:
        return JSONResponse({"detail": "AUTH_REQUIRED"}, status_code=401)
    chat = await chat_service.get_chat(session, chat_id)
    if chat is None or not chat_service.can_access(chat, user):
        return JSONResponse({"detail": "CHAT_FORBIDDEN"}, status_code=403)
    role = SenderRole.admin if user.is_admin else SenderRole.user
    updated = await chat_service.mark_read(session, chat, reader_role=role)
    await session.commit()
    return JSONResponse({"ok": True, "updated": updated})


async def _extract_text(request: Request) -> str:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            return ""
        return str(payload.get("text", ""))
    form = await request.form()
    return str(form.get("text", ""))
