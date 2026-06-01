from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aio_pika
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import database
from app.models.integration_task import IntegrationTask
from app.repositories.integration_task import IntegrationTaskRepository

logger = logging.getLogger("app")

AMQP_URL = os.getenv("AMQP_URL", "").strip()
INTEGRATION_TASK_QUEUE = os.getenv("INTEGRATION_TASK_QUEUE", "integration_tasks")


def utcnow() -> datetime:
    return datetime.utcnow()


def backoff_delay_seconds(attempts: int) -> int:
    # 10s, 20s, 40s, ... up to 30m
    base = 10 * (2 ** max(attempts - 1, 0))
    return int(min(base, 30 * 60))


@dataclass(frozen=True)
class EnqueueResult:
    task_id: int
    created: bool


class IntegrationTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IntegrationTaskRepository(session)

    async def enqueue(
        self,
        *,
        task_type: str,
        entity_type: str,
        entity_id: int,
        dedupe_key: str,
        payload: dict[str, Any],
        run_after: datetime | None = None,
    ) -> EnqueueResult:
        # Dedup via unique constraint on dedupe_key. If it already exists, just return it.
        # We avoid SELECT+INSERT race by trying insert first and catching.
        task = IntegrationTask(
            task_type=task_type,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=dedupe_key,
            payload=payload,
            status="PENDING",
            attempts=0,
            run_after=run_after,
        )
        self.repo.add(task)
        try:
            await self.session.flush()
            return EnqueueResult(task_id=task.id, created=True)
        except Exception:
            await self.session.rollback()
            from sqlalchemy import select

            stmt = select(IntegrationTask).where(IntegrationTask.dedupe_key == dedupe_key)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                raise
            return EnqueueResult(task_id=existing.id, created=False)


async def publish_task_message(
    channel: aio_pika.abc.AbstractChannel,
    *,
    task_id: int,
) -> None:
    queue = await channel.declare_queue(INTEGRATION_TASK_QUEUE, durable=True)
    body = json.dumps({"task_id": task_id}).encode("utf-8")
    message = aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
    await channel.default_exchange.publish(message, routing_key=queue.name)


async def integration_task_publisher_loop(
    *,
    poll_interval_s: float = 1.0,
    batch_size: int = 200,
) -> None:
    if not AMQP_URL:
        logger.warning("AMQP_URL is empty, integration publisher disabled")
        return

    logger.info("Integration publisher starting (queue=%s)", INTEGRATION_TASK_QUEUE)
    while True:
        try:
            connection = await aio_pika.connect_robust(AMQP_URL)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=50)
                await channel.declare_queue(INTEGRATION_TASK_QUEUE, durable=True)

                while True:
                    try:
                        async with database.session() as session:
                            repo = IntegrationTaskRepository(session)
                            due = await repo.get_due_pending(limit=batch_size)
                            if not due:
                                await asyncio.sleep(poll_interval_s)
                                continue

                            for task in due:
                                await publish_task_message(channel, task_id=task.id)
                                task.status = "PUBLISHED"
                                task.updated_at = utcnow()

                            await session.commit()
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("Integration publisher loop error")
                        await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Integration publisher cannot connect to RabbitMQ")
            await asyncio.sleep(3.0)

