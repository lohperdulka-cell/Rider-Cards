"""Customer-facing orders: history, details, cancellation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import flash
from app.deps import CsrfDep, PageContext, SessionDep, CurrentUser
from app.i18n import translate
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.templating import render

router = APIRouter(prefix="/profile/orders")


@router.get("", name="orders_list")
async def orders_list(request: Request, session: SessionDep, ctx: PageContext, user: CurrentUser):
    orders = await orders_service.list_for_user(session, user.id)
    chats = {chat.order_id: chat.id for chat in await chat_service.list_for_user(session, user.id)}
    return await render(
        request,
        "pages/orders/list.html",
        orders=orders,
        chats=chats,
        crumbs=[
            (translate(request.state.locale, "profile.title"), "/profile"),
            (translate(request.state.locale, "orders.title"), None),
        ],
    )


@router.get("/{order_id}", name="order_detail")
async def order_detail(
    request: Request, order_id: int, session: SessionDep, ctx: PageContext, user: CurrentUser
):
    order = await orders_service.get_for_user(session, order_id, user.id)
    if order is None:
        raise HTTPException(status_code=404, detail="ORDER_NOT_FOUND")
    chat = await chat_service.get_chat_for_order(session, order.id)
    locale = request.state.locale
    return await render(
        request,
        "pages/orders/detail.html",
        order=order,
        chat=chat,
        crumbs=[
            (translate(locale, "profile.title"), "/profile"),
            (translate(locale, "orders.title"), "/profile/orders"),
            (translate(locale, "orders.detail.title", id=order.id), None),
        ],
    )


@router.post("/{order_id}/cancel", name="order_cancel")
async def order_cancel(
    request: Request,
    order_id: int,
    session: SessionDep,
    ctx: PageContext,
    user: CurrentUser,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    order = await orders_service.get_for_user(session, order_id, user.id)
    if order is None:
        raise HTTPException(status_code=404, detail="ORDER_NOT_FOUND")

    try:
        await orders_service.cancel_by_user(session, order, locale=locale)
        await session.commit()
        chat = await chat_service.get_chat_for_order(session, order_id)
        message = chat.messages[-1] if chat and chat.messages else None
    except orders_service.OrderError:
        await session.rollback()
        response = RedirectResponse(f"/profile/orders/{order_id}", status_code=303)
        flash.add(response, translate(locale, "orders.cannot_cancel"), "error")
        return response

    if message is not None:
        chat = await chat_service.get_chat_for_order(session, order_id)
        if chat is not None:
            from app.ws import chat_manager

            await chat_manager.broadcast(
                chat.id, {"type": "message", "message": chat_service.message_payload(message)}
            )

    response = RedirectResponse(f"/profile/orders/{order_id}", status_code=303)
    flash.add(response, translate(locale, "orders.cancelled"), "info")
    return response
