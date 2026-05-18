from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Order, OrderItem, Product
from app.repositories.specs.order import OrderSpec


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_orders(self, spec: OrderSpec) -> list[Order]:
        if spec.customer_id is None:
            raise ValueError("OrderSpec requires customer_id")

        stmt = (
            select(Order)
            .where(Order.customer_id == spec.customer_id)
            .options(
                selectinload(Order.order_items).selectinload(
                    OrderItem.product
                ).selectinload(Product.images)
            )
            .order_by(Order.id.desc())
        )

        if spec.statuses:
            stmt = stmt.where(Order.status.in_(spec.statuses))

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    def add(self, order: Order) -> Order:
        self.session.add(order)
        return order

    def add_item(self, order_item: OrderItem) -> OrderItem:
        self.session.add(order_item)
        return order_item

    async def get_order_by_id(
        self,
        order_id: int,
        *,
        customer_id: int | None = None,
    ) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.order_items).selectinload(
                    OrderItem.product
                ).selectinload(Product.images)
            )
        )
        if customer_id is not None:
            stmt = stmt.where(Order.customer_id == customer_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
