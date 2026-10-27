"""Password hashing, signed sessions and CSRF helpers."""

from __future__ import annotations

import hmac
import secrets
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="ridercards-session-v1")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return pwd_context.needs_update(password_hash)
    except ValueError:
        return False


def sign_session(data: dict[str, Any]) -> str:
    return _serializer.dumps(data)


def load_session(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=settings.session_max_age)
    except (BadSignature, SignatureExpired):
        return None
    return data if isinstance(data, dict) else None


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_tokens_match(cookie_token: str, form_token: str) -> bool:
    if not cookie_token or not form_token:
        return False
    return hmac.compare_digest(cookie_token, form_token)


def safe_next_url(value: str | None, default: str = "/") -> str:
    """Only allow same-origin relative redirects (blocks open redirects)."""
    if not value:
        return default
    value = value.strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return default
    return value
