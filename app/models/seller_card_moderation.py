from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import ModerationStatus

if TYPE_CHECKING:
    from . import SellerCard, User


class SellerCardModerationAction(str, Enum):
    CREATE_SHOP = "CREATE_SHOP"
    UPDATE_BRAND = "UPDATE_BRAND"


class SellerCardModeration(Base, WithIDMixin):
    seller_card_id: Mapped[int] = mapped_column(
        ForeignKey("seller_card.id", ondelete="CASCADE")
    )
    moderator_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_type: Mapped[SellerCardModerationAction] = mapped_column(
        SqlEnum(
            SellerCardModerationAction,
            name="sellercardmoderationaction",
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[ModerationStatus] = mapped_column(
        SqlEnum(ModerationStatus, name="moderationstatus", create_type=False),
        nullable=False,
        default=ModerationStatus.PENDING,
    )
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    proposed_name: Mapped[str] = mapped_column(String, nullable=False)
    proposed_desc: Mapped[str] = mapped_column(String, nullable=False)
    proposed_banner_image: Mapped[str | None] = mapped_column(String, nullable=True)
    proposed_avatar_image: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    seller_card: Mapped["SellerCard"] = relationship(back_populates="moderations")
    moderator: Mapped["User | None"] = relationship(
        back_populates="seller_card_moderations"
    )
