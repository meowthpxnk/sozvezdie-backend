from dataclasses import dataclass

from app.schemas.database import OrderStatus


@dataclass
class OrderSpec:
    customer_id: int | None = None
    statuses: list[OrderStatus] | None = None
