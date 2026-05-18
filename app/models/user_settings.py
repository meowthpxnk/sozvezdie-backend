from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import AppTheme

if TYPE_CHECKING:
    from . import User


class UserSettings(Base, WithIDMixin):
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True
    )
    theme: Mapped[AppTheme] = mapped_column(
        Enum(AppTheme), nullable=False, default=AppTheme.DARK
    )
    ava_path: Mapped[str] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="settings")
