from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, ForeignKey, Integer, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Cart, Product


class ProductImage(Base, WithIDMixin):
    image_uuid: Mapped[UUID] = mapped_column(UUID, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="images")
