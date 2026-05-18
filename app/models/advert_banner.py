from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer, UUID, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Cart, Product


class AdvertBanner(Base, WithIDMixin):
    image_uuid: Mapped[UUID] = mapped_column(UUID, nullable=False)
    link: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
