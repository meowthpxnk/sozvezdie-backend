from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import User, SellerCard


class FavouriteAuthor(Base, WithIDMixin):
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "seller_card_id",
            name="uq_favourite_author_user_seller_card",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE")
    )
    seller_card_id: Mapped[int] = mapped_column(
        ForeignKey("seller_card.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="favourite_authors")
    seller_card: Mapped["SellerCard"] = relationship(back_populates="favourites")
