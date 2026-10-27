"""News article model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class News(Base, TimestampMixin):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    title_ru: Mapped[str] = mapped_column(String(240), nullable=False)
    title_en: Mapped[str] = mapped_column(String(240), nullable=False)
    excerpt_ru: Mapped[str] = mapped_column(Text, default="", nullable=False)
    excerpt_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_ru: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cover_image: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def localized_title(self, locale: str) -> str:
        return self.title_en if locale == "en" else self.title_ru

    def localized_excerpt(self, locale: str) -> str:
        return self.excerpt_en if locale == "en" else self.excerpt_ru

    def localized_body(self, locale: str) -> str:
        return self.body_en if locale == "en" else self.body_ru

    def __repr__(self) -> str:  # pragma: no cover
        return f"<News {self.slug}>"
