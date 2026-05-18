from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Enum, String, ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import ModerationStatus

if TYPE_CHECKING:
    from . import Cart, Product, User


class ProductModeration(Base, WithIDMixin):
    status: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus), nullable=False, default=ModerationStatus.REJECTED
    )
    comment: Mapped[str] = mapped_column(String)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )
    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE")
    )

    product: Mapped["Product"] = relationship(back_populates="moderations")
    moderator: Mapped["User"] = relationship(back_populates="product_moderations")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
