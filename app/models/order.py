"""Order and order line models."""

import enum
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


ORDER_STATUS_META: dict[str, dict[str, str]] = {
    "pending": {"ru": "Ожидает оплаты", "en": "Awaiting payment", "color": "amber"},
    "paid": {"ru": "Оплачен", "en": "Paid", "color": "lime"},
    "processing": {"ru": "В сборке", "en": "Processing", "color": "sky"},
    "shipped": {"ru": "Отправлен", "en": "Shipped", "color": "violet"},
    "delivered": {"ru": "Доставлен", "en": "Delivered", "color": "emerald"},
    "cancelled": {"ru": "Отменён", "en": "Cancelled", "color": "rose"},
}


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20), default=OrderStatus.pending, nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="RUB", nullable=False)
    address: Mapped[str] = mapped_column(Text, default="", nullable=False)
    contact: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    chat = relationship(
        "Chat", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def status_meta(self) -> dict[str, str]:
        return ORDER_STATUS_META.get(self.status.value, {})

    @property
    def status_label(self) -> dict[str, str]:
        return ORDER_STATUS_META.get(self.status.value, {})

    @property
    def items_count(self) -> int:
        return sum(item.qty for item in self.items)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Order {self.id} {self.status.value}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    product_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    cover_image: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    qty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price_at_purchase: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )

    order = relationship("Order", back_populates="items")
    product = relationship("Product", lazy="selectin")

    @property
    def subtotal(self) -> Decimal:
        return self.price_at_purchase * self.qty

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OrderItem {self.id} x{self.qty}>"
