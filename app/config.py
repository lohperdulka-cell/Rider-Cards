"""Application settings, loaded from environment variables (.env supported)."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"
LOCALES_DIR = BASE_DIR / "i18n"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "dev"
    debug: bool = True
    secret_key: str = "dev-secret-key-change-me-0123456789abcdef"

    database_url: str = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'data' / 'ridercards.db'}"
    # Neon hands out two strings for the same database. They are optional so
    # local and Render setups keep working with a single DATABASE_URL.
    database_url_pooled: str = ""
    database_url_unpooled: str = ""

    session_cookie_name: str = "rc_session"
    session_max_age: int = 60 * 60 * 24 * 14
    cookie_secure: bool = False
    csrf_cookie_name: str = "rc_csrf"

    admin_login: str = "admin"
    admin_password: str = "ChangeMe_StrongPassw0rd!"
    admin_email: str = "admin@ridercards.dev"

    default_locale: str = "ru"
    supported_locales: str = "ru,en"

    currency: str = "RUB"
    support_email: str = "support@ridercards.example"
    shop_name: str = "RiderCards"

    max_upload_size: int = 5 * 1024 * 1024
    allowed_image_types: str = "image/jpeg,image/png,image/webp,image/gif"

    @field_validator("secret_key")
    @classmethod
    def _secret_not_empty(cls, v: str) -> str:
        if not v or len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters long")
        return v

    @field_validator("database_url", "database_url_pooled", "database_url_unpooled")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        """Normalise the connection strings managed hosts hand out.

        Two things break asyncpg: the ``postgres://`` scheme, which SQLAlchemy
        cannot drive asynchronously, and libpq query parameters. ``sslmode`` is
        renamed to asyncpg's ``ssl`` and ``channel_binding`` is dropped, since
        asyncpg rejects both as unexpected keyword arguments. TLS stays
        enforced either way, so the rename loses no protection.
        """
        if not v:
            return v
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        if not v.startswith("postgresql+asyncpg://"):
            return v
        parts = urlsplit(v)
        if not parts.query:
            return v
        query = [
            ("ssl" if key == "sslmode" else key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "channel_binding"
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @property
    def engine_url(self) -> str:
        """URL the request path should use.

        Neon routes ``-pooler`` hostnames through PgBouncer in transaction
        mode, which is what a web app wants: it survives the many short-lived
        connections an async server opens. Schema work goes to
        ``migration_url`` instead, because DDL and session-level state do not
        behave under transaction pooling.
        """
        return self.database_url_pooled or self.database_url

    @property
    def migration_url(self) -> str:
        """Direct, non-pooled URL for DDL and migrations."""
        return self.database_url_unpooled or self.database_url

    @property
    def is_sqlite(self) -> bool:
        return self.engine_url.startswith("sqlite")

    @property
    def locales(self) -> list[str]:
        return [item.strip() for item in self.supported_locales.split(",") if item.strip()]

    @property
    def allowed_image_types_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_image_types.split(",") if item.strip()]

    @property
    def session_cookie_secure(self) -> bool:
        return self.cookie_secure and self.env != "dev"

    @property
    def bcrypt_rounds(self) -> int:
        return 12 if self.env != "dev" else 12


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Ensure runtime directories exist (uploads target and sqlite parent folder).
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
if settings.is_sqlite:
    db_path = settings.database_url.split("///", 1)[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
