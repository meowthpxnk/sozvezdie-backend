from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import DeliveryMethod, OrderStatus, PaymentMethod

if TYPE_CHECKING:
    from . import Cart, Product, User, Order, Review, OrderItem, UserAddress


class Order(Base, WithIDMixin):
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), nullable=False, default=PaymentMethod.CARD_ONLINE
    )
    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        Enum(DeliveryMethod), nullable=False, default=DeliveryMethod.SELF_PICKUP
    )
    delivery_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_flat: Mapped[str | None] = mapped_column(String, nullable=True)
    cdek_pvz_code: Mapped[str | None] = mapped_column(String, nullable=True)
    cdek_pvz_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    cdek_order_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    cdek_tariff_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cdek_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    yookassa_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    user_address_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_address.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE")
    )

    customer: Mapped["User"] = relationship(back_populates="orders")
    user_address: Mapped["UserAddress | None"] = relationship(
        back_populates="orders"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"
    )
