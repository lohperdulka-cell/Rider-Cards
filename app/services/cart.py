"""Server-side cart stored in a signed cookie (no extra DB model needed)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.product import Product

CART_COOKIE = "rc_cart"
CART_MAX_AGE = 60 * 60 * 24 * 30
MAX_QTY_PER_ITEM = 99
MAX_CART_LINES = 50

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="ridercards-cart-v1")


def load_cart(raw: str | None) -> dict[int, int]:
    """Decode the cookie payload into {product_id: qty}. Invalid data -> empty cart."""
    if not raw:
        return {}
    try:
        data: Any = _serializer.loads(raw, max_age=CART_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return {}
    if not isinstance(data, dict):
        return {}
    cart: dict[int, int] = {}
    for key, value in data.items():
        try:
            pid = int(key)
            qty = int(value)
        except (TypeError, ValueError):
            continue
        if pid > 0 and 0 < qty <= MAX_QTY_PER_ITEM:
            cart[pid] = qty
    return cart


def dump_cart(cart: dict[int, int]) -> str:
    return _serializer.dumps({str(k): v for k, v in cart.items() if v > 0})


def add_item(cart: dict[int, int], product_id: int, qty: int = 1) -> dict[int, int]:
    if product_id <= 0:
        return cart
    if product_id not in cart and len(cart) >= MAX_CART_LINES:
        return cart
    new_qty = min(MAX_QTY_PER_ITEM, cart.get(product_id, 0) + max(1, qty))
    cart[product_id] = new_qty
    return cart


def set_item(cart: dict[int, int], product_id: int, qty: int) -> dict[int, int]:
    if qty <= 0:
        cart.pop(product_id, None)
        return cart
    cart[product_id] = min(MAX_QTY_PER_ITEM, qty)
    return cart


def remove_item(cart: dict[int, int], product_id: int) -> dict[int, int]:
    cart.pop(product_id, None)
    return cart


def cart_quantity(cart: dict[int, int]) -> int:
    return sum(cart.values())


async def get_cart_items(session: AsyncSession, cart: dict[int, int]) -> list[dict[str, Any]]:
    """Join the cookie cart with live product rows, dropping vanished products."""
    if not cart:
        return []
    result = await session.execute(
        select(Product).where(
            Product.id.in_(list(cart.keys())), Product.is_active.is_(True), Product.is_deleted.is_(False)
        )
    )
    products = {p.id: p for p in result.scalars().all()}
    items: list[dict[str, Any]] = []
    for pid, qty in cart.items():
        product = products.get(pid)
        if product is None:
            continue
        available = product.stock
        items.append(
            {
                "product": product,
                "qty": qty,
                "available": available,
                "over_stock": qty > available,
                "subtotal": Decimal(product.price) * qty,
            }
        )
    return items


def cart_total(items: list[dict[str, Any]]) -> Decimal:
    return sum((item["subtotal"] for item in items), Decimal("0.00"))


def cart_count_from_cookie(raw: str | None) -> int:
    return cart_quantity(load_cart(raw))
