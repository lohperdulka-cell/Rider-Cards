"""Admin chat console: filter unread, search by user/order, open any chat."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.deps import AdminUser, PageContext, SessionDep
from app.models.chat import SenderRole
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.templating import render

router = APIRouter(prefix="/admin/chats")


@router.get("", name="admin_chats")
async def chats_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    only_unread: str = Query(default="", max_length=5),
    q: str = Query(default="", max_length=120),
):
    chats = await chat_service.list_for_admin(
        session, only_unread=only_unread in {"1", "true"}, query=q, limit=100
    )
    return await render(
        request,
        "admin/chats/list.html",
        admin=admin,
        chats=chats,
        filters={"only_unread": only_unread, "q": q},
    )


@router.get("/{chat_id}", name="admin_chat_thread")
async def chat_thread(
    request: Request, chat_id: int, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    chat = await chat_service.get_chat(session, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="CHAT_NOT_FOUND")
    order = await orders_service.get_any(session, chat.order_id)
    await chat_service.mark_read(session, chat, reader_role=SenderRole.admin)
    await session.commit()
    return await render(
        request,
        "chat/thread.html",
        chat=chat,
        order=order,
        is_admin=True,
        admin=admin,
    )


@router.post("/{chat_id}/close", name="admin_chat_close")
async def chat_close(
    request: Request, chat_id: int, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    from app.deps import CsrfDep
    from fastapi import Depends

    chat = await chat_service.get_chat(session, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="CHAT_NOT_FOUND")
    chat.is_closed = not chat.is_closed
    await session.commit()
    return RedirectResponse(f"/admin/chats/{chat_id}", status_code=303)
