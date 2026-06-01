from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.moderation_access import ModerationAccessDepends
from app.models.integration_task import IntegrationTask
from app.schemas.api.integration_tasks import (
    IntegrationTaskResponse,
    IntegrationTasksListResponse,
)

router = APIRouter(prefix="/integration-tasks", tags=["IntegrationTasks"])


def _to_response(task: IntegrationTask) -> IntegrationTaskResponse:
    return IntegrationTaskResponse(
        id=task.id,
        task_type=task.task_type,
        entity_type=task.entity_type,
        entity_id=task.entity_id,
        dedupe_key=task.dedupe_key,
        payload=task.payload or {},
        status=task.status,
        attempts=task.attempts,
        run_after=task.run_after,
        last_error=task.last_error,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("")
async def list_tasks(
    _: ModerationAccessDepends,
    session: DatabaseDepends,
    status_filter: str | None = Query(default=None, alias="status"),
    task_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> IntegrationTasksListResponse:
    stmt = select(IntegrationTask).order_by(IntegrationTask.id.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(IntegrationTask.status == status_filter)
    if task_type:
        stmt = stmt.where(IntegrationTask.task_type == task_type)
    result = await session.execute(stmt)
    tasks = list(result.scalars().all())
    return IntegrationTasksListResponse(items=[_to_response(t) for t in tasks])


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int,
    _: ModerationAccessDepends,
    session: DatabaseDepends,
) -> IntegrationTaskResponse:
    task = await session.get(IntegrationTask, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    task.status = "PENDING"
    task.run_after = None
    task.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(task)
    return _to_response(task)

