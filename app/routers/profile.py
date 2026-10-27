"""Customer profile: details, password, wishlist, tickets."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import flash
from app.deps import CsrfDep, FormDep, PageContext, SessionDep, CurrentUser
from app.i18n import translate
from app.schemas.auth import PasswordChangeIn, ProfileUpdateIn
from app.services import auth as auth_service
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.services import support as support_service
from app.services import wishlist as wishlist_service
from app.templating import render

router = APIRouter(prefix="/profile")


def _error_key(code: str) -> str:
    return {
        "EMAIL_TAKEN": "auth.errors.email_taken",
        "BAD_CURRENT_PASSWORD": "auth.errors.bad_current_password",
        "PASSWORD_MISMATCH": "auth.errors.password_mismatch",
    }.get(code, "auth.errors.validation")


@router.get("", name="profile")
async def profile(request: Request, session: SessionDep, ctx: PageContext, user: CurrentUser):
    orders = await orders_service.list_for_user(session, user.id)
    spent = sum((Decimal(order.total) for order in orders), Decimal("0.00"))
    wishlist_items = await wishlist_service.items(session, user.id)
    tickets = await support_service.list_for_user(session, user.id)
    chats = await chat_service.list_for_user(session, user.id)
    return await render(
        request,
        "pages/profile/index.html",
        orders=orders,
        spent=spent,
        wishlist_items=wishlist_items,
        tickets=tickets,
        chats=chats,
        form_data={},
        errors={},
        crumbs=[(translate(request.state.locale, "profile.title"), None)],
    )


@router.post("", name="profile_update")
async def profile_update(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    user: CurrentUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    try:
        data = ProfileUpdateIn(**payload)
    except ValidationError as exc:
        errors = {str(e["loc"][0]): str(e["msg"]) for e in exc.errors() if e["loc"]}
        return await _profile_error(request, session, user, payload, errors, locale)

    try:
        await auth_service.update_profile(
            session, user, name=data.name, email=data.email, locale=data.locale
        )
    except auth_service.AuthError as exc:
        await session.rollback()
        return await _profile_error(
            request, session, user, payload, {"form": translate(locale, _error_key(exc.code))}, locale
        )

    await session.commit()
    response = RedirectResponse("/profile", status_code=303)
    flash.add(response, translate(locale, "profile.saved"), "success")
    return response


async def _profile_error(request, session, user, payload, errors, locale):
    orders = await orders_service.list_for_user(session, user.id)
    spent = sum((Decimal(order.total) for order in orders), Decimal("0.00"))
    wishlist_items = await wishlist_service.items(session, user.id)
    tickets = await support_service.list_for_user(session, user.id)
    chats = await chat_service.list_for_user(session, user.id)
    return await render(
        request,
        "pages/profile/index.html",
        orders=orders,
        spent=spent,
        wishlist_items=wishlist_items,
        tickets=tickets,
        chats=chats,
        form_data=payload,
        errors=errors,
        status_code=400,
        crumbs=[(translate(locale, "profile.title"), None)],
    )


@router.post("/password", name="profile_password")
async def profile_password(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    user: CurrentUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    response = RedirectResponse("/profile", status_code=303)
    try:
        data = PasswordChangeIn(**payload)
        await auth_service.change_password(
            session,
            user,
            current=data.current_password,
            new=data.new_password,
            confirm=data.new_password_confirm,
        )
        await session.commit()
        flash.add(response, translate(locale, "profile.password.changed"), "success")
    except (ValidationError, auth_service.AuthError) as exc:
        await session.rollback()
        code = exc.code if isinstance(exc, auth_service.AuthError) else "VALIDATION"
        flash.add(response, translate(locale, _error_key(code)), "error")
    return response


@router.get("/wishlist", name="profile_wishlist")
async def profile_wishlist(request: Request, session: SessionDep, ctx: PageContext, user: CurrentUser):
    items = await wishlist_service.items(session, user.id)
    return await render(
        request,
        "pages/profile/wishlist.html",
        items=items,
        crumbs=[
            (translate(request.state.locale, "profile.title"), "/profile"),
            (translate(request.state.locale, "profile.tab.wishlist"), None),
        ],
    )


@router.get("/tickets", name="profile_tickets")
async def profile_tickets(request: Request, session: SessionDep, ctx: PageContext, user: CurrentUser):
    tickets = await support_service.list_for_user(session, user.id)
    return await render(
        request,
        "pages/profile/tickets.html",
        tickets=tickets,
        crumbs=[
            (translate(request.state.locale, "profile.title"), "/profile"),
            (translate(request.state.locale, "profile.tab.tickets"), None),
        ],
    )
