"""Admin user management: search, block/unblock, admin grants, order history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select

from app import flash
from app.deps import AdminUser, CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.models.user import User
from app.services import orders as orders_service
from app.templating import render

from app.routers.admin._common import log_action, paginate

router = APIRouter(prefix="/admin/users")

PER_PAGE = 20


@router.get("", name="admin_users")
async def users_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    q: str = Query(default="", max_length=120),
    page: int = Query(default=1, ge=1, le=1000),
):
    stmt = select(User)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.email).like(needle), func.lower(User.name).like(needle))
        )
    stmt = stmt.order_by(User.id.desc())
    rows, total, pages = await paginate(session, stmt, page=page, per_page=PER_PAGE)
    return await render(
        request,
        "admin/users/list.html",
        admin=admin,
        users=rows,
        total=total,
        pages=pages,
        page=page,
        filters={"q": q},
    )


@router.get("/{user_id}", name="admin_user_detail")
async def user_detail(
    request: Request, user_id: int, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    orders = await orders_service.list_for_user(session, target.id)
    return await render(
        request,
        "admin/users/detail.html",
        admin=admin,
        target_user=target,
        orders=orders,
    )


@router.post("/{user_id}/block", name="admin_user_block")
async def user_block(
    request: Request,
    user_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")

    response = RedirectResponse("/admin/users", status_code=303)
    if target.id == admin.id:
        flash.add(response, translate(locale, "admin.filter"), "error")
        return response

    block = str(form.get("block", "1")) in {"1", "true", "on", "yes"}
    target.is_active = not block
    await log_action(
        session,
        request,
        actor=admin,
        action="user.block" if block else "user.unblock",
        entity="user",
        entity_id=target.id,
    )
    await session.commit()
    flash.add(
        response,
        translate(locale, "admin.users.blocked" if block else "admin.users.unblocked"),
        "success",
    )
    return response


@router.post("/{user_id}/admin", name="admin_user_toggle_admin")
async def user_toggle_admin(
    request: Request,
    user_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")

    response = RedirectResponse("/admin/users", status_code=303)
    if target.id == admin.id:
        flash.add(response, translate(locale, "admin.filter"), "error")
        return response

    target.is_admin = not target.is_admin
    await log_action(
        session,
        request,
        actor=admin,
        action="user.grant_admin" if target.is_admin else "user.revoke_admin",
        entity="user",
        entity_id=target.id,
    )
    await session.commit()
    flash.add(
        response,
        translate(
            locale, "admin.users.admin_granted" if target.is_admin else "admin.users.admin_revoked"
        ),
        "success",
    )
    return response
