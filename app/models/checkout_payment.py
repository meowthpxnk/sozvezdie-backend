import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin

if TYPE_CHECKING:
    from . import Order, User


class CheckoutPaymentStatus(enum.Enum):
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELED = "CANCELED"


class CheckoutPayment(Base, WithIDMixin):
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    yookassa_payment_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    yookassa_idempotence_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        default=lambda: str(uuid.uuid4()),
    )
    cart_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    total_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[CheckoutPaymentStatus] = mapped_column(
        Enum(CheckoutPaymentStatus),
        nullable=False,
        default=CheckoutPaymentStatus.PENDING,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("order.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    customer: Mapped["User"] = relationship()
    order: Mapped["Order | None"] = relationship()
