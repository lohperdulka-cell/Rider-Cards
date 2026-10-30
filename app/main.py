"""RiderCards FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import create_async_engine

from app import __version__
from app.config import STATIC_DIR, settings
from app.db.base import Base
from app.db.session import engine, session_scope
from app.middleware import RequestContextMiddleware, RequestLogMiddleware, SecurityHeadersMiddleware
from app.routers import (
    auth,
    cart,
    catalog,
    chat,
    checkout,
    errors,
    home,
    news,
    orders,
    pages,
    product,
    profile,
    wishlist,
)
from app.routers.admin import admin_router
from app.ws import chat as ws_chat

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ridercards")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)


async def _bootstrap() -> None:
    """Create tables and the default admin on first boot (dev convenience).

    DDL goes through the direct URL: Neon's pooler runs PgBouncer in
    transaction mode, where ``CREATE TABLE`` can land on a different backend
    than the one that later reads the schema.
    """
    migration_engine = create_async_engine(settings.migration_url, echo=False, future=True)
    try:
        async with migration_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await migration_engine.dispose()
    async with session_scope() as session:
        from app.services.auth import ensure_default_admin

        admin = await ensure_default_admin(session)
        if admin is not None:
            logger.info("default admin ready: %s", admin.email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _bootstrap()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RiderCards",
        version=__version__,
        description="Premium playing cards store",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(home.router)
    app.include_router(catalog.router)
    app.include_router(product.router)
    app.include_router(news.router)
    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(cart.router)
    app.include_router(checkout.router)
    app.include_router(orders.router)
    app.include_router(profile.router)
    app.include_router(wishlist.router)
    app.include_router(chat.router)
    app.include_router(admin_router)
    app.include_router(ws_chat.router)

    errors.register_error_handlers(app)
    _register_rate_limits(app)
    return app


def _register_rate_limits(app: FastAPI) -> None:
    """Attach slowapi limits to the abuse-prone endpoints by route name."""

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        from app.i18n import translate

        locale = getattr(request.state, "locale", settings.default_locale)
        message = translate(locale, "auth.errors.rate_limited")
        if "text/html" in request.headers.get("accept", "") and not request.url.path.startswith(
            ("/login", "/register")
        ):
            return HTMLResponse(
                f'<div class="rc-card p-6 text-sm text-rose-200">{message}</div>', status_code=429
            )
        return JSONResponse({"detail": message}, status_code=429)


app = create_app()


# Rate limits are declared on the routers themselves to keep the wiring explicit.
def _apply_limits() -> None:
    limits = {
        "login_submit": "10/minute",
        "register_submit": "5/minute",
        "support_submit": "5/minute",
        "chat_send": "30/minute",
    }
    for route in app.routes:
        name = getattr(route, "name", "")
        if name in limits:
            endpoint = route.endpoint  # type: ignore[attr-defined]
            route.endpoint = limiter.limit(limits[name])(endpoint)  # type: ignore[attr-defined]


_apply_limits()
