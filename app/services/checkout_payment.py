import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.email import require_verified_email
from app.integrations import yookassa
from app.integrations.yookassa_payment import is_payment_successful
from app.models import CheckoutPayment, CheckoutPaymentStatus, User
from app.repositories.checkout_payment import CheckoutPaymentRepository
from app.schemas.api.responses import (
    CheckoutCompleteResponse,
    CheckoutPaymentInitResponse,
    OrderCreateRequest,
    PendingPaymentSyncItem,
    SyncPendingPaymentsResponse,
    UserOrderResponse,
)
from app.schemas.database import OrderStatus, PaymentMethod
from app.services.order import OrderService, PaymentNotCompletedError, PreparedOrderContext
from app.utils.cart_fingerprint import build_cart_fingerprint

logger = logging.getLogger("app")


class CheckoutPaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CheckoutPaymentRepository(session)
        self.order_service = OrderService(session)

    def _context_to_payload(self, context: PreparedOrderContext) -> dict:
        return {
            "request": context.data.model_dump(mode="json"),
            "resolved": {
                "delivery_cost": context.delivery_cost,
                "tariff_code": context.tariff_code,
                "pvz_code": context.pvz_code,
                "pvz_address": context.pvz_address,
                "recipient_city_code": context.recipient_city_code,
                "delivery_flat": context.delivery_flat,
                "user_address_id": context.user_address_id,
                "line_prices": {str(k): v for k, v in context.line_prices.items()},
            },
        }

    def _payload_to_context(self, payload: dict) -> PreparedOrderContext:
        data = OrderCreateRequest.model_validate(payload["request"])
        resolved = payload["resolved"]
        line_prices = {
            int(product_id): int(price)
            for product_id, price in resolved["line_prices"].items()
        }
        items_total = sum(
            line_prices[item.product_id] * item.quantity for item in data.items
        )
        delivery_cost = int(resolved["delivery_cost"])
        return PreparedOrderContext(
            data=data,
            delivery_cost=delivery_cost,
            tariff_code=resolved.get("tariff_code"),
            pvz_code=resolved.get("pvz_code"),
            pvz_address=resolved.get("pvz_address"),
            recipient_city_code=resolved.get("recipient_city_code"),
            delivery_flat=resolved.get("delivery_flat"),
            user_address_id=resolved.get("user_address_id"),
            items_total=items_total,
            total_kopecks=items_total + delivery_cost,
            line_prices=line_prices,
        )

    async def _sync_checkout_with_yookassa(
        self,
        checkout: CheckoutPayment,
        *,
        customer: User,
    ) -> PendingPaymentSyncItem:
        if checkout.yookassa_payment_id in ("", "pending"):
            return PendingPaymentSyncItem(
                checkout_id=checkout.id,
                status="pending",
                cart_fingerprint=checkout.cart_fingerprint,
            )

        payment = await yookassa.get_payment(checkout.yookassa_payment_id)

        if payment.status == "canceled":
            if checkout.status == CheckoutPaymentStatus.PENDING:
                await self._cancel_checkout(checkout)
            return PendingPaymentSyncItem(
                checkout_id=checkout.id,
                status="failed",
                cart_fingerprint=checkout.cart_fingerprint,
            )

        if is_payment_successful(payment):
            if checkout.status in (
                CheckoutPaymentStatus.PENDING,
                CheckoutPaymentStatus.CANCELED,
            ):
                order = await self.fulfill_checkout(
                    checkout,
                    customer=customer,
                    allow_canceled_recovery=(
                        checkout.status == CheckoutPaymentStatus.CANCELED
                    ),
                )
                await self._cancel_other_pending(
                    checkout.customer_id,
                    except_checkout_id=checkout.id,
                )
                return self._paid_sync_item(checkout, order)
            return await self._paid_sync_item_from_checkout(checkout)

        return PendingPaymentSyncItem(
            checkout_id=checkout.id,
            status="pending",
            cart_fingerprint=checkout.cart_fingerprint,
            payment_confirmation_url=payment.confirmation_url,
        )

    def _paid_sync_item(
        self,
        checkout: CheckoutPayment,
        order: UserOrderResponse,
    ) -> PendingPaymentSyncItem:
        return PendingPaymentSyncItem(
            checkout_id=checkout.id,
            status="paid",
            cart_fingerprint=checkout.cart_fingerprint,
            order_id=order.id,
            product_ids=[item.product_id for item in order.items],
            order=order,
        )

    async def _paid_sync_item_from_checkout(
        self,
        checkout: CheckoutPayment,
    ) -> PendingPaymentSyncItem:
        order = None
        if checkout.order_id is not None:
            loaded = await self.order_service.repo.get_order_by_id(
                checkout.order_id,
                customer_id=checkout.customer_id,
            )
            if loaded is not None:
                order = self.order_service._to_order_response(loaded)
        if order is not None:
            return self._paid_sync_item(checkout, order)
        return PendingPaymentSyncItem(
            checkout_id=checkout.id,
            status="paid",
            cart_fingerprint=checkout.cart_fingerprint,
            order_id=checkout.order_id,
        )

    async def _already_paid_response(
        self,
        checkout: CheckoutPayment,
    ) -> CheckoutPaymentInitResponse | None:
        if checkout.order_id is None:
            return None
        loaded = await self.order_service.repo.get_order_by_id(
            checkout.order_id,
            customer_id=checkout.customer_id,
        )
        if loaded is None:
            return None
        order = self.order_service._to_order_response(loaded)
        return CheckoutPaymentInitResponse(
            checkout_id=checkout.id,
            payment_confirmation_url="",
            total=checkout.total_kopecks,
            already_paid=True,
            order=order,
        )

    async def _get_linked_order_status(
        self,
        checkout: CheckoutPayment,
    ) -> OrderStatus | None:
        if checkout.order_id is None:
            return None
        order = await self.order_service.repo.get_order_by_id(
            checkout.order_id,
            customer_id=checkout.customer_id,
        )
        if order is None:
            return None
        return order.status

    async def _checkout_can_resume_payment(self, checkout: CheckoutPayment) -> bool:
        if checkout.status != CheckoutPaymentStatus.PENDING:
            return False
        order_status = await self._get_linked_order_status(checkout)
        if order_status is None:
            return True
        return order_status == OrderStatus.PENDING

    async def cancel_pending_checkouts_for_order(self, order_id: int) -> None:
        checkouts = await self.repo.get_by_order_id(
            order_id,
            statuses=[CheckoutPaymentStatus.PENDING],
        )
        for checkout in checkouts:
            checkout.status = CheckoutPaymentStatus.CANCELED

    async def _cancel_checkout(self, checkout: CheckoutPayment) -> None:
        if checkout.status == CheckoutPaymentStatus.CANCELED:
            return
        checkout.status = CheckoutPaymentStatus.CANCELED
        if checkout.order_id is not None:
            await self.order_service.cancel_unpaid_online_order(
                checkout.order_id,
                customer_id=checkout.customer_id,
            )

    async def _discard_stale_checkout(self, checkout: CheckoutPayment) -> None:
        """Cancel checkout whose linked order is no longer awaiting payment."""
        if await self._checkout_can_resume_payment(checkout):
            return
        logger.info(
            "Discarding stale checkout %s (order_id=%s)",
            checkout.id,
            checkout.order_id,
        )
        await self._cancel_checkout(checkout)

    async def _cancel_other_pending(
        self,
        customer_id: int,
        *,
        except_checkout_id: int | None = None,
    ) -> None:
        for checkout in await self.repo.get_pending_by_customer(customer_id):
            if except_checkout_id is not None and checkout.id == except_checkout_id:
                continue
            await self._cancel_checkout(checkout)

    async def sync_pending_payments(
        self,
        user_id: int,
        *,
        customer: User,
        cart_fingerprint: str | None = None,
    ) -> SyncPendingPaymentsResponse:
        pending = await self.repo.get_pending_by_customer(user_id)
        items: list[PendingPaymentSyncItem] = []
        fulfilled_fingerprints: set[str] = set()

        for checkout in pending:
            if (
                cart_fingerprint is not None
                and checkout.cart_fingerprint != cart_fingerprint
            ):
                continue
            if (
                checkout.cart_fingerprint
                and checkout.cart_fingerprint in fulfilled_fingerprints
            ):
                await self._cancel_checkout(checkout)
                items.append(
                    PendingPaymentSyncItem(
                        checkout_id=checkout.id,
                        status="failed",
                        cart_fingerprint=checkout.cart_fingerprint,
                    )
                )
                continue
            locked = await self.repo.get_by_id(
                checkout.id,
                customer_id=user_id,
                for_update=True,
            )
            if locked is None:
                continue
            if not await self._checkout_can_resume_payment(locked):
                await self._discard_stale_checkout(locked)
                items.append(
                    PendingPaymentSyncItem(
                        checkout_id=locked.id,
                        status="failed",
                        cart_fingerprint=locked.cart_fingerprint,
                    )
                )
                continue
            item = await self._sync_checkout_with_yookassa(
                locked, customer=customer
            )
            items.append(item)
            if item.status == "paid" and locked.cart_fingerprint:
                fulfilled_fingerprints.add(locked.cart_fingerprint)

        await self.session.commit()
        return SyncPendingPaymentsResponse(items=items)

    async def initiate_payment(
        self,
        user_id: int,
        data: OrderCreateRequest,
        *,
        customer: User,
    ) -> CheckoutPaymentInitResponse:
        if data.payment_method != PaymentMethod.CARD_ONLINE:
            raise ValueError("Only CARD_ONLINE uses initiate-payment")
        require_verified_email(
            email=customer.email,
            email_verified=bool(customer.email_verified),
        )

        fingerprint = build_cart_fingerprint(data)

        await self.sync_pending_payments(user_id, customer=customer)

        # Idempotent retry for the same checkout session only (fingerprint includes
        # checkout_session_id). Repeat purchases with the same cart get a new session id.
        fulfilled = await self.repo.get_fulfilled_by_fingerprint(user_id, fingerprint)
        if fulfilled is not None and data.checkout_session_id:
            already_paid = await self._already_paid_response(fulfilled)
            if already_paid is not None:
                return already_paid

        existing = await self.repo.get_pending_by_fingerprint(user_id, fingerprint)
        if existing is not None:
            if not await self._checkout_can_resume_payment(existing):
                await self._discard_stale_checkout(existing)
                await self.session.flush()
                existing = None

        if existing is not None:
            payment = await yookassa.get_payment(existing.yookassa_payment_id)
            if is_payment_successful(payment):
                order = await self.fulfill_checkout(existing, customer=customer)
                await self.session.commit()
                return CheckoutPaymentInitResponse(
                    checkout_id=existing.id,
                    payment_confirmation_url="",
                    total=existing.total_kopecks,
                    already_paid=True,
                    order=order,
                )
            if payment.status == "pending" and payment.confirmation_url:
                if await self._checkout_can_resume_payment(existing):
                    return CheckoutPaymentInitResponse(
                        checkout_id=existing.id,
                        payment_confirmation_url=payment.confirmation_url,
                        total=existing.total_kopecks,
                    )
            await self._cancel_checkout(existing)
            await self.session.flush()

        pending_checkouts = await self.repo.get_pending_by_customer(user_id)
        for pending_checkout in pending_checkouts:
            await self._cancel_checkout(pending_checkout)

        context = await self.order_service.prepare_order_context(user_id, data)

        checkout = CheckoutPayment(
            customer_id=user_id,
            yookassa_payment_id="pending",
            yookassa_idempotence_key=str(uuid.uuid4()),
            cart_fingerprint=fingerprint,
            total_kopecks=context.total_kopecks,
            payload=self._context_to_payload(context),
            status=CheckoutPaymentStatus.PENDING,
        )
        self.repo.add(checkout)
        await self.session.flush()

        pending_order = await self.order_service.create_pending_order_for_online_payment(
            user_id,
            context,
            customer=customer,
        )
        checkout.order_id = pending_order.id
        await self.session.flush()

        payment = await yookassa.create_payment(
            checkout_id=checkout.id,
            amount_kopecks=context.total_kopecks,
            description=yookassa.build_payment_description(
                username=customer.username,
                order_id=pending_order.id,
            ),
            idempotence_key=checkout.yookassa_idempotence_key,
            username=customer.username,
            order_id=pending_order.id,
        )
        checkout.yookassa_payment_id = payment.payment_id
        await self.session.commit()

        return CheckoutPaymentInitResponse(
            checkout_id=checkout.id,
            payment_confirmation_url=payment.confirmation_url or "",
            total=context.total_kopecks,
        )

    async def _return_fulfilled_order(self, checkout: CheckoutPayment) -> UserOrderResponse:
        if checkout.order_id is None:
            raise PaymentNotCompletedError("Checkout fulfilled without order")
        order = await self.order_service.repo.get_order_by_id(
            checkout.order_id,
            customer_id=checkout.customer_id,
        )
        if order is None:
            raise ValueError("Fulfilled checkout order not found")
        return self.order_service._to_order_response(order)

    async def _fulfill_checkout_order(
        self,
        checkout: CheckoutPayment,
        context: PreparedOrderContext,
        *,
        customer: User,
    ) -> UserOrderResponse:
        if checkout.order_id is not None:
            order = await self.order_service.repo.get_order_by_id(
                checkout.order_id,
                customer_id=checkout.customer_id,
            )
            if order is not None and order.status == OrderStatus.PAID:
                return self.order_service._to_order_response(order)
            if order is not None and order.status == OrderStatus.PENDING:
                return await self.order_service.complete_online_payment(
                    checkout.order_id,
                    checkout.customer_id,
                    customer=customer,
                    yookassa_payment_id=checkout.yookassa_payment_id,
                )
            if order is not None and order.status == OrderStatus.CANCELED:
                logger.warning(
                    "Checkout %s linked to canceled order %s; creating new order",
                    checkout.id,
                    checkout.order_id,
                )
            elif checkout.order_id is not None:
                logger.warning(
                    "Checkout %s linked to order %s in status %s; creating new order",
                    checkout.id,
                    checkout.order_id,
                    order.status if order else "missing",
                )
            checkout.order_id = None

        return await self.order_service.commit_prepared_order(
            checkout.customer_id,
            context,
            customer=customer,
            yookassa_payment_id=checkout.yookassa_payment_id,
        )

    async def _attach_to_existing_fulfilled_checkout(
        self,
        checkout: CheckoutPayment,
        *,
        source: CheckoutPayment,
    ) -> UserOrderResponse:
        if (
            checkout.order_id is not None
            and checkout.order_id != source.order_id
        ):
            await self.order_service.cancel_unpaid_online_order(
                checkout.order_id,
                customer_id=checkout.customer_id,
            )
        checkout.status = CheckoutPaymentStatus.FULFILLED
        checkout.order_id = source.order_id
        await self._cancel_other_pending(
            checkout.customer_id,
            except_checkout_id=checkout.id,
        )
        await self.session.commit()
        return await self._return_fulfilled_order(checkout)

    async def fulfill_checkout(
        self,
        checkout: CheckoutPayment,
        *,
        customer: User,
        allow_canceled_recovery: bool = False,
    ) -> UserOrderResponse:
        locked = await self.repo.get_by_id(
            checkout.id, customer_id=checkout.customer_id, for_update=True
        )
        if locked is None:
            raise ValueError("Checkout not found")
        checkout = locked

        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": checkout.id},
        )

        if checkout.status == CheckoutPaymentStatus.FULFILLED and checkout.order_id:
            return await self._return_fulfilled_order(checkout)

        if checkout.cart_fingerprint:
            fulfilled = await self.repo.get_fulfilled_by_fingerprint(
                checkout.customer_id,
                checkout.cart_fingerprint,
            )
            if (
                fulfilled is not None
                and fulfilled.id != checkout.id
                and fulfilled.order_id is not None
            ):
                return await self._attach_to_existing_fulfilled_checkout(
                    checkout,
                    source=fulfilled,
                )

        if checkout.status == CheckoutPaymentStatus.CANCELED:
            if not allow_canceled_recovery:
                raise PaymentNotCompletedError("Payment was canceled")
            checkout.status = CheckoutPaymentStatus.PENDING

        if checkout.status != CheckoutPaymentStatus.PENDING:
            raise PaymentNotCompletedError("Checkout is not pending")

        context = self._payload_to_context(checkout.payload)
        order_response = await self._fulfill_checkout_order(
            checkout,
            context,
            customer=customer,
        )
        checkout.order_id = order_response.id

        checkout.status = CheckoutPaymentStatus.FULFILLED
        await self._cancel_other_pending(
            checkout.customer_id,
            except_checkout_id=checkout.id,
        )
        await self.session.commit()

        return order_response

    async def complete_checkout(
        self,
        checkout_id: int,
        user_id: int,
        *,
        customer: User,
    ) -> CheckoutCompleteResponse:
        checkout = await self.repo.get_by_id(
            checkout_id,
            customer_id=user_id,
            for_update=True,
        )
        if checkout is None:
            raise ValueError("Checkout not found")

        if checkout.status == CheckoutPaymentStatus.FULFILLED and checkout.order_id:
            order = await self._return_fulfilled_order(checkout)
            await self.session.commit()
            return CheckoutCompleteResponse(
                status="paid",
                order=order,
                message=None,
            )

        try:
            sync_item = await self._sync_checkout_with_yookassa(
                checkout, customer=customer
            )
        except PaymentNotCompletedError as error:
            await self.session.commit()
            return CheckoutCompleteResponse(
                status="failed",
                order=None,
                message=str(error),
            )
        await self.session.commit()

        if sync_item.status == "paid":
            order = sync_item.order
            if order is None and sync_item.order_id is not None:
                loaded = await self.order_service.repo.get_order_by_id(
                    sync_item.order_id,
                    customer_id=user_id,
                )
                if loaded is not None:
                    order = self.order_service._to_order_response(loaded)
            return CheckoutCompleteResponse(
                status="paid",
                order=order,
                message=None,
            )

        if sync_item.status == "failed":
            return CheckoutCompleteResponse(
                status="failed",
                order=None,
                message="Оплата не прошла",
            )

        return CheckoutCompleteResponse(
            status="pending",
            order=None,
            message="Ожидаем подтверждение оплаты",
        )

    async def handle_webhook(
        self,
        *,
        event: str,
        payment_id: str,
        payment_status: str,
        paid: bool,
        metadata: dict | None,
    ) -> None:
        logger.info(
            "YooKassa webhook: event=%s payment_id=%s status=%s paid=%s metadata=%s",
            event,
            payment_id,
            payment_status,
            paid,
            metadata,
        )

        try:
            verified = await yookassa.get_payment(payment_id)
            payment_status = verified.status
            paid = verified.paid
        except Exception:
            logger.exception("Failed to verify payment %s from YooKassa API", payment_id)

        checkout = await self.repo.get_by_payment_id(payment_id, for_update=True)
        if checkout is None and metadata:
            checkout_id_raw = metadata.get("checkout_id")
            if checkout_id_raw is not None:
                checkout = await self.repo.get_by_id(
                    int(checkout_id_raw), for_update=True
                )

        if checkout is None:
            from app.services.payment import PaymentService

            await PaymentService(self.session).handle_webhook(
                event=event,
                payment_id=payment_id,
                payment_status=payment_status,
                paid=paid,
                metadata=metadata,
            )
            return

        if event == "payment.canceled":
            if checkout.status == CheckoutPaymentStatus.PENDING:
                await self._cancel_checkout(checkout)
                await self.session.commit()
            return

        if event in ("payment.succeeded", "payment.waiting_for_capture"):
            if not (
                paid
                and payment_status in ("succeeded", "waiting_for_capture")
            ):
                return
            if checkout.status != CheckoutPaymentStatus.PENDING:
                return
            from app.services.user import UserService

            customer = await UserService(self.session).get_user_by_id(
                checkout.customer_id
            )
            if customer is None:
                logger.error(
                    "Cannot fulfill checkout %s: user %s not found",
                    checkout.id,
                    checkout.customer_id,
                )
                return
            await self.fulfill_checkout(checkout, customer=customer)
