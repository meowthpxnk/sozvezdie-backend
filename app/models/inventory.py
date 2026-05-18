from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Cart, Product


class Inventory(Base, WithIDMixin):
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), unique=True
    )

    product: Mapped["Product"] = relationship(back_populates="inventory")
