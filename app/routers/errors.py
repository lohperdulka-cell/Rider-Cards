"""Error handlers and the custom 404/403/500 pages."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.deps import handle_auth_required, handle_forbidden
from app.templating import render


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "") or "HX-Request" in request.headers


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 401:
            return await handle_auth_required(request, exc)
        if exc.status_code == 403:
            return await handle_forbidden(request, exc)
        if exc.status_code == 404:
            if _wants_html(request):
                return await render(request, "pages/errors/404.html", status_code=404)
            return JSONResponse({"detail": exc.detail}, status_code=404)
        if _wants_html(request):
            return await render(
                request,
                "pages/errors/error.html",
                status_code=exc.status_code,
                detail=exc.detail,
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        if _wants_html(request):
            return await render(
                request,
                "pages/errors/error.html",
                status_code=422,
                detail="VALIDATION_ERROR",
            )
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):  # pragma: no cover
        import logging

        logging.getLogger("ridercards").exception("Unhandled error on %s", request.url.path)
        if _wants_html(request):
            return await render(request, "pages/errors/500.html", status_code=500)
        return JSONResponse({"detail": "INTERNAL_ERROR"}, status_code=500)
