"""News list and article pages."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.deps import PageContext, SessionDep
from app.services import news as news_service
from app.templating import render

router = APIRouter(prefix="/news")

PER_PAGE = 9


@router.get("", name="news_list")
async def news_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    page: int = Query(default=1, ge=1, le=200),
):
    offset = (page - 1) * PER_PAGE
    items = await news_service.published(session, limit=PER_PAGE, offset=offset)
    total = await news_service.published_count(session)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    locale = request.state.locale
    return await render(
        request,
        "pages/news_list.html",
        items=items,
        page=page,
        pages=pages,
        total=total,
        crumbs=[(("Новости" if locale == "ru" else "News"), None)],
    )


@router.get("/{slug}", name="news_detail")
async def news_detail(request: Request, slug: str, session: SessionDep, ctx: PageContext):
    item = await news_service.get_by_slug(session, slug)
    if item is None:
        raise HTTPException(status_code=404, detail="NEWS_NOT_FOUND")
    await news_service.increment_views(session, item)
    related = [n for n in await news_service.latest(session, limit=4) if n.id != item.id][:3]
    locale = request.state.locale
    return await render(
        request,
        "pages/news_detail.html",
        item=item,
        related=related,
        crumbs=[
            (("Новости" if locale == "ru" else "News"), "/news"),
            (item.localized_title(locale), None),
        ],
    )
