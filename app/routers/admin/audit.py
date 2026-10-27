"""Admin audit log viewer."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from sqlalchemy import or_, select

from app.deps import AdminUser, PageContext, SessionDep
from app.models.audit import AuditLog
from app.services import audit as audit_service
from app.templating import render

from app.routers.admin._common import paginate

router = APIRouter(prefix="/admin/audit")


@router.get("", name="admin_audit")
async def audit_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    q: str = Query(default="", max_length=120),
    page: int = Query(default=1, ge=1, le=1000),
):
    stmt = select(AuditLog)
    if q:
        needle = f"%{q.strip().lower()}%"
        from sqlalchemy import func

        stmt = stmt.where(
            or_(
                func.lower(AuditLog.action).like(needle),
                func.lower(AuditLog.actor_email).like(needle),
                func.lower(AuditLog.details).like(needle),
            )
        )
    stmt = stmt.order_by(AuditLog.id.desc())
    rows, total, pages = await paginate(session, stmt, page=page, per_page=30)
    return await render(
        request,
        "admin/audit/list.html",
        admin=admin,
        entries=rows,
        total=total,
        pages=pages,
        page=page,
        filters={"q": q},
    )
