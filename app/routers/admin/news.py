"""Admin news CRUD with publish toggling and cover uploads."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select

from app import flash
from app.deps import AdminUser, CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.models.news import News
from app.routers.admin._common import (
    UploadError,
    as_upload,
    log_action,
    paginate,
    save_upload,
    unique_slug,
)
from app.schemas.admin import NewsIn
from app.services import news as news_service
from app.templating import render

router = APIRouter(prefix="/admin/news")

PER_PAGE = 20


def _clean(payload: dict) -> dict:
    data = dict(payload)
    data.pop("csrf_token", None)
    data["is_published"] = str(data.get("is_published", "")).lower() in {"1", "true", "on", "yes"}
    if not str(data.get("title_en", "")).strip():
        data["title_en"] = data.get("title_ru", "")
    return data


async def _form_context(session, admin, item, payload, errors, status_code=200, request=None):
    return await render(
        request,
        "admin/news/form.html",
        admin=admin,
        item=item,
        form_data=payload,
        errors=errors,
        status_code=status_code,
    )


async def _cover_from_request(request: Request) -> str:
    form = await request.form()
    file = as_upload(form.get("cover_file"))
    if file is None:
        return ""
    try:
        return await save_upload(file, prefix="news")
    except UploadError:
        return ""


@router.get("", name="admin_news")
async def news_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    q: str = Query(default="", max_length=120),
    page: int = Query(default=1, ge=1, le=1000),
):
    stmt = select(News)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(News.title_ru).like(needle), func.lower(News.slug).like(needle)))
    stmt = stmt.order_by(News.id.desc())
    rows, total, pages = await paginate(session, stmt, page=page, per_page=PER_PAGE)
    return await render(
        request,
        "admin/news/list.html",
        admin=admin,
        items=rows,
        total=total,
        pages=pages,
        page=page,
        filters={"q": q},
    )


@router.get("/new", name="admin_news_new")
async def news_new(request: Request, ctx: PageContext, admin: AdminUser):
    return await render(
        request,
        "admin/news/form.html",
        admin=admin,
        item=None,
        form_data={"is_published": False},
        errors={},
    )


@router.post("/new", name="admin_news_create")
async def news_create(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    payload = _clean(form)
    try:
        data = NewsIn(**payload)
    except ValidationError as exc:
        errors = {str(e["loc"][0]): str(e["msg"]) for e in exc.errors() if e["loc"]}
        return await _form_context(session, admin, None, payload, errors, 400, request)

    item = News(
        slug=await unique_slug(session, News, data.slug or data.title_ru),
        title_ru=data.title_ru,
        title_en=data.title_en or data.title_ru,
        excerpt_ru=data.excerpt_ru,
        excerpt_en=data.excerpt_en,
        body_ru=data.body_ru,
        body_en=data.body_en,
    )
    news_service.mark_published(item, data.is_published)
    session.add(item)
    await session.flush()

    cover = await _cover_from_request(request)
    if cover:
        item.cover_image = cover

    await log_action(session, request, actor=admin, action="news.create", entity="news", entity_id=item.id)
    await session.commit()
    response = RedirectResponse("/admin/news", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.created"), "success")
    return response


@router.get("/{news_id}", name="admin_news_edit")
async def news_edit(request: Request, news_id: int, session: SessionDep, ctx: PageContext, admin: AdminUser):
    item = await session.get(News, news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NEWS_NOT_FOUND")
    payload = {
        "title_ru": item.title_ru,
        "title_en": item.title_en,
        "slug": item.slug,
        "excerpt_ru": item.excerpt_ru,
        "excerpt_en": item.excerpt_en,
        "body_ru": item.body_ru,
        "body_en": item.body_en,
        "is_published": item.is_published,
    }
    return await _form_context(session, admin, item, payload, {}, request=request)


@router.post("/{news_id}", name="admin_news_update")
async def news_update(
    request: Request,
    news_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    item = await session.get(News, news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NEWS_NOT_FOUND")
    payload = _clean(form)
    try:
        data = NewsIn(**payload)
    except ValidationError as exc:
        errors = {str(e["loc"][0]): str(e["msg"]) for e in exc.errors() if e["loc"]}
        return await _form_context(session, admin, item, payload, errors, 400, request)

    item.title_ru = data.title_ru
    item.title_en = data.title_en or data.title_ru
    item.excerpt_ru = data.excerpt_ru
    item.excerpt_en = data.excerpt_en
    item.body_ru = data.body_ru
    item.body_en = data.body_en
    if data.slug and data.slug != item.slug:
        item.slug = await unique_slug(session, News, data.slug, exclude_id=item.id)
    news_service.mark_published(item, data.is_published)

    cover = await _cover_from_request(request)
    if cover:
        item.cover_image = cover

    await log_action(session, request, actor=admin, action="news.update", entity="news", entity_id=item.id)
    await session.commit()
    response = RedirectResponse("/admin/news", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.saved"), "success")
    return response


@router.post("/{news_id}/publish", name="admin_news_publish")
async def news_publish(
    request: Request,
    news_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    _csrf: CsrfDep,
):
    item = await session.get(News, news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NEWS_NOT_FOUND")
    news_service.mark_published(item, not item.is_published)
    await log_action(
        session,
        request,
        actor=admin,
        action="news.publish" if item.is_published else "news.unpublish",
        entity="news",
        entity_id=item.id,
    )
    await session.commit()
    response = RedirectResponse("/admin/news", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.saved"), "success")
    return response


@router.post("/{news_id}/delete", name="admin_news_delete")
async def news_delete(
    request: Request,
    news_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    _csrf: CsrfDep,
):
    item = await session.get(News, news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NEWS_NOT_FOUND")
    await session.delete(item)
    await log_action(session, request, actor=admin, action="news.delete", entity="news", entity_id=news_id)
    await session.commit()
    response = RedirectResponse("/admin/news", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.deleted"), "info")
    return response
