from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import User


class VkIdMapping(Base, WithIDMixin):
    __table_args__ = (
        UniqueConstraint("vk_id", name="uq_vk_id_mapping_vk_id"),
        UniqueConstraint("user_id", name="uq_vk_id_mapping_user_id"),
    )

    vk_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship()
