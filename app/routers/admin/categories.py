"""Admin category CRUD."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select

from app import flash
from app.deps import AdminUser, CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.models.category import Category
from app.schemas.admin import CategoryIn
from app.templating import render

from app.routers.admin._common import log_action, unique_slug

router = APIRouter(prefix="/admin/categories")


@router.get("", name="admin_categories")
async def categories_list(
    request: Request, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    stmt = select(Category).order_by(Category.sort_order, Category.id)
    categories = list((await session.execute(stmt)).scalars().all())
    return await render(
        request,
        "admin/categories/list.html",
        admin=admin,
        categories=categories,
        form_data={},
        errors={},
    )


@router.post("", name="admin_category_create")
async def category_create(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    payload["is_active"] = str(payload.get("is_active", "")).lower() in {"1", "true", "on", "yes"}
    if not str(payload.get("name_en", "")).strip():
        payload["name_en"] = payload.get("name_ru", "")
    try:
        data = CategoryIn(**payload)
    except ValidationError:
        response = RedirectResponse("/admin/categories", status_code=303)
        flash.add(response, translate(locale, "auth.errors.validation"), "error")
        return response

    category = Category(
        slug=await unique_slug(session, Category, data.slug or data.name_ru),
        name_ru=data.name_ru,
        name_en=data.name_en or data.name_ru,
        description_ru=data.description_ru,
        description_en=data.description_en,
        icon=data.icon,
        is_active=data.is_active,
    )
    session.add(category)
    await session.flush()
    await log_action(
        session, request, actor=admin, action="category.create", entity="category", entity_id=category.id
    )
    await session.commit()
    response = RedirectResponse("/admin/categories", status_code=303)
    flash.add(response, translate(locale, "admin.created"), "success")
    return response


@router.post("/{category_id}", name="admin_category_update")
async def category_update(
    request: Request,
    category_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="CATEGORY_NOT_FOUND")
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    category.name_ru = str(payload.get("name_ru", category.name_ru))[:160]
    category.name_en = str(payload.get("name_en", category.name_en))[:160]
    category.description_ru = str(payload.get("description_ru", ""))[:2000]
    category.description_en = str(payload.get("description_en", ""))[:2000]
    category.icon = str(payload.get("icon", ""))[:40]
    category.is_active = str(payload.get("is_active", "")).lower() in {"1", "true", "on", "yes"}
    try:
        category.sort_order = int(str(payload.get("sort_order", category.sort_order)))
    except (TypeError, ValueError):
        pass
    await log_action(
        session, request, actor=admin, action="category.update", entity="category", entity_id=category.id
    )
    await session.commit()
    response = RedirectResponse("/admin/categories", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.saved"), "success")
    return response
