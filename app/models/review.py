from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import OrderItem


class Review(Base, WithIDMixin):
    body: Mapped[str] = mapped_column(String)
    rating: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_item.id", ondelete="CASCADE")
    )
    order_item: Mapped["OrderItem"] = relationship(back_populates="reviews")
