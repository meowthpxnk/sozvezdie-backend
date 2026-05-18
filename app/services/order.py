from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderItem, Product
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.specs.cart import CartSpec
from app.repositories.specs.order import OrderSpec
from app.repositories.specs.product import ProductSpec
from app.schemas.api.responses import (
    OrderCreateRequest,
    OrderLineItemResponse,
    OrdersListResponse,
    UserOrderResponse,
)
from app.schemas.database import OrderStatus

ACTIVE_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.PAID,
    OrderStatus.SHIPPED,
]
ARCHIVE_STATUSES = [OrderStatus.DELIVERED, OrderStatus.CANCELED]


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)
        self.cart_repo = CartRepository(session)
        self.product_repo = ProductRepository(session)

    def _to_line_item(self, item: OrderItem) -> OrderLineItemResponse:
        product = item.product
        image = (
            str(product.images[0].image_uuid) if product.images else None
        )
        line_total = item.price_at_time * item.quantity
        return OrderLineItemResponse(
            product_id=product.id,
            name=product.name,
            price_at_time=item.price_at_time,
            line_total=line_total,
            image=image,
            quantity=item.quantity,
        )

    def _to_order_response(self, order: Order) -> UserOrderResponse:
        items = [self._to_line_item(item) for item in order.order_items]
        items_total = sum(line.line_total for line in items)
        delivery_cost = order.delivery_cost
        return UserOrderResponse(
            id=order.id,
            status=order.status,
            payment_method=order.payment_method,
            delivery_method=order.delivery_method,
            items_total=items_total,
            delivery_cost=delivery_cost,
            total=items_total + delivery_cost,
            created_at=order.created_at,
            items=items,
        )

    def _validate_and_reserve_stock(
        self,
        data: OrderCreateRequest,
        products_by_id: dict[int, Product],
    ) -> dict[int, int]:
        requested: dict[int, int] = defaultdict(int)
        for item in data.items:
            requested[item.product_id] += item.quantity

        for product_id, quantity in requested.items():
            product = products_by_id[product_id]
            inventory = product.inventory
            if inventory is None:
                raise ValueError(
                    f"Product '{product.name}' is not available for order"
                )
            if inventory.quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for '{product.name}': "
                    f"available {inventory.quantity}, requested {quantity}"
                )

        return requested

    async def get_orders_for_user(
        self,
        user_id: int,
        *,
        archive: bool = False,
    ) -> OrdersListResponse:
        statuses = ARCHIVE_STATUSES if archive else ACTIVE_STATUSES
        orders = await self.repo.get_orders(
            OrderSpec(customer_id=user_id, statuses=statuses)
        )
        return OrdersListResponse(
            items=[self._to_order_response(order) for order in orders]
        )

    async def create_order(
        self,
        user_id: int,
        data: OrderCreateRequest,
    ) -> UserOrderResponse:
        product_ids = [item.product_id for item in data.items]
        products = await self.product_repo.get_product(
            ProductSpec(
                ids=product_ids,
                include_images=True,
                include_inventory=True,
                all=True,
                approved_only=True,
            )
        )
        products_by_id = {product.id: product for product in products}

        missing_ids = [
            product_id
            for product_id in product_ids
            if product_id not in products_by_id
        ]
        if missing_ids:
            raise ValueError(f"Products not found: {missing_ids}")

        reserved = self._validate_and_reserve_stock(data, products_by_id)

        order = Order(
            customer_id=user_id,
            status=OrderStatus.PENDING,
            payment_method=data.payment_method,
            delivery_method=data.delivery_method,
            delivery_cost=data.delivery_cost,
        )
        self.repo.add(order)
        await self.session.flush()

        for item in data.items:
            product = products_by_id[item.product_id]
            self.repo.add_item(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    price_at_time=product.price,
                )
            )

        for product_id, quantity in reserved.items():
            products_by_id[product_id].inventory.quantity -= quantity

        cart = await self.cart_repo.get_cart(CartSpec(user_id=user_id))
        if cart is not None:
            for product_id in reserved:
                await self.cart_repo.delete_cart_item(cart.id, product_id)

        await self.session.commit()

        created_order = await self.repo.get_order_by_id(
            order.id,
            customer_id=user_id,
        )
        if created_order is None:
            raise ValueError("Failed to load created order")

        return self._to_order_response(created_order)
