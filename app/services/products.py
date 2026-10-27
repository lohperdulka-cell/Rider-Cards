"""Catalog queries: filtering, sorting, pagination, featured picks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.product import Product
from app.schemas.catalog import CatalogFilters

DEFAULT_PER_PAGE = 12


@dataclass(slots=True)
class Page:
    items: list[Product]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    def page_range(self, window: int = 2) -> list[int | None]:
        """Compact pagination window with None as an ellipsis marker."""
        pages: list[int | None] = []
        start = max(1, self.page - window)
        end = min(self.pages, self.page + window)
        if start > 1:
            pages.append(1)
            if start > 2:
                pages.append(None)
        pages.extend(range(start, end + 1))
        if end < self.pages:
            if end < self.pages - 1:
                pages.append(None)
            pages.append(self.pages)
        return pages


def _apply_filters(stmt: Select, filters: CatalogFilters) -> Select:
    stmt = stmt.where(Product.is_active.is_(True), Product.is_deleted.is_(False))
    if filters.q:
        needle = f"%{filters.q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.name_ru).like(needle),
                func.lower(Product.name_en).like(needle),
                func.lower(Product.brand).like(needle),
                func.lower(Product.description_ru).like(needle),
            )
        )
    if filters.category:
        stmt = stmt.join(Category, Product.category_id == Category.id, isouter=True).where(
            Category.slug == filters.category
        )
    if filters.brand:
        stmt = stmt.where(Product.brand.in_(filters.brand))
    if filters.rarity:
        stmt = stmt.where(Product.rarity.in_(filters.rarity))
    if filters.min_price is not None:
        stmt = stmt.where(Product.price >= filters.min_price)
    if filters.max_price is not None:
        stmt = stmt.where(Product.price <= filters.max_price)
    if filters.in_stock:
        stmt = stmt.where(Product.stock > 0)
    return stmt


def _apply_sort(stmt: Select, order_by: str) -> Select:
    match order_by:
        case "price_asc":
            return stmt.order_by(Product.price.asc(), Product.id.desc())
        case "price_desc":
            return stmt.order_by(Product.price.desc(), Product.id.desc())
        case "popular":
            return stmt.order_by(Product.views.desc(), Product.id.desc())
        case "name_asc":
            return stmt.order_by(Product.name_ru.asc())
        case _:
            return stmt.order_by(Product.created_at.desc(), Product.id.desc())


async def list_products(
    session: AsyncSession, filters: CatalogFilters, *, per_page: int = DEFAULT_PER_PAGE
) -> Page:
    filters.per_page = per_page
    count_stmt = _apply_filters(select(func.count(Product.id)), filters)
    total = int((await session.execute(count_stmt)).scalar_one() or 0)

    stmt = _apply_filters(select(Product), filters)
    stmt = _apply_sort(stmt, filters.order_by).limit(per_page).offset(filters.offset)
    items = list((await session.execute(stmt)).scalars().unique().all())
    return Page(items=items, total=total, page=filters.page, per_page=per_page)


async def featured(session: AsyncSession, limit: int = 8) -> list[Product]:
    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.is_deleted.is_(False),
            Product.is_featured.is_(True),
        )
        .order_by(Product.created_at.desc())
        .limit(limit)
    )
    items = list((await session.execute(stmt)).scalars().unique().all())
    if items:
        return items
    return await newest(session, limit=limit)


async def newest(session: AsyncSession, limit: int = 8) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.is_deleted.is_(False))
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def bestsellers(session: AsyncSession, limit: int = 4) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.is_deleted.is_(False), Product.stock > 0)
        .order_by(Product.views.desc(), Product.id.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def get_by_slug(session: AsyncSession, slug: str) -> Product | None:
    stmt = select(Product).where(
        Product.slug == slug, Product.is_active.is_(True), Product.is_deleted.is_(False)
    )
    return (await session.execute(stmt)).scalars().first()


async def similar(session: AsyncSession, product: Product, limit: int = 4) -> list[Product]:
    stmt = (
        select(Product)
        .where(
            Product.id != product.id,
            Product.is_active.is_(True),
            Product.is_deleted.is_(False),
            or_(
                Product.category_id == product.category_id,
                Product.rarity == product.rarity,
                Product.brand == product.brand,
            ),
        )
        .order_by(Product.views.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def increment_views(session: AsyncSession, product: Product) -> None:
    product.views = (product.views or 0) + 1
    await session.flush()


async def brands(session: AsyncSession) -> list[str]:
    stmt = (
        select(Product.brand)
        .where(
            Product.is_active.is_(True),
            Product.is_deleted.is_(False),
            Product.brand != "",
        )
        .distinct()
        .order_by(Product.brand)
    )
    return [row for row in (await session.execute(stmt)).scalars().all() if row]


async def price_bounds(session: AsyncSession) -> tuple[Decimal, Decimal]:
    stmt = select(func.min(Product.price), func.max(Product.price)).where(
        Product.is_active.is_(True), Product.is_deleted.is_(False)
    )
    row = (await session.execute(stmt)).one()
    return (Decimal(row[0] or 0), Decimal(row[1] or 0))


async def active_categories(session: AsyncSession) -> list[Category]:
    stmt = select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.id)
    return list((await session.execute(stmt)).scalars().all())
