import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.order import InsufficientStockError
from app.integrations import cdek
from app.models import Inventory, Order, OrderItem, Product, User
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.specs.cart import CartSpec
from app.repositories.specs.order import OrderSpec
from app.repositories.specs.product import ProductSpec
from app.schemas.api.delivery import (
    DeliveryAddressInput,
    DeliveryCalculateItemRequest,
    DeliveryCalculateRequest,
    OrderDeliveryAddressPayload,
)
from app.schemas.api.responses import (
    ModeratorOrderCustomerResponse,
    ModeratorOrderDetailResponse,
    ModeratorOrderListItemResponse,
    ModeratorOrdersListResponse,
    OrderCreateRequest,
    OrderLineItemResponse,
    OrdersListResponse,
    UserOrderResponse,
)
from app.schemas.database import DeliveryMethod, OrderStatus, PaymentMethod
from app.services.delivery import DeliveryService
from app.services.integration_tasks import IntegrationTaskService
from app.services.user_address import UserAddressService

logger = logging.getLogger("app")

MODERATOR_STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELED: set(),
}


class PaymentNotCompletedError(Exception):
    def __init__(self, message: str = "Payment was not completed"):
        self.message = message
        super().__init__(message)


@dataclass
class PreparedOrderContext:
    data: OrderCreateRequest
    delivery_cost: int
    tariff_code: int | None
    pvz_code: str | None
    pvz_address: str | None
    recipient_city_code: int | None
    delivery_flat: str | None
    user_address_id: int | None
    items_total: int
    total_kopecks: int
    line_prices: dict[int, int]


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)
        self.cart_repo = CartRepository(session)
        self.product_repo = ProductRepository(session)
        self.delivery_service = DeliveryService()
        self.address_service = UserAddressService(session)

    def _to_line_item(self, item: OrderItem) -> OrderLineItemResponse:
        product = item.product
        image = str(product.images[0].image_uuid) if product.images else None
        line_total = item.price_at_time * item.quantity
        return OrderLineItemResponse(
            product_id=product.id,
            name=product.name,
            price_at_time=item.price_at_time,
            line_total=line_total,
            image=image,
            quantity=item.quantity,
        )

    def _to_order_response(
        self,
        order: Order,
        *,
        payment_confirmation_url: str | None = None,
    ) -> UserOrderResponse:
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
            delivery_date=order.delivery_date,
            delivery_address_text=order.delivery_address_text,
            delivery_flat=order.delivery_flat,
            cdek_pvz_code=order.cdek_pvz_code,
            cdek_pvz_address=order.cdek_pvz_address,
            payment_confirmation_url=payment_confirmation_url,
            items=items,
        )

    def _collect_requested_quantities(
        self,
        data: OrderCreateRequest,
    ) -> dict[int, int]:
        requested: dict[int, int] = defaultdict(int)
        for item in data.items:
            requested[item.product_id] += item.quantity
        return requested

    async def _lock_inventories(
        self,
        product_ids: list[int],
    ) -> dict[int, Inventory]:
        if not product_ids:
            return {}
        stmt = (
            select(Inventory)
            .where(Inventory.product_id.in_(product_ids))
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return {inventory.product_id: inventory for inventory in result.scalars()}

    def _assert_stock_available(
        self,
        requested: dict[int, int],
        products_by_id: dict[int, Product],
    ) -> None:
        for product_id, quantity in requested.items():
            product = products_by_id[product_id]
            inventory = product.inventory
            if inventory is None:
                raise InsufficientStockError()
            if inventory.quantity < quantity:
                raise InsufficientStockError()

    async def _reserve_stock(
        self,
        requested: dict[int, int],
        products_by_id: dict[int, Product],
    ) -> None:
        inventories = await self._lock_inventories(list(requested.keys()))
        for product_id, quantity in requested.items():
            inventory = inventories.get(product_id)
            if inventory is None:
                raise InsufficientStockError()
            if inventory.quantity < quantity:
                raise InsufficientStockError()
            inventory.quantity -= quantity
            product = products_by_id[product_id]
            if product.inventory is not None:
                product.inventory.quantity = inventory.quantity

    async def _restore_order_stock(self, order: Order) -> None:
        product_ids = [item.product_id for item in order.order_items]
        if not product_ids:
            return

        products = await self.product_repo.get_product(
            ProductSpec(
                ids=product_ids,
                include_inventory=True,
                all=True,
            )
        )
        products_by_id = {product.id: product for product in products}
        for item in order.order_items:
            product = products_by_id.get(item.product_id)
            if product is not None and product.inventory is not None:
                product.inventory.quantity += item.quantity

    def _validate_delivery_payload(self, data: OrderCreateRequest) -> None:
        if data.delivery_method == DeliveryMethod.SELF_PICKUP:
            return

        if data.delivery_method == DeliveryMethod.COURIER:
            raise ValueError(
                "Door delivery is not available. Use pickup point or self pickup"
            )

        if data.delivery_method != DeliveryMethod.PICKUP_POINT:
            return

        if data.address is None:
            raise ValueError("Delivery address is required")
        if data.delivery_date is None:
            raise ValueError("Delivery date is required")
        if data.address.lat is None or data.address.lon is None:
            raise ValueError("Address coordinates are required")
        if not data.address.pvz_code:
            raise ValueError("Pickup point is required")

    async def _resolve_delivery_cost(
        self,
        data: OrderCreateRequest,
    ) -> tuple[int, int | None, str | None, str | None, int | None]:
        self._validate_delivery_payload(data)
        if data.delivery_method == DeliveryMethod.SELF_PICKUP:
            if data.delivery_cost != 0:
                raise ValueError("Self pickup delivery cost must be 0")
            return 0, None, None, None, None

        if data.delivery_method != DeliveryMethod.PICKUP_POINT:
            return data.delivery_cost, None, None, None, None

        assert data.address is not None

        calc = await self.delivery_service.calculate(
            DeliveryCalculateRequest(
                delivery_method=data.delivery_method,
                address=DeliveryAddressInput(
                    formatted_address=data.address.formatted_address,
                    city=data.address.city,
                    street=data.address.street,
                    house=data.address.house,
                    postal_code=data.address.postal_code,
                    lat=data.address.lat,
                    lon=data.address.lon,
                    cdek_city_code=data.address.cdek_city_code,
                ),
                items=[
                    DeliveryCalculateItemRequest(
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )
                    for item in data.items
                ],
            )
        )

        if data.delivery_cost != calc.delivery_cost:
            raise ValueError(
                f"Delivery cost mismatch: expected {calc.delivery_cost}, "
                f"got {data.delivery_cost}"
            )

        if data.delivery_date is not None:
            date_min = (
                date.fromisoformat(calc.delivery_date_min)
                if calc.delivery_date_min
                else None
            )
            date_max = (
                date.fromisoformat(calc.delivery_date_max)
                if calc.delivery_date_max
                else None
            )
            if not cdek.is_delivery_date_available(
                data.delivery_date,
                delivery_date_min=date_min,
                delivery_date_max=date_max,
                period_min=calc.period_min,
                period_max=calc.period_max,
            ):
                if date_min and date_max:
                    raise ValueError(
                        f"Delivery date must be between {date_min.isoformat()} "
                        f"and {date_max.isoformat()}"
                    )
                raise ValueError("Selected delivery date is not available")

        pvz_code = calc.pvz_code or data.address.pvz_code
        pvz_address = calc.pvz_address
        return (
            calc.delivery_cost,
            calc.tariff_code,
            pvz_code,
            pvz_address,
            calc.pvz_search_city_code,
        )

    async def get_orders_for_user(
        self,
        user_id: int,
        *,
        archive: bool = False,
    ) -> OrdersListResponse:
        orders = await self.repo.get_orders(
            OrderSpec(customer_id=user_id, archive=archive)
        )
        return OrdersListResponse(
            items=[self._to_order_response(order) for order in orders]
        )

    def _to_moderator_customer(self, customer: User) -> ModeratorOrderCustomerResponse:
        return ModeratorOrderCustomerResponse(
            id=customer.id,
            username=customer.username,
            full_name=customer.full_name,
            email=customer.email,
            phone=customer.phone,
        )

    def _to_moderator_list_item(self, order: Order) -> ModeratorOrderListItemResponse:
        base = self._to_order_response(order)
        return ModeratorOrderListItemResponse(
            **base.model_dump(),
            customer=self._to_moderator_customer(order.customer),
        )

    def _to_moderator_detail(self, order: Order) -> ModeratorOrderDetailResponse:
        base = self._to_moderator_list_item(order)
        return ModeratorOrderDetailResponse(
            **base.model_dump(),
            cdek_order_uuid=order.cdek_order_uuid,
            cdek_error=order.cdek_error,
            yookassa_payment_id=order.yookassa_payment_id,
        )

    async def list_orders_for_moderation(
        self,
        *,
        status_filter: OrderStatus | None = None,
        archive: bool = False,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ModeratorOrdersListResponse:
        spec = OrderSpec(
            statuses=[status_filter] if status_filter is not None else None,
            archive=archive if status_filter is None else None,
            search=search,
            limit=limit,
            offset=offset,
        )
        total = await self.repo.count_orders(spec)
        orders = await self.repo.get_orders(spec)
        return ModeratorOrdersListResponse(
            items=[self._to_moderator_list_item(order) for order in orders],
            total=total,
        )

    async def get_order_for_moderation(self, order_id: int) -> ModeratorOrderDetailResponse:
        order = await self.repo.get_order_by_id(order_id)
        if order is None:
            raise ValueError("Order not found")
        return self._to_moderator_detail(order)

    async def update_order_status_for_moderation(
        self,
        order_id: int,
        new_status: OrderStatus,
    ) -> ModeratorOrderDetailResponse:
        order = await self.repo.get_order_by_id(order_id)
        if order is None:
            raise ValueError("Order not found")

        allowed = MODERATOR_STATUS_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot change status from {order.status.value} to {new_status.value}"
            )

        if new_status == OrderStatus.CANCELED:
            await self._moderator_cancel_order(order)
        elif new_status == OrderStatus.PAID and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.PAID
            await self._enqueue_cdek_create_order(order, customer=order.customer)
            await self.session.commit()
        else:
            order.status = new_status
            if new_status == OrderStatus.DELIVERED:
                order.delivered_at = datetime.now()
            await self.session.commit()

        refreshed = await self.repo.get_order_by_id(order_id)
        if refreshed is None:
            raise ValueError("Order not found")
        return self._to_moderator_detail(refreshed)

    async def _moderator_cancel_order(self, order: Order) -> None:
        if order.status == OrderStatus.CANCELED:
            return
        if order.status == OrderStatus.DELIVERED:
            raise ValueError("Delivered order cannot be canceled")
        if order.status not in (OrderStatus.PENDING, OrderStatus.PAID):
            raise ValueError("Order cannot be canceled in current status")

        await self._restore_order_stock(order)
        order.status = OrderStatus.CANCELED

        from app.services.checkout_payment import CheckoutPaymentService

        await CheckoutPaymentService(self.session).cancel_pending_checkouts_for_order(
            order.id
        )
        await self.session.commit()

        tasks = IntegrationTaskService(self.session)
        if order.cdek_order_uuid:
            await tasks.enqueue(
                task_type="CDEK_CANCEL_ORDER",
                entity_type="order",
                entity_id=order.id,
                dedupe_key=f"order:{order.id}:cdek_cancel",
                payload={
                    "order_id": order.id,
                    "cdek_order_uuid": order.cdek_order_uuid,
                },
            )

        if (
            order.payment_method == PaymentMethod.CARD_ONLINE
            and order.yookassa_payment_id
        ):
            total_kopecks = self._order_total_kopecks(order)
            await tasks.enqueue(
                task_type="YOOKASSA_CANCEL_OR_REFUND",
                entity_type="order",
                entity_id=order.id,
                dedupe_key=f"order:{order.id}:yookassa_cancel_or_refund",
                payload={"order_id": order.id, "total_kopecks": total_kopecks},
            )

        await self.session.commit()

    def _order_total_kopecks(self, order: Order) -> int:
        items_total = sum(
            (item.price_at_time or 0) * (item.quantity or 0)
            for item in (order.order_items or [])
        )
        return int(items_total + (order.delivery_cost or 0))

    async def cancel_order(
        self,
        *,
        user_id: int,
        order_id: int,
        customer: User,
    ) -> tuple[UserOrderResponse, dict, dict]:
        """
        Cancel order locally and attempt to cancel external services (CDEK + YooKassa).

        Returns:
          (order_response, cdek_result, payment_result)
        where *_result are dicts with keys: status, message.
        """
        order = await self.repo.get_order_by_id(order_id, customer_id=user_id)
        if order is None:
            raise ValueError("Order not found")

        if order.status in (OrderStatus.DELIVERED,):
            raise ValueError("Delivered order cannot be canceled")
        if order.status == OrderStatus.CANCELED:
            return (
                self._to_order_response(order),
                {"status": "skipped", "message": "Заказ уже отменён"},
                {"status": "skipped", "message": "Заказ уже отменён"},
            )

        if order.status not in (OrderStatus.PENDING, OrderStatus.PAID):
            raise ValueError("Order cannot be canceled in current status")

        cdek_result = {"status": "skipped", "message": None}
        payment_result = {"status": "skipped", "message": None}

        await self._restore_order_stock(order)
        order.status = OrderStatus.CANCELED

        from app.services.checkout_payment import CheckoutPaymentService

        await CheckoutPaymentService(self.session).cancel_pending_checkouts_for_order(
            order.id
        )
        await self.session.commit()

        tasks = IntegrationTaskService(self.session)
        # Enqueue best-effort integration tasks. They can be retried by worker.
        if order.cdek_order_uuid:
            await tasks.enqueue(
                task_type="CDEK_CANCEL_ORDER",
                entity_type="order",
                entity_id=order.id,
                dedupe_key=f"order:{order.id}:cdek_cancel",
                payload={
                    "order_id": order.id,
                    "cdek_order_uuid": order.cdek_order_uuid,
                },
            )
            cdek_result = {"status": "queued", "message": None}

        if (
            order.payment_method == PaymentMethod.CARD_ONLINE
            and order.yookassa_payment_id
        ):
            total_kopecks = self._order_total_kopecks(order)
            await tasks.enqueue(
                task_type="YOOKASSA_CANCEL_OR_REFUND",
                entity_type="order",
                entity_id=order.id,
                dedupe_key=f"order:{order.id}:yookassa_cancel_or_refund",
                payload={"order_id": order.id, "total_kopecks": total_kopecks},
            )
            payment_result = {"status": "queued", "message": None}

        await self.session.commit()

        refreshed = await self.repo.get_order_by_id(
            order.id, customer_id=user_id
        )
        if refreshed is None:
            refreshed = order
        return self._to_order_response(refreshed), cdek_result, payment_result

    async def prepare_order_context(
        self,
        user_id: int,
        data: OrderCreateRequest,
    ) -> PreparedOrderContext:
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

        requested = self._collect_requested_quantities(data)
        self._assert_stock_available(requested, products_by_id)
        self._validate_delivery_payload(data)

        (
            delivery_cost,
            tariff_code,
            pvz_code,
            pvz_address,
            recipient_city_code,
        ) = await self._resolve_delivery_cost(data)

        delivery_flat = None

        user_address_id = None
        if data.address and data.delivery_method != DeliveryMethod.SELF_PICKUP:
            saved_address = await self.address_service.save_from_order(
                user_id, data.address
            )
            user_address_id = saved_address.id

        line_prices = {
            item.product_id: products_by_id[item.product_id].price
            for item in data.items
        }
        items_total = sum(
            line_prices[item.product_id] * item.quantity for item in data.items
        )
        total_kopecks = items_total + delivery_cost
        if total_kopecks <= 0:
            raise ValueError("Order total must be positive")

        return PreparedOrderContext(
            data=data,
            delivery_cost=delivery_cost,
            tariff_code=tariff_code,
            pvz_code=pvz_code,
            pvz_address=pvz_address,
            recipient_city_code=recipient_city_code,
            delivery_flat=delivery_flat,
            user_address_id=user_address_id,
            items_total=items_total,
            total_kopecks=total_kopecks,
            line_prices=line_prices,
        )

    async def commit_prepared_order(
        self,
        user_id: int,
        context: PreparedOrderContext,
        *,
        customer: User,
        yookassa_payment_id: str | None = None,
    ) -> UserOrderResponse:
        return await self._create_order_from_context(
            user_id,
            context,
            customer=customer,
            initial_status=OrderStatus.PAID,
            yookassa_payment_id=yookassa_payment_id,
            auto_commit=False,
        )

    async def create_pending_order_for_online_payment(
        self,
        user_id: int,
        context: PreparedOrderContext,
        *,
        customer: User,
    ) -> UserOrderResponse:
        """Заказ до оплаты: резерв остатка, корзина и CDEK — после успешной оплаты."""
        return await self._create_order_from_context(
            user_id,
            context,
            customer=customer,
            initial_status=OrderStatus.PENDING,
            yookassa_payment_id=None,
            auto_commit=False,
            clear_cart=False,
            enqueue_cdek=False,
        )

    async def complete_online_payment(
        self,
        order_id: int,
        user_id: int,
        *,
        customer: User,
        yookassa_payment_id: str,
    ) -> UserOrderResponse:
        order = await self.repo.get_order_by_id(order_id, customer_id=user_id)
        if order is None:
            raise ValueError("Order not found")
        if order.status == OrderStatus.PAID:
            return self._to_order_response(order)
        if order.status != OrderStatus.PENDING:
            raise PaymentNotCompletedError("Order is not awaiting payment")
        if order.payment_method != PaymentMethod.CARD_ONLINE:
            raise ValueError("Order is not an online payment order")

        order.status = OrderStatus.PAID
        order.yookassa_payment_id = yookassa_payment_id

        cart = await self.cart_repo.get_cart(CartSpec(user_id=user_id))
        if cart is not None:
            for item in order.order_items:
                await self.cart_repo.delete_cart_item(cart.id, item.product_id)

        await self._enqueue_cdek_create_order(order, customer=customer)
        await self.session.flush()

        refreshed = await self.repo.get_order_by_id(
            order.id, customer_id=user_id
        )
        if refreshed is None:
            raise ValueError("Failed to load paid order")
        return self._to_order_response(refreshed)

    async def cancel_unpaid_online_order(
        self,
        order_id: int,
        *,
        customer_id: int,
    ) -> None:
        order = await self.repo.get_order_by_id(
            order_id, customer_id=customer_id
        )
        if order is None:
            return
        if order.status != OrderStatus.PENDING:
            return
        if order.payment_method != PaymentMethod.CARD_ONLINE:
            return

        await self._restore_order_stock(order)
        order.status = OrderStatus.CANCELED
        await self.session.flush()

    async def _enqueue_cdek_create_order(
        self,
        order: Order,
        *,
        customer: User,
    ) -> None:
        if order.delivery_method not in (
            DeliveryMethod.COURIER,
            DeliveryMethod.PICKUP_POINT,
        ):
            return
        if not order.cdek_tariff_code:
            return
        if not order.delivery_address_text and not order.cdek_pvz_code:
            return

        tasks = IntegrationTaskService(self.session)
        recipient_name = customer.full_name or customer.username
        recipient_phone = customer.phone or "70000000000"
        await tasks.enqueue(
            task_type="CDEK_CREATE_ORDER",
            entity_type="order",
            entity_id=order.id,
            dedupe_key=f"order:{order.id}:cdek_create",
            payload={
                "order_id": order.id,
                "recipient_name": recipient_name,
                "recipient_phone": recipient_phone,
            },
        )

    async def create_order(
        self,
        user_id: int,
        data: OrderCreateRequest,
        *,
        customer: User | None = None,
    ) -> UserOrderResponse:
        if data.payment_method == PaymentMethod.CARD_ONLINE:
            raise ValueError(
                "Online payment requires POST /order/initiate-payment"
            )
        if customer is None:
            raise ValueError("Customer is required")

        context = await self.prepare_order_context(user_id, data)
        return await self._create_order_from_context(
            user_id,
            context,
            customer=customer,
            initial_status=OrderStatus.PENDING,
        )

    async def _create_order_from_context(
        self,
        user_id: int,
        context: PreparedOrderContext,
        *,
        customer: User,
        initial_status: OrderStatus,
        yookassa_payment_id: str | None = None,
        auto_commit: bool = True,
        clear_cart: bool = True,
        enqueue_cdek: bool = True,
    ) -> UserOrderResponse:
        data = context.data
        trace_cdek = data.delivery_method in (
            DeliveryMethod.COURIER,
            DeliveryMethod.PICKUP_POINT,
        )
        if trace_cdek:
            cdek.begin_cdek_request_trace()

        order_id_for_cdek_log: int | None = None
        try:
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
            reserved = self._collect_requested_quantities(data)
            await self._reserve_stock(reserved, products_by_id)

            order = Order(
                customer_id=user_id,
                status=initial_status,
                payment_method=data.payment_method,
                delivery_method=data.delivery_method,
                delivery_cost=context.delivery_cost,
                delivery_date=data.delivery_date,
                delivery_address_text=(
                    data.address.formatted_address if data.address else None
                ),
                delivery_lat=data.address.lat if data.address else None,
                delivery_lon=data.address.lon if data.address else None,
                delivery_flat=context.delivery_flat,
                cdek_pvz_code=context.pvz_code,
                cdek_pvz_address=context.pvz_address,
                cdek_tariff_code=context.tariff_code,
                user_address_id=context.user_address_id,
                yookassa_payment_id=yookassa_payment_id,
            )
            self.repo.add(order)
            await self.session.flush()
            order_id_for_cdek_log = order.id

            for item in data.items:
                product = products_by_id[item.product_id]
                self.repo.add_item(
                    OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=item.quantity,
                        price_at_time=context.line_prices[item.product_id],
                    )
                )

            if clear_cart:
                cart = await self.cart_repo.get_cart(CartSpec(user_id=user_id))
                if cart is not None:
                    for product_id in reserved:
                        await self.cart_repo.delete_cart_item(
                            cart.id, product_id
                        )

            if auto_commit:
                await self.session.commit()
            else:
                await self.session.flush()

            if enqueue_cdek:
                await self._enqueue_cdek_create_order(order, customer=customer)
                if auto_commit:
                    await self.session.commit()
                else:
                    await self.session.flush()

            created_order = await self.repo.get_order_by_id(
                order.id,
                customer_id=user_id,
            )
            if created_order is None:
                raise ValueError("Failed to load created order")

            return self._to_order_response(created_order)
        finally:
            if trace_cdek:
                cdek.flush_cdek_request_trace_log(
                    order_id_for_cdek_log or 0,
                    delivery_method=str(data.delivery_method),
                )
