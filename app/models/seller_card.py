from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import ModerationStatus

if TYPE_CHECKING:
    from . import User, Product, FavouriteAuthor, Subcategory, SellerCardModeration


class SellerCard(Base, WithIDMixin):
    name: Mapped[str] = mapped_column(String, nullable=False)
    desc: Mapped[str] = mapped_column(String)
    status: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus, name="moderationstatus", create_type=False),
        nullable=False,
        default=ModerationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True
    )
    banner_image: Mapped[str] = mapped_column(String, nullable=True)
    avatar_image: Mapped[str] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="seller_card")
    moderations: Mapped[list["SellerCardModeration"]] = relationship(
        back_populates="seller_card",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="seller_card", cascade="all, delete-orphan"
    )
    favourites: Mapped[list["FavouriteAuthor"]] = relationship(
        back_populates="seller_card",
        cascade="all, delete-orphan",
    )
    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="seller_card",
        cascade="all, delete-orphan",
    )
