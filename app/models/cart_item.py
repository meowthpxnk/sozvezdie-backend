from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Cart, Product


class CartItem(Base, WithIDMixin):
    __table_args__ = (
        UniqueConstraint(
            "cart_id",
            "product_id",
            name="uq_cart_product",
        ),
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("cart.id", ondelete="CASCADE")
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )

    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="cart_items")
