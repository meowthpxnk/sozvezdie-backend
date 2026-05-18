from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import User, Product


class FavouriteProduct(Base, WithIDMixin):
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_favourite_product_user_product",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE")
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="favourite_products")
    product: Mapped["Product"] = relationship(back_populates="favourites")
