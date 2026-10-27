"""Admin dashboard: KPI cards, chart payload, recent activity."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.deps import AdminUser, PageContext, SessionDep
from app.models.audit import AuditLog
from app.models.user import User
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.templating import render

router = APIRouter(prefix="/admin")


@router.get("", name="admin_dashboard")
async def dashboard(request: Request, session: SessionDep, ctx: PageContext, admin: AdminUser):
    stats = await orders_service.stats_summary(session)
    series = await orders_service.daily_series(session, days=14)
    recent_orders = await orders_service.recent_orders(session, limit=8)
    low_stock = await orders_service.low_stock_products(session, limit=6)
    unread_chats = await chat_service.list_for_admin(session, only_unread=True, limit=6)

    users_stmt = select(User).where(User.is_admin.is_(False)).order_by(User.id.desc()).limit(6)
    recent_users = list((await session.execute(users_stmt)).scalars().all())

    audit_stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(8)
    audit_entries = list((await session.execute(audit_stmt)).scalars().unique().all())

    return await render(
        request,
        "admin/dashboard.html",
        admin=admin,
        stats=stats,
        series=series,
        series_json=json.dumps(series, ensure_ascii=False),
        recent_orders=recent_orders,
        recent_users=recent_users,
        low_stock=low_stock,
        unread_chats=unread_chats,
        audit_entries=audit_entries,
    )
