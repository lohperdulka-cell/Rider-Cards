"""News queries and CRUD helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import News


async def published(session: AsyncSession, *, limit: int = 9, offset: int = 0) -> list[News]:
    stmt = (
        select(News)
        .where(News.is_published.is_(True))
        .order_by(News.published_at.desc().nullslast(), News.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


async def published_count(session: AsyncSession) -> int:
    stmt = select(func.count(News.id)).where(News.is_published.is_(True))
    return int((await session.execute(stmt)).scalar_one() or 0)


async def latest(session: AsyncSession, limit: int = 3) -> list[News]:
    return await published(session, limit=limit)


async def get_by_slug(session: AsyncSession, slug: str, *, only_published: bool = True) -> News | None:
    stmt = select(News).where(News.slug == slug)
    if only_published:
        stmt = stmt.where(News.is_published.is_(True))
    return (await session.execute(stmt)).scalars().first()


async def get_by_id(session: AsyncSession, news_id: int) -> News | None:
    return await session.get(News, news_id)


async def all_items(session: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[News]:
    stmt = select(News).order_by(News.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def search(session: AsyncSession, query: str, *, limit: int = 100) -> list[News]:
    if not query:
        return await all_items(session, limit=limit)
    needle = f"%{query.strip().lower()}%"
    stmt = (
        select(News)
        .where(or_(func.lower(News.title_ru).like(needle), func.lower(News.slug).like(needle)))
        .order_by(News.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def increment_views(session: AsyncSession, item: News) -> None:
    item.views = (item.views or 0) + 1
    await session.flush()


def mark_published(item: News, published: bool) -> None:
    item.is_published = published
    if published and item.published_at is None:
        item.published_at = datetime.now(UTC)
    if not published:
        item.published_at = None
