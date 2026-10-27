"""Wishlist toggle endpoint (JSON for the front-end, redirect otherwise)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.deps import CsrfDep, PageContext, SessionDep
from app.i18n import translate
from app.services import wishlist as wishlist_service
from app.templating import render

router = APIRouter(prefix="/wishlist")


@router.get("", name="wishlist_page")
async def wishlist_page(request: Request, session: SessionDep, ctx: PageContext):
    locale = request.state.locale
    user = request.state.user
    if user is None:
        return RedirectResponse("/login?next=/wishlist", status_code=303)
    items = await wishlist_service.items(session, user.id)
    return await render(
        request,
        "pages/profile/wishlist.html",
        items=items,
        crumbs=[(translate(locale, "nav.wishlist"), None)],
    )


@router.post("/toggle", name="wishlist_toggle")
async def wishlist_toggle(
    request: Request, session: SessionDep, ctx: PageContext, _csrf: CsrfDep
):
    locale = request.state.locale
    user = request.state.user
    form = await request.form()
    try:
        product_id = int(str(form.get("product_id", "0")))
    except (TypeError, ValueError):
        product_id = 0

    if user is None:
        message = translate(locale, "checkout.need_login")
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse({"ok": False, "message": message}, status_code=401)
        return RedirectResponse(f"/login?next=/product", status_code=303)

    added = await wishlist_service.toggle(session, user.id, product_id)
    await session.commit()
    count = await wishlist_service.count(session, user.id)
    message = translate(locale, "cart.added" if added else "cart.removed")

    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse(
            {
                "ok": True,
                "added": added,
                "wishlist_count": count,
                "message": translate(locale, "product.wishlist_add")
                if added
                else translate(locale, "product.wishlist_remove"),
            }
        )
    return RedirectResponse(request.headers.get("referer", "/wishlist"), status_code=303)
