from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration_task import IntegrationTask


class IntegrationTaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, task: IntegrationTask) -> IntegrationTask:
        self.session.add(task)
        return task

    async def get_by_id(self, task_id: int, *, for_update: bool = False) -> IntegrationTask | None:
        stmt = select(IntegrationTask).where(IntegrationTask.id == task_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_due_pending(self, *, limit: int = 100) -> list[IntegrationTask]:
        now = datetime.utcnow()
        stmt = (
            select(IntegrationTask)
            .where(
                and_(
                    IntegrationTask.status == "PENDING",
                    (IntegrationTask.run_after.is_(None) | (IntegrationTask.run_after <= now)),
                )
            )
            .order_by(IntegrationTask.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

