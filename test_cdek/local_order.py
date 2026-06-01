"""Read local order row from PostgreSQL (same DB as main app)."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_engine: Engine | None = None


def _database_uri() -> str:
    uri = os.getenv("DATABASE_URI", "")
    if not uri:
        raise RuntimeError("DATABASE_URI is not set")
    return uri.replace("+asyncpg", "+psycopg2")


def _engine_instance() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_database_uri(), pool_pre_ping=True)
    return _engine


def fetch_local_order(order_id: int) -> dict[str, Any] | None:
    sql = text(
        """
        SELECT
            id,
            status,
            delivery_method,
            delivery_cost,
            delivery_date,
            delivery_address_text,
            cdek_pvz_code,
            cdek_pvz_address,
            cdek_order_uuid,
            cdek_tariff_code,
            cdek_error,
            created_at
        FROM "order"
        WHERE id = :order_id
        """
    )
    with _engine_instance().connect() as conn:
        row = conn.execute(sql, {"order_id": order_id}).mappings().first()
    if row is None:
        return None
    data = dict(row)
    if data.get("delivery_date") is not None:
        data["delivery_date"] = data["delivery_date"].isoformat()
    if data.get("created_at") is not None:
        data["created_at"] = data["created_at"].isoformat()
    if data.get("delivery_method") is not None:
        data["delivery_method"] = str(data["delivery_method"])
    if data.get("status") is not None:
        data["status"] = str(data["status"])
    return data
