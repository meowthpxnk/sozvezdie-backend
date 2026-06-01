from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Order, OrderItem, Product, User
from app.repositories.specs.order import DELIVERED_ARCHIVE_GRACE_DAYS, OrderSpec
from app.schemas.database import OrderStatus

ACTIVE_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.PAID,
    OrderStatus.SHIPPED,
]


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _order_options(self):
        return (
            selectinload(Order.customer),
            selectinload(Order.order_items)
            .selectinload(OrderItem.product)
            .selectinload(Product.images),
        )

    def _delivered_archive_cutoff(self) -> datetime:
        return datetime.now() - timedelta(days=DELIVERED_ARCHIVE_GRACE_DAYS)

    def _delivered_at_expr(self):
        return func.coalesce(Order.delivered_at, Order.created_at)

    def _apply_archive_filter(self, stmt, *, archive: bool):
        cutoff = self._delivered_archive_cutoff()
        delivered_at = self._delivered_at_expr()
        delivered_recent = and_(
            Order.status == OrderStatus.DELIVERED,
            delivered_at >= cutoff,
        )
        delivered_archived = and_(
            Order.status == OrderStatus.DELIVERED,
            delivered_at < cutoff,
        )
        if archive:
            return stmt.where(
                or_(Order.status == OrderStatus.CANCELED, delivered_archived)
            )
        return stmt.where(
            or_(Order.status.in_(ACTIVE_STATUSES), delivered_recent)
        )

    def _apply_spec_filters(self, stmt, spec: OrderSpec):
        if spec.customer_id is not None:
            stmt = stmt.where(Order.customer_id == spec.customer_id)
        if spec.statuses:
            stmt = stmt.where(Order.status.in_(spec.statuses))
        elif spec.archive is not None:
            stmt = self._apply_archive_filter(stmt, archive=spec.archive)
        if spec.search:
            search = spec.search.strip()
            if search.isdigit():
                stmt = stmt.where(Order.id == int(search))
            else:
                pattern = f"%{search}%"
                stmt = stmt.join(Order.customer).where(
                    or_(
                        User.username.ilike(pattern),
                        User.full_name.ilike(pattern),
                        User.email.ilike(pattern),
                        User.phone.ilike(pattern),
                    )
                )
        return stmt

    async def get_orders(self, spec: OrderSpec) -> list[Order]:
        stmt = (
            select(Order)
            .options(*self._order_options())
            .order_by(Order.id.desc())
        )
        stmt = self._apply_spec_filters(stmt, spec)

        if spec.offset:
            stmt = stmt.offset(spec.offset)
        if spec.limit is not None:
            stmt = stmt.limit(spec.limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_orders(self, spec: OrderSpec) -> int:
        if spec.search and not spec.search.strip().isdigit():
            stmt = select(func.count(func.distinct(Order.id))).select_from(Order)
        else:
            stmt = select(func.count()).select_from(Order)
        stmt = self._apply_spec_filters(stmt, spec)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

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
            .options(*self._order_options())
        )
        if customer_id is not None:
            stmt = stmt.where(Order.customer_id == customer_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
