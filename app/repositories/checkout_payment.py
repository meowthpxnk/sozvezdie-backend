from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CheckoutPayment, CheckoutPaymentStatus


class CheckoutPaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, checkout: CheckoutPayment) -> CheckoutPayment:
        self.session.add(checkout)
        return checkout

    async def get_by_id(
        self,
        checkout_id: int,
        *,
        customer_id: int | None = None,
        for_update: bool = False,
    ) -> CheckoutPayment | None:
        stmt = select(CheckoutPayment).where(CheckoutPayment.id == checkout_id)
        if customer_id is not None:
            stmt = stmt.where(CheckoutPayment.customer_id == customer_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_payment_id(
        self, payment_id: str, *, for_update: bool = False
    ) -> CheckoutPayment | None:
        stmt = select(CheckoutPayment).where(
            CheckoutPayment.yookassa_payment_id == payment_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_by_customer(
        self, customer_id: int
    ) -> list[CheckoutPayment]:
        stmt = (
            select(CheckoutPayment)
            .where(
                CheckoutPayment.customer_id == customer_id,
                CheckoutPayment.status == CheckoutPaymentStatus.PENDING,
            )
            .order_by(CheckoutPayment.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_by_fingerprint(
        self,
        customer_id: int,
        cart_fingerprint: str,
    ) -> CheckoutPayment | None:
        stmt = (
            select(CheckoutPayment)
            .where(
                CheckoutPayment.customer_id == customer_id,
                CheckoutPayment.cart_fingerprint == cart_fingerprint,
                CheckoutPayment.status == CheckoutPaymentStatus.PENDING,
            )
            .order_by(CheckoutPayment.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_fulfilled_by_fingerprint(
        self,
        customer_id: int,
        cart_fingerprint: str,
    ) -> CheckoutPayment | None:
        stmt = (
            select(CheckoutPayment)
            .where(
                CheckoutPayment.customer_id == customer_id,
                CheckoutPayment.cart_fingerprint == cart_fingerprint,
                CheckoutPayment.status == CheckoutPaymentStatus.FULFILLED,
                CheckoutPayment.order_id.isnot(None),
            )
            .order_by(CheckoutPayment.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_order_id(
        self,
        order_id: int,
        *,
        statuses: list[CheckoutPaymentStatus] | None = None,
    ) -> list[CheckoutPayment]:
        stmt = select(CheckoutPayment).where(CheckoutPayment.order_id == order_id)
        if statuses is not None:
            stmt = stmt.where(CheckoutPayment.status.in_(statuses))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cancel_pending_for_customer(
        self,
        customer_id: int,
        *,
        except_checkout_id: int | None = None,
    ) -> None:
        pending = await self.get_pending_by_customer(customer_id)
        for checkout in pending:
            if except_checkout_id is not None and checkout.id == except_checkout_id:
                continue
            checkout.status = CheckoutPaymentStatus.CANCELED
