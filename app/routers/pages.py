"""Static-ish pages: about, FAQ, support form, sitemap, robots, health."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from pydantic import ValidationError

from app import flash
from app.config import settings
from app.deps import CsrfDep, FormDep, PageContext, SessionDep, UserDep
from app.i18n import translate
from app.schemas.catalog import CatalogFilters
from app.schemas.support import SupportIn
from app.services import products as products_service
from app.services import support as support_service
from app.templating import render

router = APIRouter()


@router.get("/about", name="about")
async def about(request: Request, session: SessionDep, ctx: PageContext):
    locale = request.state.locale
    stats = await products_service.list_products(session, CatalogFilters(), per_page=1)
    return await render(
        request,
        "pages/about.html",
        product_count=stats.total,
        crumbs=[(("О магазине" if locale == "ru" else "About"), None)],
    )


@router.get("/faq", name="faq")
async def faq(request: Request, ctx: PageContext):
    return await render(
        request,
        "pages/faq.html",
        crumbs=[("FAQ", None)],
    )


@router.get("/support", name="support")
async def support_form(request: Request, session: SessionDep, ctx: PageContext):
    locale = request.state.locale
    tickets = []
    if request.state.user is not None:
        tickets = await support_service.list_for_user(session, request.state.user.id)
    return await render(
        request,
        "pages/support.html",
        tickets=tickets,
        form_data={},
        errors={},
        crumbs=[(("Поддержка" if locale == "ru" else "Support"), None)],
    )


@router.post("/support", name="support_submit")
async def support_submit(
    request: Request,
    session: SessionDep,
    ctx: PageContext,
    form: FormDep,
    user: UserDep,
    _csrf: CsrfDep,
):
    locale = request.state.locale
    payload = {k: v for k, v in form.items() if k != "csrf_token"}
    errors: dict[str, str] = {}
    try:
        data = SupportIn(**payload)
    except ValidationError as exc:
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "form"
            errors[field] = str(error["msg"])
        tickets = await support_service.list_for_user(session, user.id) if user else []
        response = await render(
            request,
            "pages/support.html",
            tickets=tickets,
            form_data=payload,
            errors=errors,
            status_code=400,
            crumbs=[(("Поддержка" if locale == "ru" else "Support"), None)],
        )
        return response

    await support_service.create(
        session,
        user=user,
        name=data.name,
        email=data.email,
        subject=data.subject,
        message=data.message,
    )
    await session.commit()

    redirect = RedirectResponse("/support", status_code=303)
    flash.add(redirect, translate(locale, "support.sent"), "success")
    return redirect


@router.get("/sitemap.xml", name="sitemap")
async def sitemap(request: Request, session: SessionDep, ctx: PageContext):
    base = f"{request.url.scheme}://{request.url.netloc}"
    from app.services import news as news_service

    products = await products_service.list_products(session, CatalogFilters(), per_page=500)
    news_items = await news_service.published(session, limit=200)
    static_paths = ["/", "/catalog", "/news", "/about", "/faq", "/support"]

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in static_paths:
        parts.append(
            f"<url><loc>{base}{path}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>"
        )
    for product in products.items:
        parts.append(
            f"<url><loc>{base}/product/{product.slug}</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>"
        )
    for item in news_items:
        parts.append(
            f"<url><loc>{base}/news/{item.slug}</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>"
        )
    parts.append("</urlset>")
    return Response("\n".join(parts), media_type="application/xml")


@router.get("/robots.txt", name="robots")
async def robots(request: Request):
    base = f"{request.url.scheme}://{request.url.netloc}"
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /profile\n"
        "Disallow: /cart\n"
        "Disallow: /checkout\n"
        "Disallow: /chats\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return PlainTextResponse(body)


@router.get("/healthz", name="health")
async def health(session: SessionDep):
    from sqlalchemy import text

    await session.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.env}
