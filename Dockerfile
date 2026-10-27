# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# uv resolves and installs from pyproject.toml much faster than pip.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Only what the runtime needs: the editable install resolves `app` back to
# /app/app, so templates, static files and translations are read from here.
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# [postgres] pulls in asyncpg; the default SQLite driver ships with the app deps.
RUN uv pip install --system -e ".[postgres]"

# Run unprivileged. Uploads and the SQLite file need write access, so the app
# tree is owned by that user.
RUN useradd --create-home --uid 1000 rider \
    && mkdir -p /app/data /app/app/static/uploads \
    && chown -R rider:rider /app
USER rider

EXPOSE 8000

# Render injects PORT; --proxy-headers makes request.url reflect the public
# https scheme instead of the container's internal http.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
