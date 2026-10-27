"""Order lifecycle: creation from cart, status transitions, reporting."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.chat import Chat, Message, SenderRole
from app.models.order import ORDER_STATUS_META, Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User

MAX_ITEMS_PER_ORDER = 50


class OrderError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def status_text(status: OrderStatus | str, locale: str) -> str:
    key = status.value if isinstance(status, OrderStatus) else str(status)
    meta = ORDER_STATUS_META.get(key, {})
    return meta.get("en" if locale == "en" else "ru", key)


def system_order_message(order: Order, locale: str = "ru") -> str:
    label = status_text(order.status, locale)
    total = f"{Decimal(order.total):,.2f}".replace(",", " ").replace(".", ",")
    if locale == "en":
        return f"Order #{order.id} created, status: {label}. Total: {total} {order.currency}"
    return f"Заказ #{order.id} создан, статус: {label}. Сумма: {total} ₽"


def system_status_message(order: Order, locale: str = "ru") -> str:
    label = status_text(order.status, locale)
    if locale == "en":
        return f"Order #{order.id} status changed to: {label}"
    return f"Статус заказа #{order.id} изменён на: «{label}»"


async def create_from_cart(
    session: AsyncSession,
    *,
    user: User,
    cart: dict[int, int],
    contact: str,
    address: str,
    note: str = "",
) -> Order:
    """Create the order, its lines and the 1:1 support chat with a system message."""
    if not cart:
        raise OrderError("EMPTY_CART")
    if len(cart) > MAX_ITEMS_PER_ORDER:
        raise OrderError("TOO_MANY_ITEMS")

    result = await session.execute(
        select(Product).where(
            Product.id.in_(list(cart.keys())),
            Product.is_active.is_(True),
            Product.is_deleted.is_(False),
        )
    )
    products = {p.id: p for p in result.scalars().all()}
    if not products:
        raise OrderError("EMPTY_CART")

    order = Order(
        user_id=user.id,
        status=OrderStatus.pending,
        currency=settings.currency,
        contact=contact.strip(),
        address=address.strip(),
        note=note.strip(),
    )
    session.add(order)
    await session.flush()

    total = Decimal("0.00")
    for pid, qty in cart.items():
        product = products.get(pid)
        if product is None:
            continue
        qty = min(qty, max(1, product.stock))
        line = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name_ru,
            product_slug=product.slug,
            cover_image=product.cover_image,
            qty=qty,
            price_at_purchase=Decimal(product.price),
        )
        session.add(line)
        product.stock = max(0, product.stock - qty)
        total += Decimal(product.price) * qty

    order.total = total
    chat = Chat(order_id=order.id, user_id=user.id)
    session.add(chat)
    await session.flush()

    session.add(
        Message(
            chat_id=chat.id,
            sender_id=None,
            sender_role=SenderRole.system,
            text=system_order_message(order, user.locale or settings.default_locale),
        )
    )
    await session.flush()
    await session.refresh(order, attribute_names=["items"])
    return order


async def get_for_user(session: AsyncSession, order_id: int, user_id: int) -> Order | None:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    return (await session.execute(stmt)).scalars().first()


async def get_any(session: AsyncSession, order_id: int) -> Order | None:
    stmt = (
        select(Order).options(selectinload(Order.items), selectinload(Order.user)).where(Order.id == order_id)
    )
    return (await session.execute(stmt)).scalars().first()


async def list_for_user(session: AsyncSession, user_id: int) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def list_orders(
    session: AsyncSession,
    *,
    status: str = "",
    query: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Order], int]:
    stmt = select(Order).options(selectinload(Order.items), selectinload(Order.user))
    count_stmt = select(func.count(Order.id))
    if status:
        stmt = stmt.where(Order.status == status)
        count_stmt = count_stmt.where(Order.status == status)
    if query:
        needle = f"%{query.strip().lower()}%"
        if query.strip().isdigit():
            stmt = stmt.where(Order.id == int(query.strip()))
            count_stmt = count_stmt.where(Order.id == int(query.strip()))
        else:
            stmt = stmt.join(User, Order.user_id == User.id).where(func.lower(User.email).like(needle))
            count_stmt = count_stmt.join(User, Order.user_id == User.id).where(
                func.lower(User.email).like(needle)
            )
    if date_from:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
        count_stmt = count_stmt.where(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        end = datetime.combine(date_to, datetime.min.time()) + timedelta(days=1)
        stmt = stmt.where(Order.created_at < end)
        count_stmt = count_stmt.where(Order.created_at < end)
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    stmt = stmt.order_by(Order.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().unique().all()), total


async def set_status(
    session: AsyncSession, order: Order, new_status: OrderStatus, *, locale: str = "ru", notify: bool = True
) -> Message | None:
    """Change the status and push a system message into the order chat."""
    if order.status == new_status:
        return None
    order.status = new_status
    await session.flush()
    if not notify:
        return None
    chat = (await session.execute(select(Chat).where(Chat.order_id == order.id))).scalars().first()
    if chat is None:
        return None
    message = Message(
        chat_id=chat.id,
        sender_id=None,
        sender_role=SenderRole.system,
        text=system_status_message(order, locale),
    )
    session.add(message)
    await session.flush()
    return message


async def cancel_by_user(session: AsyncSession, order: Order, *, locale: str = "ru") -> None:
    if order.status not in {OrderStatus.pending, OrderStatus.paid}:
        raise OrderError("CANNOT_CANCEL")
    await set_status(session, order, OrderStatus.cancelled, locale=locale)


async def stats_summary(session: AsyncSession) -> dict[str, Any]:
    """KPI numbers for the admin dashboard."""
    now = datetime.now(UTC)
    start_today = datetime.combine(now.date(), datetime.min.time())
    start_week = start_today - timedelta(days=6)

    async def _count(stmt) -> int:
        return int((await session.execute(stmt)).scalar_one() or 0)

    orders_today = await _count(select(func.count(Order.id)).where(Order.created_at >= start_today))
    orders_week = await _count(select(func.count(Order.id)).where(Order.created_at >= start_week))
    revenue_total = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status.notin_([OrderStatus.cancelled])
            )
        )
    ).scalar_one()
    revenue_week = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.created_at >= start_week, Order.status.notin_([OrderStatus.cancelled])
            )
        )
    ).scalar_one()
    new_users = await _count(
        select(func.count(User.id)).where(User.created_at >= start_week, User.is_admin.is_(False))
    )
    open_chats = await _count(select(func.count(Chat.id)).where(Chat.is_closed.is_(False)))
    unread_messages = await _count(
        select(func.count(Message.id)).where(
            Message.sender_role == SenderRole.user, Message.read_at.is_(None)
        )
    )
    low_stock = await _count(
        select(func.count(Product.id)).where(
            Product.is_deleted.is_(False), Product.is_active.is_(True), Product.stock <= 3
        )
    )
    total_orders = await _count(select(func.count(Order.id)))
    avg_order = (
        await session.execute(
            select(func.coalesce(func.avg(Order.total), 0)).where(
                Order.status.notin_([OrderStatus.cancelled])
            )
        )
    ).scalar_one()

    return {
        "orders_today": orders_today,
        "orders_week": orders_week,
        "total_orders": total_orders,
        "revenue_total": Decimal(revenue_total or 0),
        "revenue_week": Decimal(revenue_week or 0),
        "avg_order": Decimal(avg_order or 0),
        "new_users_week": new_users,
        "open_chats": open_chats,
        "unread_messages": unread_messages,
        "low_stock": low_stock,
    }


async def daily_series(session: AsyncSession, days: int = 14) -> list[dict[str, Any]]:
    """Orders and revenue per day for the dashboard chart."""
    now = datetime.now(UTC)
    start = datetime.combine((now - timedelta(days=days - 1)).date(), datetime.min.time())
    stmt = (
        select(
            func.date(Order.created_at).label("day"),
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
        )
        .where(Order.created_at >= start)
        .group_by("day")
        .order_by("day")
    )
    rows = {str(row.day): row for row in (await session.execute(stmt)).all()}
    series: list[dict[str, Any]] = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date()
        row = rows.get(day.isoformat())
        series.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%d.%m"),
                "orders": int(row.orders) if row else 0,
                "revenue": float(row.revenue) if row else 0.0,
            }
        )
    return series


async def low_stock_products(session: AsyncSession, limit: int = 8) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.is_deleted.is_(False), Product.is_active.is_(True), Product.stock <= 3)
        .order_by(Product.stock.asc(), Product.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def recent_orders(session: AsyncSession, limit: int = 8) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .order_by(Order.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().unique().all())


def orders_to_csv(orders: list[Order]) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        ["id", "created_at", "status", "user_email", "items", "total", "currency", "contact", "address"]
    )
    for order in orders:
        writer.writerow(
            [
                order.id,
                order.created_at.strftime("%Y-%m-%d %H:%M") if order.created_at else "",
                order.status.value,
                order.user.email if order.user else "",
                order.items_count,
                f"{Decimal(order.total):.2f}",
                order.currency,
                order.contact,
                order.address.replace("\n", " "),
            ]
        )
    return buffer.getvalue()
