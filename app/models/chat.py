"""Order chat and message models."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SenderRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    system = "system"


class Chat(Base, TimestampMixin):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    order = relationship("Order", back_populates="chat")
    user = relationship("User", back_populates="chats")
    messages = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.id",
        lazy="selectin",
    )

    @property
    def last_message(self) -> "Message | None":
        return self.messages[-1] if self.messages else None

    @property
    def unread_for_user(self) -> int:
        return sum(1 for m in self.messages if m.sender_role == SenderRole.admin and m.read_at is None)

    @property
    def unread_for_admin(self) -> int:
        return sum(1 for m in self.messages if m.sender_role == SenderRole.user and m.read_at is None)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Chat {self.id} order={self.order_id}>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_role: Mapped[SenderRole] = mapped_column(
        Enum(SenderRole, native_enum=False, length=10), default=SenderRole.user, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", lazy="selectin")

    @property
    def is_system(self) -> bool:
        return self.sender_role == SenderRole.system

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Message {self.id} chat={self.chat_id}>"
