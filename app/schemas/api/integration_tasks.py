from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IntegrationTaskResponse(BaseModel):
    id: int
    task_type: str
    entity_type: str
    entity_id: int
    dedupe_key: str
    payload: dict[str, Any]
    status: str
    attempts: int
    run_after: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class IntegrationTasksListResponse(BaseModel):
    items: list[IntegrationTaskResponse]

