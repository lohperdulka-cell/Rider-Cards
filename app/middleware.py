"""HTTP middleware: security headers, locale, CSRF cookie, request context."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.i18n import normalize_locale
from app.security import generate_csrf_token

logger = logging.getLogger("ridercards.http")

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the hardening headers required by the security checklist."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if settings.session_cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Locale resolution, CSRF cookie bootstrap and request timing."""

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()

        lang = request.query_params.get("lang")
        if lang:
            locale = normalize_locale(lang)
            request.state.locale_from_query = locale
        else:
            locale = normalize_locale(request.cookies.get("rc_lang"))
        request.state.locale = locale

        csrf_token = request.cookies.get(settings.csrf_cookie_name) or generate_csrf_token()
        request.state.csrf_token = csrf_token

        response: Response = await call_next(request)

        if lang:
            response.set_cookie(
                "rc_lang",
                normalize_locale(lang),
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=settings.session_cookie_secure,
                path="/",
            )
        if request.cookies.get(settings.csrf_cookie_name) != csrf_token:
            response.set_cookie(
                settings.csrf_cookie_name,
                csrf_token,
                httponly=False,  # double-submit cookie must be readable by the form
                samesite="lax",
                secure=settings.session_cookie_secure,
                path="/",
                max_age=60 * 60 * 12,
            )

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"
        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Compact access log (level-configurable) without leaking query secrets."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static"):
            return response
        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
