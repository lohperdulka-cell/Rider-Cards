"""Admin support ticket queue."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import flash
from app.deps import AdminUser, CsrfDep, FormDep, PageContext, SessionDep
from app.i18n import translate
from app.models.support import TicketStatus
from app.services import support as support_service
from app.templating import render

from app.routers.admin._common import log_action

router = APIRouter(prefix="/admin/tickets")


@router.get("", name="admin_tickets")
async def tickets_list(
    request: Request, session: SessionDep, ctx: PageContext, admin: AdminUser
):
    tickets = await support_service.list_all(session, limit=200)
    return await render(
        request,
        "admin/tickets/list.html",
        admin=admin,
        tickets=tickets,
        statuses=[status.value for status in TicketStatus],
    )


@router.post("/{ticket_id}", name="admin_ticket_update")
async def ticket_update(
    request: Request,
    ticket_id: int,
    session: SessionDep,
    ctx: PageContext,
    admin: AdminUser,
    form: FormDep,
    _csrf: CsrfDep,
):
    ticket = await support_service.get(session, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="TICKET_NOT_FOUND")

    status_value = str(form.get("status", ""))
    if status_value in {s.value for s in TicketStatus}:
        await support_service.set_status(session, ticket, TicketStatus(status_value))
    ticket.answer = str(form.get("answer", ""))[:4000]

    await log_action(
        session,
        request,
        actor=admin,
        action="ticket.update",
        entity="ticket",
        entity_id=ticket.id,
    )
    await session.commit()
    response = RedirectResponse("/admin/tickets", status_code=303)
    flash.add(response, translate(request.state.locale, "admin.ticket.answer_sent"), "success")
    return response
