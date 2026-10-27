"""Catalog query filters."""

from dataclasses import dataclass, field
from decimal import Decimal

SORT_OPTIONS = {
    "new": "created_at_desc",
    "price_asc": "price_asc",
    "price_desc": "price_desc",
    "popular": "popular",
    "name": "name_asc",
}


@dataclass(slots=True)
class CatalogFilters:
    q: str = ""
    category: str = ""
    brand: list[str] = field(default_factory=list)
    rarity: list[str] = field(default_factory=list)
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool = False
    sort: str = "new"
    page: int = 1
    per_page: int = 12

    @property
    def order_by(self) -> str:
        return SORT_OPTIONS.get(self.sort, "created_at_desc")

    @property
    def offset(self) -> int:
        return max(0, (self.page - 1) * self.per_page)

    def as_query(self) -> dict[str, str | list[str]]:
        params: dict[str, str | list[str]] = {}
        if self.q:
            params["q"] = self.q
        if self.category:
            params["category"] = self.category
        if self.brand:
            params["brand"] = self.brand
        if self.rarity:
            params["rarity"] = self.rarity
        if self.min_price is not None:
            params["min_price"] = str(self.min_price)
        if self.max_price is not None:
            params["max_price"] = str(self.max_price)
        if self.in_stock:
            params["in_stock"] = "1"
        if self.sort and self.sort != "new":
            params["sort"] = self.sort
        return params
