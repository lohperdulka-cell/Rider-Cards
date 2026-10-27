"""Checkout: turns the cookie cart into an order and opens the support chat."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import flash
from app.deps import CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.schemas.order import CheckoutIn
from app.services import cart as cart_service
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.services.chat import message_payload
from app.templating import render

router = APIRouter(prefix="/checkout")


def _cart(request: Request) -> dict[int, int]:
    return cart_service.load_cart(request.cookies.get(cart_service.CART_COOKIE))


@router.get("", name="checkout_page")
async def checkout_page(request: Request, session: SessionDep, ctx: PageContext):
    locale = request.state.locale
    user = request.state.user
    if user is None:
        return RedirectResponse("/login?next=/checkout", status_code=303)

    cart = _cart(request)
    items = await cart_service.get_cart_items(session, cart)
    if not items:
        response = RedirectResponse("/cart", status_code=303)
        flash.add(response, translate(locale, "checkout.errors.empty"), "warning")
        return response

    return await render(
        request,
        "pages/checkout.html",
        items=items,
        total=cart_service.cart_total(items),
        form_data={"contact": user.email},
        errors={},
        crumbs=[(translate(locale, "checkout.title"), None)],
    )


@router.post("", name="checkout_submit")
async def checkout_submit(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    user = request.state.user
    if user is None:
        return RedirectResponse("/login?next=/checkout", status_code=303)

    cart = _cart(request)
    items = await cart_service.get_cart_items(session, cart)
    total = cart_service.cart_total(items)

    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    try:
        data = CheckoutIn(**payload)
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "form"
            errors[field] = str(error["msg"])
        return await render(
            request,
            "pages/checkout.html",
            items=items,
            total=total,
            form_data=payload,
            errors=errors,
            status_code=400,
            crumbs=[(translate(locale, "checkout.title"), None)],
        )

    if not items:
        response = RedirectResponse("/cart", status_code=303)
        flash.add(response, translate(locale, "checkout.errors.empty"), "warning")
        return response

    try:
        order = await orders_service.create_from_cart(
            session,
            user=user,
            cart=cart,
            contact=data.contact,
            address=data.address,
            note=data.note,
        )
    except orders_service.OrderError as exc:
        await session.rollback()
        response = RedirectResponse("/cart", status_code=303)
        flash.add(
            response,
            translate(locale, "checkout.errors.empty")
            if exc.code == "EMPTY_CART"
            else translate(locale, "checkout.errors.validation"),
            "error",
        )
        return response

    await session.commit()

    # Push the freshly created system message to any open admin sockets.
    chat = await chat_service.get_chat_for_order(session, order.id)
    if chat is not None and chat.messages:
        last = chat.messages[-1]
        await chat_service_notify(chat.id, message_payload(last))

    response = RedirectResponse(f"/profile/orders/{order.id}", status_code=303)
    response.delete_cookie(cart_service.CART_COOKIE, path="/")
    flash.add(response, translate(locale, "checkout.created", id=order.id), "success")
    return response


async def chat_service_notify(chat_id: int, payload: dict) -> None:
    from app.ws import chat_manager

    await chat_manager.broadcast(chat_id, {"type": "message", "message": payload})
    await chat_manager.broadcast_global({"type": "unread", "chat_id": chat_id})
