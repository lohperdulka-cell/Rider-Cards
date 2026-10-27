"""Admin routers, all mounted behind the require_admin dependency."""

from fastapi import APIRouter

from app.routers.admin import (
    audit,
    categories,
    chats,
    dashboard,
    news,
    orders,
    products,
    settings as settings_router,
    tickets,
    users,
)

# Each sub-router carries its own "/admin/..." prefix, so the aggregator stays
# prefix-free and "/admin" itself remains a valid dashboard path.
admin_router = APIRouter(tags=["admin"])

admin_router.include_router(dashboard.router)
admin_router.include_router(orders.router)
admin_router.include_router(products.router)
admin_router.include_router(categories.router)
admin_router.include_router(news.router)
admin_router.include_router(users.router)
admin_router.include_router(chats.router)
admin_router.include_router(tickets.router)
admin_router.include_router(audit.router)
admin_router.include_router(settings_router.router)

__all__ = ["admin_router"]
