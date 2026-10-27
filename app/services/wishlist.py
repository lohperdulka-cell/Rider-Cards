"""Wishlist operations."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.wishlist import WishlistItem


async def product_ids(session: AsyncSession, user_id: int) -> set[int]:
    stmt = select(WishlistItem.product_id).where(WishlistItem.user_id == user_id)
    return set((await session.execute(stmt)).scalars().all())


async def items(session: AsyncSession, user_id: int) -> list[WishlistItem]:
    stmt = (
        select(WishlistItem)
        .where(WishlistItem.user_id == user_id)
        .order_by(WishlistItem.id.desc())
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def toggle(session: AsyncSession, user_id: int, product_id: int) -> bool:
    """Add or remove a product. Returns True when it is now in the wishlist."""
    product = await session.get(Product, product_id)
    if product is None or product.is_deleted or not product.is_active:
        return False
    existing = (
        await session.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
            )
        )
    ).scalars().first()
    if existing is not None:
        await session.delete(existing)
        await session.flush()
        return False
    session.add(WishlistItem(user_id=user_id, product_id=product_id))
    await session.flush()
    return True


async def remove(session: AsyncSession, user_id: int, product_id: int) -> None:
    await session.execute(
        delete(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
        )
    )
    await session.flush()


async def count(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func

    stmt = select(func.count(WishlistItem.id)).where(WishlistItem.user_id == user_id)
    return int((await session.execute(stmt)).scalar_one() or 0)
