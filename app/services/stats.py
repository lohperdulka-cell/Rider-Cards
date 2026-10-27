"""Thin facade so routers can import dashboard statistics from one place."""

from app.services.orders import (  # noqa: F401
    daily_series,
    low_stock_products,
    orders_to_csv,
    recent_orders,
    stats_summary,
)

__all__ = [
    "daily_series",
    "low_stock_products",
    "orders_to_csv",
    "recent_orders",
    "stats_summary",
]
