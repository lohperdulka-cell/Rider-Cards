"""Product (deck of playing cards) model."""

import enum
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Rarity(str, enum.Enum):
    common = "common"
    rare = "rare"
    epic = "epic"
    legendary = "legendary"
    limited = "limited"


RARITY_LABELS = {
    "common": {"ru": "Классика", "en": "Classic"},
    "rare": {"ru": "Редкая", "en": "Rare"},
    "epic": {"ru": "Эпическая", "en": "Epic"},
    "legendary": {"ru": "Легендарная", "en": "Legendary"},
    "limited": {"ru": "Лимитированная", "en": "Limited"},
}


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    description_ru: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    specs_ru: Mapped[str] = mapped_column(Text, default="", nullable=False)
    specs_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rarity: Mapped[Rarity] = mapped_column(
        Enum(Rarity, native_enum=False, length=20), default=Rarity.common, nullable=False
    )
    cover_image: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    gallery: Mapped[str] = mapped_column(Text, default="", nullable=False)  # newline separated paths
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    category = relationship("Category", back_populates="products", lazy="selectin")
    wishlist_items = relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan")

    def localized_name(self, locale: str) -> str:
        return self.name_en if locale == "en" else self.name_ru

    def localized_description(self, locale: str) -> str:
        return self.description_en if locale == "en" else self.description_ru

    def localized_specs(self, locale: str) -> str:
        return self.specs_en if locale == "en" else self.specs_ru

    @property
    def gallery_list(self) -> list[str]:
        return [line.strip() for line in self.gallery.splitlines() if line.strip()]

    @property
    def images(self) -> list[str]:
        images = []
        if self.cover_image:
            images.append(self.cover_image)
        images.extend(img for img in self.gallery_list if img != self.cover_image)
        return images

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def discount_percent(self) -> int:
        if self.old_price and self.old_price > self.price and self.old_price > 0:
            return int(round((1 - (self.price / self.old_price)) * 100))
        return 0

    @property
    def rarity_label(self) -> dict[str, str]:
        return RARITY_LABELS.get(self.rarity.value if isinstance(self.rarity, Rarity) else str(self.rarity), {})

    @property
    def currency(self) -> str:
        """Shop currency; products have no per-item currency."""
        from app.config import settings

        return settings.currency

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.slug}>"
