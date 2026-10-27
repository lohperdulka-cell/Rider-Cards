"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.models.audit import AuditLog
from app.models.category import Category
from app.models.chat import Chat, Message
from app.models.news import News
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, Rarity
from app.models.support import SupportTicket
from app.models.user import User
from app.models.wishlist import WishlistItem

__all__ = [
    "AuditLog",
    "Category",
    "Chat",
    "Message",
    "News",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
    "Rarity",
    "SupportTicket",
    "User",
    "WishlistItem",
]
