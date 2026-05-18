from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Cart, Product, User, Order, Review


class OrderItem(Base, WithIDMixin):
    price_at_time: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("order.id", ondelete="CASCADE")
    )

    product: Mapped["Product"] = relationship(back_populates="order_items")
    order: Mapped["Order"] = relationship(back_populates="order_items")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="order_item",
        cascade="all, delete-orphan"
    )
