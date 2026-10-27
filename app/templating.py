"""Jinja2 environment and the shared render helper."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import flash
from app import __version__
from app.config import STATIC_DIR, TEMPLATES_DIR, settings
from app.i18n import LOCALE_LABELS, SUPPORTED_LOCALES, gettext_for, normalize_locale
from app.models.order import ORDER_STATUS_META
from app.models.product import RARITY_LABELS

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

CURRENCY_SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€"}


def money(value: Decimal | float | int | None, currency: str | None = None) -> str:
    if value is None:
        value = 0
    amount = Decimal(str(value))
    symbol = CURRENCY_SYMBOLS.get(currency or settings.currency, settings.currency)
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {symbol}"


def datetime_fmt(value: Any, fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not value:
        return ""
    try:
        return value.strftime(fmt)
    except AttributeError:
        return str(value)


def date_fmt(value: Any, fmt: str = "%d.%m.%Y") -> str:
    return datetime_fmt(value, fmt)


templates.env.filters["money"] = money
templates.env.filters["dt"] = datetime_fmt
templates.env.filters["date"] = date_fmt
def _asset_version() -> str:
    """Cache-busting token derived from the built CSS bundle."""
    css = STATIC_DIR / "css" / "app.css"
    try:
        stamp = int(css.stat().st_mtime)
    except OSError:
        stamp = 0
    return f"{__version__}-{stamp}"


def urlencode_query(params: dict[str, Any], page: int | None = None) -> str:
    """Build a querystring from a filter dict, expanding list values."""
    from urllib.parse import urlencode

    pairs: list[tuple[str, Any]] = []
    for key, value in (params or {}).items():
        if isinstance(value, (list, tuple, set)):
            pairs.extend((key, item) for item in value)
        elif value not in (None, ""):
            pairs.append((key, value))
    if page is not None:
        pairs.append(("page", page))
    return urlencode(pairs)


templates.env.filters["urlencode_query"] = urlencode_query
templates.env.globals.update(
    settings=settings,
    asset_version=_asset_version(),
    now_year=datetime.now(timezone.utc).year,
    SUPPORTED_LOCALES=SUPPORTED_LOCALES,
    LOCALE_LABELS=LOCALE_LABELS,
    ORDER_STATUS_META=ORDER_STATUS_META,
    RARITY_LABELS=RARITY_LABELS,
    money=money,
)


async def render_partial(
    request: Request,
    template_name: str,
    *,
    status_code: int = 200,
    **context: Any,
) -> HTMLResponse:
    """Render an HTMX partial with the same context the full page would receive."""
    locale = normalize_locale(getattr(request.state, "locale", None))
    base_context: dict[str, Any] = {
        "request": request,
        "user": getattr(request.state, "user", None),
        "locale": locale,
        "t": gettext_for(locale),
        "csrf_token": getattr(request.state, "csrf_token", ""),
        "cart_count": getattr(request.state, "cart_count", 0),
        "unread_count": getattr(request.state, "unread_count", 0),
        "admin_unread_count": getattr(request.state, "admin_unread_count", 0),
        "wishlist_ids": getattr(request.state, "wishlist_ids", set()),
        "current_path": request.url.path,
        "query_params": request.query_params,
    }
    base_context.update(context)
    return templates.TemplateResponse(
        request, template_name, base_context, status_code=status_code
    )


async def render(
    request: Request,
    template_name: str,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    **context: Any,
) -> HTMLResponse:
    """Render a template with the shared layout context injected."""
    locale = normalize_locale(getattr(request.state, "locale", None))
    user = getattr(request.state, "user", None)
    csrf_token = getattr(request.state, "csrf_token", "")

    base_context: dict[str, Any] = {
        "request": request,
        "user": user,
        "locale": locale,
        "t": gettext_for(locale),
        "csrf_token": csrf_token,
        "cart_count": request.state.cart_count if hasattr(request.state, "cart_count") else 0,
        "unread_count": getattr(request.state, "unread_count", 0),
        "admin_unread_count": getattr(request.state, "admin_unread_count", 0),
        "wishlist_ids": getattr(request.state, "wishlist_ids", set()),
        "current_path": request.url.path,
        "query_params": request.query_params,
        "status_code": status_code,
    }
    base_context.update(context)
    response = templates.TemplateResponse(request, template_name, base_context, status_code=status_code)
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    messages = flash.take(request, response)
    if messages:
        response.headers["X-RC-Flashes"] = str(len(messages))
    response.body = _inject_flashes(response, messages)
    return response


def _inject_flashes(response: HTMLResponse, messages: list[dict[str, str]]) -> bytes:
    """Append toast payload for Alpine to pick up on load."""
    import json

    body = response.body
    if not messages or b"</body>" not in body:
        return body
    script = (
        '<script id="rc-flashes" type="application/json">'
        + json.dumps(messages, ensure_ascii=False)
        + "</script></body>"
    ).encode()
    return body.replace(b"</body>", script, 1)
