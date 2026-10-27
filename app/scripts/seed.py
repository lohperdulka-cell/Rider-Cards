"""Seed the database with a demo catalogue, news and the default admin.

Usage: ``python -m app.scripts.seed`` (or ``make seed``).
Idempotent: existing slugs are left untouched, so re-running only fills gaps.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.db.base import Base
from app.db.session import engine, session_scope
from app.models.category import Category
from app.models.news import News
from app.models.product import Product, Rarity
from app.services.auth import ensure_default_admin

CATEGORIES = [
    ("collectible", "Коллекционные", "Collectible", "♠", 1,
     "Ограниченные тиражи и редкие колоды для коллекции.",
     "Limited print runs and rare decks for collectors."),
    ("design", "Дизайнерские", "Designer", "♥", 2,
     "Колоды от независимых иллюстраторов и студий.",
     "Decks from independent illustrators and studios."),
    ("classic", "Классические", "Classic", "♦", 3,
     "Проверенная временем классика для игры и тасовки.",
     "Time-tested classics for play and shuffling."),
    ("magic", "Для фокусов", "Magic", "♣", 4,
     "Маркированные, форсированные и gaff-колоды.",
     "Marked, forcing and gaff decks for magicians."),
    ("boardgames", "Для настолок", "Board games", "★", 5,
     "Колоды и тайлы для настольных игр и пати.",
     "Decks and tiles for board games and party play."),
]

PRODUCTS = [
    # slug, name_ru, name_en, brand, category, price, old, stock, rarity, featured
    ("rider-back-royale", "Rider Back Royale", "Rider Back Royale", "RiderCards",
     "classic", "1490.00", "1990.00", 42, Rarity.common, True),
    ("noir-gold-edition", "Noir Gold Edition", "Noir Gold Edition", "Atelier Noir",
     "collectible", "7900.00", None, 12, Rarity.limited, True),
    ("lime-vector", "Lime Vector", "Lime Vector", "Vector Studio",
     "design", "2490.00", "2990.00", 27, Rarity.rare, True),
    ("midnight-gaff", "Midnight Gaff", "Midnight Gaff", "GaffWorks",
     "magic", "3290.00", None, 8, Rarity.epic, True),
    ("tavern-tales", "Tavern Tales", "Tavern Tales", "BoardLoom",
     "boardgames", "1890.00", None, 33, Rarity.common, False),
    ("obsidian-foil", "Obsidian Foil", "Obsidian Foil", "Atelier Noir",
     "collectible", "12900.00", "14900.00", 5, Rarity.legendary, True),
    ("paper-bloom", "Paper Bloom", "Paper Bloom", "Bloom & Co",
     "design", "2190.00", None, 21, Rarity.rare, False),
    ("monte-force", "Monte Force", "Monte Force", "GaffWorks",
     "magic", "2790.00", None, 15, Rarity.epic, False),
    ("standard-pips", "Standard Pips", "Standard Pips", "RiderCards",
     "classic", "990.00", None, 60, Rarity.common, False),
    ("hex-tiles", "Hex Tiles", "Hex Tiles", "BoardLoom",
     "boardgames", "2290.00", None, 18, Rarity.rare, False),
    ("aurora-holo", "Aurora Holo", "Aurora Holo", "Vector Studio",
     "design", "4590.00", "5290.00", 9, Rarity.epic, True),
    ("archive-1987", "Archive 1987", "Archive 1987", "RiderCards",
     "collectible", "9900.00", None, 3, Rarity.limited, False),
]

NEWS = [
    (
        "ridercards-new-line",
        "RiderCards запускает новую линейку карт",
        "RiderCards launches a new card line",
        "Мы объединили лимитированные тиражи и дизайнерские колоды в одну линейку.",
        "We combined limited print runs and designer decks into a single line.",
    ),
    (
        "restock-obsidian-foil",
        "Obsidian Foil снова в наличии",
        "Obsidian Foil is back in stock",
        "Легендарная фольга вернулась — всего 5 колод в наличии.",
        "The legendary foil is back — only 5 decks in stock.",
    ),
    (
        "support-chat-launch",
        "Чат по каждому заказу",
        "A chat for every order",
        "Теперь у каждого заказа есть отдельный чат с поддержкой в реальном времени.",
        "Every order now has its own real-time support chat.",
    ),
]

BODY_RU = (
    "Мы верим, что колода — это не расходник, а предмет коллекции. "
    "Поэтому каждую поставку мы проверяем вручную: смотрим на печать, "
    "срез, покрытие и качество тасовки.\n\n"
    "Линейка объединяет четыре направления: коллекционные, дизайнерские, "
    "классические колоды и карты для фокусов. У каждой категории свой куратор, "
    "который отвечает за подбор и подлинность."
)
BODY_EN = (
    "We believe a deck is a collectible, not a consumable. "
    "That is why every shipment is inspected by hand: print, edges, coating and shuffling.\n\n"
    "The line spans four directions: collectible, designer, classic decks and cards for magic. "
    "Each category has its own curator responsible for selection and authenticity."
)


async def seed_categories(session) -> dict[str, Category]:
    existing = {
        c.slug: c for c in (await session.execute(select(Category))).scalars().all()
    }
    mapping: dict[str, Category] = {}
    for slug, name_ru, name_en, icon, order, desc_ru, desc_en in CATEGORIES:
        category = existing.get(slug)
        if category is None:
            category = Category(
                slug=slug,
                name_ru=name_ru,
                name_en=name_en,
                icon=icon,
                sort_order=order,
                description_ru=desc_ru,
                description_en=desc_en,
                is_active=True,
            )
            session.add(category)
            await session.flush()
        mapping[slug] = category
    return mapping


async def seed_products(session, categories: dict[str, Category]) -> int:
    existing = {p.slug for p in (await session.execute(select(Product))).scalars().all()}
    created = 0
    for (
        slug, name_ru, name_en, brand, category_slug, price, old_price, stock, rarity, featured,
    ) in PRODUCTS:
        if slug in existing:
            continue
        session.add(
            Product(
                slug=slug,
                name_ru=name_ru,
                name_en=name_en,
                brand=brand,
                category_id=categories[category_slug].id if category_slug in categories else None,
                price=Decimal(price),
                old_price=Decimal(old_price) if old_price else None,
                stock=stock,
                rarity=rarity,
                is_featured=featured,
                is_active=True,
                description_ru=BODY_RU,
                description_en=BODY_EN,
                specs_ru="Печать: премиум\nРазмер: 63×88 мм\nПокрытие: air-cushion",
                specs_en="Print: premium\nSize: 63×88 mm\nFinish: air-cushion",
            )
        )
        created += 1
    await session.flush()
    return created


async def seed_news(session) -> int:
    existing = {n.slug for n in (await session.execute(select(News))).scalars().all()}
    created = 0
    now = datetime.now(timezone.utc)
    for slug, title_ru, title_en, excerpt_ru, excerpt_en in NEWS:
        if slug in existing:
            continue
        session.add(
            News(
                slug=slug,
                title_ru=title_ru,
                title_en=title_en,
                excerpt_ru=excerpt_ru,
                excerpt_en=excerpt_en,
                body_ru=BODY_RU,
                body_en=BODY_EN,
                is_published=True,
                published_at=now,
            )
        )
        created += 1
    await session.flush()
    return created


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_scope() as session:
        await ensure_default_admin(session)
        categories = await seed_categories(session)
        products = await seed_products(session, categories)
        news = await seed_news(session)

    print(
        f"seed done: {len(categories)} categories, {products} new products, "
        f"{news} new articles (admin: {settings.admin_email})"
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
