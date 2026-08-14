from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import User


class AuthorInvite(Base, WithIDMixin):
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    one_c_author_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    used_by: Mapped["User | None"] = relationship()
