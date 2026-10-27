"""Home page."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.deps import PageContext, SessionDep
from app.schemas.catalog import CatalogFilters
from app.services import news as news_service
from app.services import products as products_service
from app.templating import render

router = APIRouter()


@router.get("/", name="home")
async def home(request: Request, session: SessionDep, ctx: PageContext):
    categories = await products_service.active_categories(session)
    featured = await products_service.featured(session, limit=8)
    bestsellers = await products_service.bestsellers(session, limit=4)
    latest_news = await news_service.latest(session, limit=3)
    total_products = await products_service.list_products(session, CatalogFilters(), per_page=1)

    return await render(
        request,
        "pages/home.html",
        categories=categories,
        featured=featured,
        bestsellers=bestsellers,
        news=latest_news,
        total_products=total_products.total,
    )
