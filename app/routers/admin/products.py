"""Admin product CRUD with soft delete, bulk visibility and image uploads."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select

from app import flash
from app.deps import AdminUser, CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.models.category import Category
from app.models.product import Product, Rarity
from app.schemas.admin import ProductIn
from app.services import products as products_service
from app.services.audit import diff_details
from app.templating import render

from app.routers.admin._common import (
    UploadError,
    log_action,
    paginate,
    save_upload,
    unique_slug,
)

router = APIRouter(prefix="/admin/products")

PER_PAGE = 20


def _clean(payload: dict) -> dict:
    data = dict(payload)
    data.pop("csrf_token", None)
    for flag in ("is_featured", "is_active"):
        data[flag] = str(data.get(flag, "")).lower() in {"1", "true", "on", "yes"}
    if not str(data.get("name_en", "")).strip():
        data["name_en"] = data.get("name_ru", "")
    if not str(data.get("category_id", "")).strip():
        data["category_id"] = None
    if not str(data.get("old_price", "")).strip():
        data["old_price"] = None
    return data


async def _form_context(session, admin, product, payload, errors, status_code=200, request=None):
    categories = await products_service.active_categories(session)
    return await render(
        request,
        "admin/products/form.html",
        admin=admin,
        product=product,
        categories=categories,
        rarities=[r.value for r in Rarity],
        form_data=payload,
        errors=errors,
        status_code=status_code,
    )


@router.get("", name="admin_products")
async def products_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=120),
    show_deleted: str = Query(default="", max_length=5),
    page: int = Query(default=1, ge=1, le=1000),
):
    stmt = select(Product)
    if show_deleted in {"1", "true"}:
        stmt = stmt.where(Product.is_deleted.is_(True))
    else:
        stmt = stmt.where(Product.is_deleted.is_(False))
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(Product.name_ru).like(needle), func.lower(Product.slug).like(needle))
        )
    if category:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(
            Category.slug == category
        )
    stmt = stmt.order_by(Product.id.desc())

    rows, total, pages = await paginate(session, stmt, page=page, per_page=PER_PAGE)
    categories = await products_service.active_categories(session)
    return await render(
        request,
        "admin/products/list.html",
        admin=admin,
        products=rows,
        total=total,
        pages=pages,
        page=page,
        categories=categories,
        filters={"q": q, "category": category, "show_deleted": show_deleted},
    )


@router.get("/new", name="admin_product_new")
async def product_new(request: Request, session: SessionDep, ctx: PageContext, admin: AdminUser):
    return await _form_context(
        session, admin, None, {"rarity": "common", "is_active": True}, {}, request=request
    )


@router.post("/new", name="admin_product_create")
async def product_create(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    payload = _clean(form)
    try:
        data = ProductIn(**payload)
    except ValidationError as exc:
        errors = {str(e["loc"][0]): str(e["msg"]) for e in exc.errors() if e["loc"]}
        return await _form_context(session, admin, None, payload, errors, 400, request)

    product = Product(
        slug=await unique_slug(session, Product, data.slug or data.name_ru),
        name_ru=data.name_ru,
        name_en=data.name_en or data.name_ru,
        brand=data.brand,
        category_id=data.category_id,
        price=data.price,
        old_price=data.old_price,
        stock=data.stock,
        rarity=data.rarity,
        description_ru=data.description_ru,
        description_en=data.description_en,
        specs_ru=data.specs_ru,
        specs_en=data.specs_en,
        is_featured=data.is_featured,
        is_active=data.is_active,
    )
    session.add(product)
    await session.flush()

    try:
        await _apply_images(request, product)
    except UploadError as exc:
        await session.rollback()
        return await _form_context(session, admin, None, payload, {"cover": exc.code}, 400, request)

    await log_action(
        session, request, actor=admin, action="product.create", entity="product", entity_id=product.id
    )
    await session.commit()
    response = RedirectResponse("/admin/products", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.created"), "success")
    return response


@router.get("/{product_id}", name="admin_product_edit")
async def product_edit(
    request: Request, product_id: int, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
    payload = {
        "name_ru": product.name_ru,
        "name_en": product.name_en,
        "slug": product.slug,
        "brand": product.brand,
        "category_id": product.category_id,
        "price": product.price,
        "old_price": product.old_price,
        "stock": product.stock,
        "rarity": product.rarity.value,
        "description_ru": product.description_ru,
        "description_en": product.description_en,
        "specs_ru": product.specs_ru,
        "specs_en": product.specs_en,
        "is_featured": product.is_featured,
        "is_active": product.is_active,
    }
    return await _form_context(session, admin, product, payload, {}, request=request)


@router.post("/{product_id}", name="admin_product_update")
async def product_update(
    request: Request,
    product_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")

    payload = _clean(form)
    try:
        data = ProductIn(**payload)
    except ValidationError as exc:
        errors = {str(e["loc"][0]): str(e["msg"]) for e in exc.errors() if e["loc"]}
        return await _form_context(session, admin, product, payload, errors, 400, request)

    before = {"price": str(product.price), "stock": product.stock, "is_active": product.is_active}
    product.name_ru = data.name_ru
    product.name_en = data.name_en or data.name_ru
    product.brand = data.brand
    product.category_id = data.category_id
    product.price = data.price
    product.old_price = data.old_price
    product.stock = data.stock
    product.rarity = data.rarity
    product.description_ru = data.description_ru
    product.description_en = data.description_en
    product.specs_ru = data.specs_ru
    product.specs_en = data.specs_en
    product.is_featured = data.is_featured
    product.is_active = data.is_active
    if data.slug and data.slug != product.slug:
        product.slug = await unique_slug(session, Product, data.slug, exclude_id=product.id)

    try:
        await _apply_images(request, product)
    except UploadError as exc:
        await session.rollback()
        return await _form_context(session, admin, product, payload, {"cover": exc.code}, 400, request)

    after = {"price": str(product.price), "stock": product.stock, "is_active": product.is_active}
    await log_action(
        session,
        request,
        actor=admin,
        action="product.update",
        entity="product",
        entity_id=product.id,
        details=diff_details(before, after),
    )
    await session.commit()
    response = RedirectResponse("/admin/products", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.saved"), "success")
    return response


@router.post("/{product_id}/delete", name="admin_product_delete")
async def product_delete(
    request: Request,
    product_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    _csrf: CsrfDep,
):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
    product.is_deleted = True
    product.is_active = False
    await log_action(
        session,
        request,
        actor=admin,
        action="product.soft_delete",
        entity="product",
        entity_id=product.id,
    )
    await session.commit()
    response = RedirectResponse("/admin/products", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.deleted"), "info")
    return response


@router.post("/{product_id}/restore", name="admin_product_restore")
async def product_restore(
    request: Request,
    product_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    _csrf: CsrfDep,
):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
    product.is_deleted = False
    await log_action(
        session, request, actor=admin, action="product.restore", entity="product", entity_id=product.id
    )
    await session.commit()
    response = RedirectResponse("/admin/products?show_deleted=1", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.saved"), "success")
    return response


@router.post("/bulk", name="admin_products_bulk")
async def products_bulk(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    raw = form.get("ids", [])
    ids: list[int] = []
    for value in raw if isinstance(raw, list) else [raw]:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    action = str(form.get("bulk_action", ""))
    response = RedirectResponse("/admin/products", status_code=303)
    if not ids or action not in {"enable", "disable"}:
        return response

    products = list(
        (await session.execute(select(Product).where(Product.id.in_(ids)))).scalars().all()
    )
    for product in products:
        product.is_active = action == "enable"
    await log_action(
        session,
        request,
        actor=admin,
        action=f"product.bulk_{action}",
        entity="product",
        details=f"ids={ids}",
    )
    await session.commit()
    flash.add(response, translate(request.state.locale, "admin.bulk_done"), "success")
    return response


async def _apply_images(request: Request, product: Product) -> None:
    """Attach uploaded files to the product cover and gallery."""
    form = await request.form()
    cover = form.get("cover_file")
    if cover is not None and getattr(cover, "filename", ""):
        product.cover_image = await save_upload(cover, prefix="cover")

    files = form.getlist("gallery_files")
    gallery_lines = [line.strip() for line in (product.gallery or "").splitlines() if line.strip()]
    for file in files:
        if getattr(file, "filename", ""):
            path = await save_upload(file, prefix="gallery")
            if path not in gallery_lines:
                gallery_lines.append(path)
    product.gallery = "\n".join(gallery_lines[:12])
