from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from .category import Category
    from .product import Product
    from .seller_card import SellerCard


class Subcategory(Base, WithIDMixin):
    __table_args__ = (
        UniqueConstraint("category_slug", "slug", name="uq_subcategory_category_slug"),
    )

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_slug: Mapped[str] = mapped_column(
        ForeignKey("category.slug", ondelete="CASCADE"),
        nullable=False,
    )
    seller_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("seller_card.id", ondelete="CASCADE"),
        nullable=True,
    )

    category: Mapped["Category"] = relationship(back_populates="subcategories")
    seller_card: Mapped["SellerCard | None"] = relationship(back_populates="subcategories")
    products: Mapped[list["Product"]] = relationship(back_populates="subcategory")
