from dataclasses import dataclass

from app.schemas.database import OrderStatus

DELIVERED_ARCHIVE_GRACE_DAYS = 7


@dataclass
class OrderSpec:
    customer_id: int | None = None
    statuses: list[OrderStatus] | None = None
    archive: bool | None = None
    search: str | None = None
    limit: int | None = None
    offset: int = 0
