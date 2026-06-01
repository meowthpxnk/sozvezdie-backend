import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import yookassa
from app.models import Order
from app.repositories.order import OrderRepository
from app.schemas.database import OrderStatus

logger = logging.getLogger("app")


class PaymentService:
    """Legacy: orders that already exist with yookassa_payment_id."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)

    async def get_order_by_payment_id(self, payment_id: str) -> Order | None:
        stmt = select(Order).where(Order.yookassa_payment_id == payment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def apply_payment_status(
        self,
        order: Order,
        *,
        payment_status: str,
        paid: bool,
    ) -> None:
        if paid and payment_status == "succeeded":
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.PAID
                await self.session.commit()
            return

        if payment_status == "canceled" and order.status == OrderStatus.PENDING:
            logger.info("Payment canceled for legacy order %s", order.id)

    async def handle_webhook(
        self,
        *,
        event: str,
        payment_id: str,
        payment_status: str,
        paid: bool,
        metadata: dict | None,
    ) -> None:
        order = await self.get_order_by_payment_id(payment_id)
        if order is None and metadata:
            order_id_raw = metadata.get("order_id")
            if order_id_raw is not None:
                order = await self.order_repo.get_order_by_id(int(order_id_raw))

        if order is None:
            return

        if event in ("payment.succeeded", "payment.waiting_for_capture"):
            await self.apply_payment_status(
                order,
                payment_status=payment_status,
                paid=paid,
            )
        elif event == "payment.canceled":
            await self.apply_payment_status(
                order,
                payment_status="canceled",
                paid=False,
            )
