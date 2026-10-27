"""Admin order management: list, filters, detail, status change, CSV export."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response

from app import flash
from app.deps import AdminUser, CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.models.order import OrderStatus
from app.services import chat as chat_service
from app.services import orders as orders_service
from app.templating import render

from app.routers.admin._common import log_action

router = APIRouter(prefix="/admin/orders")

STATUSES = [status.value for status in OrderStatus]
PER_PAGE = 20


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("", name="admin_orders")
async def orders_list(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    status: str = Query(default="", max_length=20),
    q: str = Query(default="", max_length=120),
    date_from: str | None = Query(default=None, max_length=10),
    date_to: str | None = Query(default=None, max_length=10),
    page: int = Query(default=1, ge=1, le=1000),
):
    status = status if status in STATUSES else ""
    orders, total = await orders_service.list_orders(
        session,
        status=status,
        query=q,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        limit=PER_PAGE,
        offset=(page - 1) * PER_PAGE,
    )
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    return await render(
        request,
        "admin/orders/list.html",
        admin=admin,
        orders=orders,
        total=total,
        pages=pages,
        page=page,
        statuses=STATUSES,
        filters={"status": status, "q": q, "date_from": date_from or "", "date_to": date_to or ""},
    )


@router.get("/export.csv", name="admin_orders_export")
async def orders_export(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    status: str = Query(default="", max_length=20),
    q: str = Query(default="", max_length=120),
):
    status = status if status in STATUSES else ""
    orders, _ = await orders_service.list_orders(session, status=status, query=q, limit=1000)
    csv_body = orders_service.orders_to_csv(orders)
    return Response(
        "\ufeff" + csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ridercards-orders.csv"'},
    )


@router.get("/{order_id}", name="admin_order_detail")
async def order_detail(
    request: Request, order_id: int, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    order = await orders_service.get_any(session, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="ORDER_NOT_FOUND")
    chat = await chat_service.get_chat_for_order(session, order.id)
    return await render(
        request,
        "admin/orders/detail.html",
        admin=admin,
        order=order,
        chat=chat,
        statuses=STATUSES,
    )


@router.post("/{order_id}/status", name="admin_order_status")
async def order_status(
    request: Request,
    order_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    order = await orders_service.get_any(session, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="ORDER_NOT_FOUND")

    new_status = str(form.get("status", ""))
    response = RedirectResponse(f"/admin/orders/{order_id}", status_code=303)
    if new_status not in STATUSES:
        flash.add(response, translate(locale, "admin.filter"), "error")
        return response

    previous = order.status.value
    order_locale = order.user.locale if order.user else locale
    message = await orders_service.set_status(
        session, order, OrderStatus(new_status), locale=order_locale
    )
    await log_action(
        session,
        request,
        actor=admin,
        action="order.status",
        entity="order",
        entity_id=order.id,
        details=f"{previous} -> {new_status}",
    )
    await session.commit()

    if message is not None:
        chat = await chat_service.get_chat_for_order(session, order_id)
        if chat is not None:
            from app.ws import chat_manager

            await chat_manager.broadcast(
                chat.id, {"type": "message", "message": chat_service.message_payload(message)}
            )
            await chat_manager.broadcast(
                chat.id,
                {
                    "type": "status",
                    "order_id": order.id,
                    "status": order.status.value,
                    "label": order.status_meta,
                },
            )

    flash.add(response, translate(locale, "admin.status_changed"), "success")
    return response
