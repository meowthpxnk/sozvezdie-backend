from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import aio_pika
from dotenv import load_dotenv

from app.core.database import database
from app.integrations import cdek, yookassa
from app.models import Order
from app.repositories.integration_task import IntegrationTaskRepository
from app.repositories.order import OrderRepository
from app.schemas.database import DeliveryMethod, OrderStatus, PaymentMethod
from app.services.integration_tasks import (
    AMQP_URL,
    INTEGRATION_TASK_QUEUE,
    backoff_delay_seconds,
)

logger = logging.getLogger("app")


def utcnow() -> datetime:
    return datetime.utcnow()


def _is_retryable_error(exc: Exception) -> bool:
    # Conservative: retry on network/5xx style errors (we keep it broad).
    # Non-retryable errors should be handled explicitly in task handlers.
    return True


async def _handle_task(task_type: str, payload: dict[str, Any]) -> None:
    if task_type == "CDEK_CREATE_ORDER":
        await _task_cdek_create_order(payload)
        return
    if task_type == "CDEK_CANCEL_ORDER":
        await _task_cdek_cancel_order(payload)
        return
    if task_type == "YOOKASSA_CANCEL_OR_REFUND":
        await _task_yookassa_cancel_or_refund(payload)
        return
    raise ValueError(f"Unknown task_type: {task_type}")


async def _task_cdek_create_order(payload: dict[str, Any]) -> None:
    order_id = int(payload["order_id"])
    async with database.session() as session:
        order_repo = OrderRepository(session)
        order = await order_repo.get_order_by_id(order_id)
        if order is None:
            return
        if order.status == OrderStatus.CANCELED:
            return
        if order.cdek_order_uuid:
            return

        if order.delivery_method not in (
            DeliveryMethod.COURIER,
            DeliveryMethod.PICKUP_POINT,
        ):
            return
        if not order.cdek_tariff_code:
            return

        recipient_name = payload.get("recipient_name") or "Customer"
        recipient_phone = payload.get("recipient_phone") or "70000000000"

        cdek_uuid = await cdek.create_order(
            tariff_code=int(order.cdek_tariff_code),
            delivery_method=order.delivery_method,
            recipient_name=str(recipient_name),
            recipient_phone=str(recipient_phone),
            address=str(order.delivery_address_text or ""),
            postal_code=None,
            city_code=None,
            pvz_code=order.cdek_pvz_code,
            flat=order.delivery_flat,
            order_number=str(order.id),
        )
        if not cdek_uuid:
            order.cdek_error = "CDEK order registration failed"
            await session.commit()
            raise RuntimeError("CDEK create_order returned no uuid")

        order.cdek_order_uuid = cdek_uuid
        order.cdek_error = None
        await session.commit()

        if order.delivery_date:
            appointment_uuid = await cdek.create_delivery_appointment(
                order_uuid=cdek_uuid,
                delivery_date=order.delivery_date,
                pvz_code=order.cdek_pvz_code,
            )
            if not appointment_uuid:
                order.cdek_error = "CDEK delivery appointment failed"
                await session.commit()


async def _task_cdek_cancel_order(payload: dict[str, Any]) -> None:
    order_uuid = str(payload.get("cdek_order_uuid") or "")
    if not order_uuid:
        return
    ok = await cdek.cancel_order(order_uuid=order_uuid)
    if not ok:
        raise RuntimeError("CDEK cancel failed")


async def _task_yookassa_cancel_or_refund(payload: dict[str, Any]) -> None:
    order_id = int(payload["order_id"])
    async with database.session() as session:
        order_repo = OrderRepository(session)
        order = await order_repo.get_order_by_id(order_id)
        if order is None:
            return
        if order.payment_method != PaymentMethod.CARD_ONLINE:
            return
        if not order.yookassa_payment_id:
            return

        payment = await yookassa.get_payment(order.yookassa_payment_id)
        total_kopecks = int(payload.get("total_kopecks") or 0)
        if total_kopecks <= 0:
            # Fallback compute (requires order_items loaded)
            items_total = sum(i.price_at_time * i.quantity for i in order.order_items)
            total_kopecks = int(items_total + order.delivery_cost)

        if payment.status == "canceled":
            return
        if payment.paid and payment.status == "succeeded":
            await yookassa.create_refund(
                payment_id=payment.payment_id,
                amount_kopecks=total_kopecks,
                idempotence_key=f"order-{order.id}-refund",
            )
            return
        if payment.status in ("waiting_for_capture", "pending"):
            await yookassa.cancel_payment(
                payment.payment_id,
                idempotence_key=f"order-{order.id}-cancel",
            )
            return


async def _process_message(task_id: int) -> None:
    async with database.session() as session:
        repo = IntegrationTaskRepository(session)
        task = await repo.get_by_id(task_id, for_update=True)
        if task is None:
            return

        # Publisher can publish message before status commit due to transaction timing.
        # Accept PENDING as well to avoid dropping valid tasks.
        if task.status not in ("PENDING", "PUBLISHED", "PROCESSING"):
            return

        task.status = "PROCESSING"
        task.updated_at = utcnow()
        await session.commit()

    # Run handler outside transaction (can be long)
    try:
        await _handle_task(task.task_type, dict(task.payload))
    except Exception as exc:
        async with database.session() as session:
            repo = IntegrationTaskRepository(session)
            locked = await repo.get_by_id(task_id, for_update=True)
            if locked is None:
                return
            locked.attempts += 1
            locked.last_error = str(exc)[:2000]
            delay = backoff_delay_seconds(locked.attempts)
            locked.run_after = utcnow() + timedelta(seconds=delay)
            locked.status = "PENDING"
            locked.updated_at = utcnow()
            await session.commit()
        raise

    async with database.session() as session:
        repo = IntegrationTaskRepository(session)
        locked = await repo.get_by_id(task_id, for_update=True)
        if locked is None:
            return
        locked.status = "SUCCEEDED"
        locked.updated_at = utcnow()
        await session.commit()


async def main() -> None:
    load_dotenv()

    if not AMQP_URL:
        logger.warning("AMQP_URL is empty, integration worker disabled")
        return

    logger.info("Integration worker starting (queue=%s)", INTEGRATION_TASK_QUEUE)
    while True:
        try:
            connection = await aio_pika.connect_robust(AMQP_URL)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)
                queue = await channel.declare_queue(INTEGRATION_TASK_QUEUE, durable=True)

                async with queue.iterator() as qiterator:
                    async for message in qiterator:
                        async with message.process(ignore_processed=True):
                            body = json.loads(message.body.decode("utf-8"))
                            task_id = int(body["task_id"])
                            try:
                                await _process_message(task_id)
                            except Exception:
                                logger.exception(
                                    "Task %s failed, scheduled retry", task_id
                                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Integration worker cannot connect to RabbitMQ")
            await asyncio.sleep(3.0)


if __name__ == "__main__":
    asyncio.run(main())

