"""Support tickets created from the public support form."""

import enum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TicketStatus(str, enum.Enum):
    new = "new"
    in_progress = "in_progress"
    closed = "closed"


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    subject: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, native_enum=False, length=20), default=TicketStatus.new, nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)

    user = relationship("User", back_populates="tickets")
