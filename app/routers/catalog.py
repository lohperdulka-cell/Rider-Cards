"""Catalog listing with filters, sorting, search and pagination."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Query, Request

from app.deps import PageContext, SessionDep
from app.schemas.catalog import SORT_OPTIONS, CatalogFilters
from app.services import products as products_service
from app.templating import render

router = APIRouter(prefix="/catalog")


def _decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed >= 0 else None


def build_filters(
    q: str = "",
    category: str = "",
    brand: list[str] | None = None,
    rarity: list[str] | None = None,
    min_price: str | None = None,
    max_price: str | None = None,
    in_stock: str | None = None,
    sort: str = "new",
    page: int = 1,
) -> CatalogFilters:
    return CatalogFilters(
        q=(q or "").strip()[:120],
        category=(category or "").strip()[:120],
        brand=[b.strip()[:120] for b in (brand or []) if b.strip()][:20],
        rarity=[r.strip()[:20] for r in (rarity or []) if r.strip()][:20],
        min_price=_decimal(min_price),
        max_price=_decimal(max_price),
        in_stock=in_stock in {"1", "true", "on", "yes"},
        sort=sort if sort in SORT_OPTIONS else "new",
        page=max(1, page),
    )


@router.get("", name="catalog")
async def catalog(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=120),
    brand: list[str] = Query(default_factory=list),
    rarity: list[str] = Query(default_factory=list),
    min_price: str | None = Query(default=None, max_length=20),
    max_price: str | None = Query(default=None, max_length=20),
    in_stock: str | None = Query(default=None, max_length=10),
    sort: str = Query(default="new", max_length=20),
    page: int = Query(default=1, ge=1, le=500),
):
    filters = build_filters(
        q=q,
        category=category,
        brand=brand,
        rarity=rarity,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort=sort,
        page=page,
    )
    result = await products_service.list_products(session, filters, per_page=12)
    categories = await products_service.active_categories(session)
    brands = await products_service.brands(session)
    bounds = await products_service.price_bounds(session)

    return await render(
        request,
        "pages/catalog.html",
        filters=filters,
        result=result,
        categories=categories,
        brands=brands,
        price_bounds=bounds,
        crumbs=[("Каталог" if request.state.locale == "ru" else "Catalog", None)],
    )
