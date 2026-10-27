"""Product detail page."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.deps import PageContext, SessionDep
from app.services import products as products_service
from app.templating import render

router = APIRouter()


@router.get("/product/{slug}", name="product_detail")
async def product_detail(request: Request, slug: str, session: SessionDep, ctx: PageContext):
    product = await products_service.get_by_slug(session, slug)
    if product is None:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")

    await products_service.increment_views(session, product)
    similar = await products_service.similar(session, product, limit=4)
    locale = request.state.locale

    return await render(
        request,
        "pages/product.html",
        product=product,
        similar=similar,
        crumbs=[
            (("Каталог" if locale == "ru" else "Catalog"), "/catalog"),
            (product.localized_name(locale), None),
        ],
    )
