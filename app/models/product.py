from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import ModerationStatus

if TYPE_CHECKING:
    from . import (
        SellerCard,
        CartItem,
        ProductImage,
        ProductAlternative,
        Inventory,
        Review,
        OrderItem,
        ProductModeration,
        FavouriteProduct,
        Category,
        Subcategory,
        Fandom,
    )


class Product(Base, WithIDMixin):
    name: Mapped[str] = mapped_column(String, nullable=False)
    desc: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus),
        nullable=False,
        default=ModerationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    cart_items: Mapped[list["CartItem"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    seller_card_id: Mapped[int] = mapped_column(
        ForeignKey("seller_card.id", ondelete="CASCADE")
    )
    seller_card: Mapped["SellerCard"] = relationship(back_populates="products")
    alternatives: Mapped[list["ProductAlternative"]] = relationship(
        back_populates="product",
        foreign_keys="ProductAlternative.product_id",
        cascade="all, delete-orphan",
    )
    incoming_alternatives: Mapped[list["ProductAlternative"]] = relationship(
        back_populates="alt_product",
        foreign_keys="ProductAlternative.alt_product_id",
        cascade="all, delete-orphan",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    moderations: Mapped[list["ProductModeration"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    inventory: Mapped["Inventory"] = relationship(
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    favourites: Mapped[list["FavouriteProduct"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    category_slug: Mapped[str | None] = mapped_column(
        ForeignKey("category.slug", ondelete="SET NULL"),
        nullable=True,
    )
    subcategory_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcategory.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped["Category | None"] = relationship(back_populates="products")
    subcategory: Mapped["Subcategory | None"] = relationship(
        back_populates="products"
    )
    fandom_slug: Mapped[str | None] = mapped_column(
        ForeignKey("fandom.slug", ondelete="SET NULL"),
        nullable=True,
    )
    fandom: Mapped["Fandom | None"] = relationship(back_populates="products")
