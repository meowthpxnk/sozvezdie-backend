from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Product


class ProductAlternative(Base, WithIDMixin):
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )
    alt_product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )

    product: Mapped["Product"] = relationship(
        foreign_keys=[product_id],
        back_populates="alternatives",
    )

    alt_product: Mapped["Product"] = relationship(
        foreign_keys=[alt_product_id],
        back_populates="incoming_alternatives",
    )
