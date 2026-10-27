"""Reusable FastAPI dependencies: DB session, auth, CSRF, locale, cart."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.db.session import get_session
from app.i18n import normalize_locale
from app.models.user import User
from app.security import csrf_tokens_match, safe_next_url

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(request: Request, session: SessionDep) -> User | None:
    """Resolve the session cookie into a User (cached on request.state)."""
    if hasattr(request.state, "user"):
        return request.state.user
    user: User | None = None
    token = request.cookies.get(settings.session_cookie_name, "")
    data = None
    if token:
        from app.security import load_session

        data = load_session(token)
    if data and data.get("uid"):
        user = await session.get(User, int(data["uid"]))
        if user and not user.is_active:
            user = None
    request.state.user = user
    if user is not None:
        request.state.locale = user.locale or settings.default_locale
    return user


UserDep = Annotated[User | None, Depends(current_user)]


async def require_user(request: Request, user: UserDep) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTH_REQUIRED")
    return user


CurrentUser = Annotated[User, Depends(require_user)]


async def require_admin(request: Request, user: UserDep) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTH_REQUIRED")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN_ONLY")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def verify_csrf(request: Request) -> None:
    """Double-submit cookie check for unsafe methods."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    form_token = request.headers.get("X-CSRF-Token", "")
    if not form_token:
        content_type = request.headers.get("content-type", "")
        if "form" in content_type or "multipart" in content_type:
            try:
                form = await request.form()
            except Exception:  # noqa: BLE001 - malformed body -> invalid CSRF
                form = None
            if form is not None:
                form_token = str(form.get("csrf_token", "") or "")
    if not csrf_tokens_match(cookie_token, form_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_FAILED")


CsrfDep = Annotated[None, Depends(verify_csrf)]


async def form_data(request: Request) -> dict[str, Any]:
    """Parse a form body once and cache it on request.state."""
    cached = getattr(request.state, "form_data", None)
    if cached is not None:
        return cached
    data: dict[str, Any] = {}
    content_type = request.headers.get("content-type", "")
    if "form" in content_type or "multipart" in content_type:
        form = await request.form()
        data = {key: form[key] for key in form}
    request.state.form_data = data
    return data


FormDep = Annotated[dict[str, Any], Depends(form_data)]


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "HX-Request" in request.headers


async def handle_auth_required(request: Request, exc: StarletteHTTPException) -> Any:
    """Redirect browsers to /login, answer APIs with JSON."""
    if _wants_html(request):
        target = request.url.path
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(
            f"/login?next={safe_next_url(target, '/')}", status_code=status.HTTP_303_SEE_OTHER
        )
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


async def handle_forbidden(request: Request, exc: StarletteHTTPException) -> Any:
    from app.templating import render

    if _wants_html(request):
        return await render(request, "pages/errors/403.html", status_code=403)
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


async def locale_for(request: Request, user: UserDep) -> str:
    """Locale priority: explicit query (?lang=) > cookie > user profile > default."""
    query_lang = request.query_params.get("lang")
    if query_lang:
        return normalize_locale(query_lang)
    cookie_lang = request.cookies.get("rc_lang")
    if cookie_lang:
        return normalize_locale(cookie_lang)
    if user is not None and user.locale:
        return normalize_locale(user.locale)
    return normalize_locale(None)


LocaleDep = Annotated[str, Depends(locale_for)]


async def cart_count_for(request: Request) -> int:
    """Cart badge counter read from the signed cart cookie (no DB round-trip)."""
    from app.services import cart as cart_service

    return cart_service.cart_count_from_cookie(request.cookies.get(cart_service.CART_COOKIE))


CartCountDep = Annotated[int, Depends(cart_count_for)]


async def unread_for_user(request: Request, session: SessionDep, user: UserDep) -> int:
    if user is None or user.is_admin:
        return 0
    from app.services import chat as chat_service

    return await chat_service.unread_count_for_user(session, user.id)


UnreadDep = Annotated[int, Depends(unread_for_user)]


async def unread_for_admin(request: Request, session: SessionDep, user: UserDep) -> int:
    if user is None or not user.is_admin:
        return 0
    from app.services import chat as chat_service

    return await chat_service.unread_count_for_admin(session)


AdminUnreadDep = Annotated[int, Depends(unread_for_admin)]


async def wishlist_ids_for(request: Request, session: SessionDep, user: UserDep) -> set[int]:
    if user is None:
        return set()
    from app.services import wishlist as wishlist_service

    return await wishlist_service.product_ids(session, user.id)


WishlistDep = Annotated[set[int], Depends(wishlist_ids_for)]


async def page_context(
    request: Request,
    session: SessionDep,
    user: UserDep,
    locale: LocaleDep,
    cart_count: CartCountDep,
    unread: UnreadDep,
    admin_unread: AdminUnreadDep,
    wishlist_ids: WishlistDep,
) -> None:
    """Populate request.state with everything the base template needs."""
    request.state.locale = locale
    request.state.user = user
    request.state.cart_count = cart_count
    request.state.unread_count = unread
    request.state.admin_unread_count = admin_unread
    request.state.wishlist_ids = wishlist_ids


PageContext = Annotated[None, Depends(page_context)]


async def session_iter() -> AsyncIterator[AsyncSession]:
    async for s in get_session():
        yield s


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


async def load_user_or_404(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()
