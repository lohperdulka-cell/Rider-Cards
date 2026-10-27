"""Admin form schemas."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.product import Rarity


class ProductIn(BaseModel):
    name_ru: str = Field(min_length=2, max_length=200)
    name_en: str = Field(default="", max_length=200)
    slug: str = Field(default="", max_length=160)
    brand: str = Field(default="", max_length=120)
    category_id: int | None = None
    price: Decimal = Field(ge=0, le=10_000_000)
    old_price: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    stock: int = Field(ge=0, le=1_000_000)
    rarity: Rarity = Rarity.common
    description_ru: str = Field(default="", max_length=8000)
    description_en: str = Field(default="", max_length=8000)
    specs_ru: str = Field(default="", max_length=4000)
    specs_en: str = Field(default="", max_length=4000)
    is_featured: bool = False
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def _slugify(cls, v: str) -> str:
        return v.strip().lower()


class NewsIn(BaseModel):
    title_ru: str = Field(min_length=2, max_length=240)
    title_en: str = Field(default="", max_length=240)
    slug: str = Field(default="", max_length=180)
    excerpt_ru: str = Field(default="", max_length=1000)
    excerpt_en: str = Field(default="", max_length=1000)
    body_ru: str = Field(default="", max_length=40000)
    body_en: str = Field(default="", max_length=40000)
    is_published: bool = False


class CategoryIn(BaseModel):
    name_ru: str = Field(min_length=2, max_length=160)
    name_en: str = Field(default="", max_length=160)
    slug: str = Field(default="", max_length=120)
    description_ru: str = Field(default="", max_length=2000)
    description_en: str = Field(default="", max_length=2000)
    icon: str = Field(default="", max_length=40)
    is_active: bool = True
