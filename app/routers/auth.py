"""Registration, login and logout."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import flash
from app.config import settings
from app.deps import CsrfDep, FormDep, PageContext, SessionDep, UserDep
from app.i18n import translate
from app.schemas.auth import LoginIn, RegisterIn
from app.security import safe_next_url, sign_session
from app.services import auth as auth_service
from app.templating import render

router = APIRouter()


def _error_key(code: str) -> str:
    return {
        "EMAIL_TAKEN": "auth.errors.email_taken",
        "BAD_CREDENTIALS": "auth.errors.bad_credentials",
        "ACCOUNT_BLOCKED": "auth.errors.account_blocked",
        "PASSWORD_MISMATCH": "auth.errors.password_mismatch",
        "BAD_CURRENT_PASSWORD": "auth.errors.bad_current_password",
    }.get(code, "auth.errors.validation")


def _set_session(response: RedirectResponse, user_id: int) -> None:
    token = sign_session({"uid": user_id})
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/login", name="login_form")
async def login_form(request: Request, ctx: PageContext, next: str = "/"):
    if request.state.user is not None:
        return RedirectResponse(safe_next_url(next), status_code=303)
    return await render(
        request,
        "pages/auth/login.html",
        form_data={},
        errors={},
        next_url=safe_next_url(next),
    )


@router.post("/login", name="login_submit")
async def login_submit(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    next_url = safe_next_url(str(form.get("next", "/")))
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    try:
        data = LoginIn(**payload)
    except ValidationError:
        return await render(
            request,
            "pages/auth/login.html",
            form_data=payload,
            errors={"form": translate(locale, "auth.errors.validation")},
            next_url=next_url,
            status_code=400,
        )

    try:
        user = await auth_service.authenticate(session, email=data.email, password=data.password)
    except auth_service.AuthError as exc:
        await session.rollback()
        return await render(
            request,
            "pages/auth/login.html",
            form_data={"email": data.email},
            errors={"form": translate(locale, _error_key(exc.code))},
            next_url=next_url,
            status_code=400,
        )

    await session.commit()
    response = RedirectResponse(next_url, status_code=303)
    _set_session(response, user.id)
    flash.add(response, translate(locale, "auth.welcome", name=user.display_name), "success")
    return response


@router.get("/register", name="register_form")
async def register_form(request: Request, ctx: PageContext, next: str = "/"):
    if request.state.user is not None:
        return RedirectResponse(safe_next_url(next), status_code=303)
    return await render(
        request,
        "pages/auth/register.html",
        form_data={},
        errors={},
        next_url=safe_next_url(next),
    )


@router.post("/register", name="register_submit")
async def register_submit(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    next_url = safe_next_url(str(form.get("next", "/")))
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    errors: dict[str, str] = {}
    try:
        data = RegisterIn(**payload)
    except ValidationError as exc:
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "form"
            errors[field] = str(error["msg"])
        return await render(
            request,
            "pages/auth/register.html",
            form_data={k: v for k, v in payload.items() if k != "password"},
            errors=errors,
            next_url=next_url,
            status_code=400,
        )

    if not data.validate_match():
        return await render(
            request,
            "pages/auth/register.html",
            form_data={"name": data.name, "email": data.email},
            errors={"password_confirm": translate(locale, "auth.errors.password_mismatch")},
            next_url=next_url,
            status_code=400,
        )

    try:
        user = await auth_service.register(session, name=data.name, email=data.email, password=data.password)
    except auth_service.AuthError as exc:
        await session.rollback()
        return await render(
            request,
            "pages/auth/register.html",
            form_data={"name": data.name, "email": data.email},
            errors={"form": translate(locale, _error_key(exc.code))},
            next_url=next_url,
            status_code=400,
        )

    await session.commit()
    response = RedirectResponse(next_url, status_code=303)
    _set_session(response, user.id)
    flash.add(response, translate(locale, "auth.welcome", name=user.display_name), "success")
    return response


@router.post("/logout", name="logout")
async def logout(request: Request, ctx: PageContext, _csrf: CsrfDep, user: UserDep):
    locale = request.state.locale
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(settings.session_cookie_name, path="/")
    flash.add(response, translate(locale, "auth.logged_out"), "info")
    return response
