"""Admin settings page (read-only view of env-driven configuration)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import settings
from app.deps import AdminUser, PageContext, SessionDep
from app.templating import render

router = APIRouter(prefix="/admin/settings")


@router.get("", name="admin_settings")
async def settings_page(
    request: Request, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    return await render(
        request,
        "admin/settings.html",
        admin=admin,
        config=settings,
    )
