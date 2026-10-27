"""Server-side cart with HTMX-friendly partial updates.

The cart itself lives in a signed cookie (`rc_cart`), so guests can fill it and only
need an account at checkout. Prices and stock always come from the database.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.deps import CsrfDep, PageContext, SessionDep
from app.i18n import translate
from app.models.product import Product
from app.services import cart as cart_service
from app.templating import render, render_partial

router = APIRouter(prefix="/cart")


def _cart(request: Request) -> dict[int, int]:
    return cart_service.load_cart(request.cookies.get(cart_service.CART_COOKIE))


def _save(response, cart: dict[int, int]) -> None:
    response.set_cookie(
        cart_service.CART_COOKIE,
        cart_service.dump_cart(cart),
        max_age=cart_service.CART_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def _is_json(request: Request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.headers.get(
        "accept", ""
    ).startswith("application/json")


def _is_htmx(request: Request) -> bool:
    return "HX-Request" in request.headers


async def _cart_context(session, cart: dict[int, int]) -> dict:
    items = await cart_service.get_cart_items(session, cart)
    return {
        "items": items,
        "total": cart_service.cart_total(items),
        "cart_count": cart_service.cart_quantity(cart),
    }


@router.get("", name="cart_page")
async def cart_page(request: Request, session: SessionDep, ctx: PageContext):
    cart = _cart(request)
    context = await _cart_context(session, cart)
    return await render(
        request,
        "pages/cart.html",
        crumbs=[(translate(request.state.locale, "cart.title"), None)],
        **context,
    )


@router.post("/add", name="cart_add")
async def cart_add(request: Request, session: SessionDep, ctx: PageContext, _csrf: CsrfDep):
    locale = request.state.locale
    form = await request.form()
    try:
        product_id = int(str(form.get("product_id", "0")))
        qty = int(str(form.get("qty", "1")))
    except (TypeError, ValueError):
        product_id, qty = 0, 1
    qty = max(1, min(qty, cart_service.MAX_QTY_PER_ITEM))

    product = await session.get(Product, product_id)
    if product is None or product.is_deleted or not product.is_active:
        message = translate(locale, "product.not_found")
        if _is_json(request):
            return JSONResponse({"ok": False, "message": message}, status_code=404)
        return RedirectResponse("/catalog", status_code=303)

    cart = cart_service.add_item(_cart(request), product_id, qty)
    context = await _cart_context(session, cart)

    if _is_json(request):
        response = JSONResponse(
            {
                "ok": True,
                "cart_count": context["cart_count"],
                "message": translate(locale, "cart.added"),
                "product": product.localized_name(locale),
            }
        )
    elif _is_htmx(request):
        response = await render_partial(request, "partials/cart_items.html", **context)
    else:
        response = RedirectResponse(request.headers.get("referer", "/cart"), status_code=303)
    _save(response, cart)
    return response


@router.post("/update", name="cart_update")
async def cart_update(request: Request, session: SessionDep, ctx: PageContext, _csrf: CsrfDep):
    form = await request.form()
    cart = _cart(request)
    try:
        product_id = int(str(form.get("product_id", "0")))
        qty = int(str(form.get("qty", "1")))
    except (TypeError, ValueError):
        product_id, qty = 0, 1
    cart_service.set_item(cart, product_id, qty)
    context = await _cart_context(session, cart)

    if _is_htmx(request):
        response = await render_partial(request, "partials/cart_items.html", **context)
    else:
        response = RedirectResponse("/cart", status_code=303)
    _save(response, cart)
    return response


@router.post("/remove", name="cart_remove")
async def cart_remove(request: Request, session: SessionDep, ctx: PageContext, _csrf: CsrfDep):
    form = await request.form()
    try:
        product_id = int(str(form.get("product_id", "0")))
    except (TypeError, ValueError):
        product_id = 0
    cart = cart_service.remove_item(_cart(request), product_id)
    context = await _cart_context(session, cart)

    if _is_htmx(request):
        response = await render_partial(request, "partials/cart_items.html", **context)
    else:
        response = RedirectResponse("/cart", status_code=303)
    _save(response, cart)
    return response


@router.post("/clear", name="cart_clear")
async def cart_clear(request: Request, ctx: PageContext, _csrf: CsrfDep):
    response = RedirectResponse("/cart", status_code=303)
    _save(response, {})
    return response
