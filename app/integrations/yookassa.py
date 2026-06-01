import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("app")

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_API_BASE = os.getenv(
    "YOOKASSA_API_BASE", "https://api.yookassa.ru/v3"
).rstrip("/")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "").rstrip("/")
YOOKASSA_HTTP_TIMEOUT = 30.0


@dataclass(frozen=True)
class YooKassaPaymentResult:
    payment_id: str
    status: str
    confirmation_url: str | None
    paid: bool


@dataclass(frozen=True)
class YooKassaRefundResult:
    refund_id: str
    status: str


def is_configured() -> bool:
    return bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)


def kopecks_to_amount_value(kopecks: int) -> str:
    return f"{kopecks / 100:.2f}"


def build_return_url(*, checkout_id: int) -> str:
    base = YOOKASSA_RETURN_URL or "http://localhost:3000/orders/payment/return"
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}checkout_id={checkout_id}"


def build_payment_description(*, username: str, order_id: int) -> str:
    """Описание платежа для ЮKassa (до 128 символов)."""
    nickname = username.strip().lstrip("@")
    text = f"Оплата заказа №{order_id}, пользователь @{nickname}"
    return text[:128]


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    idempotence_key: str | None = None,
) -> dict[str, Any]:
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YooKassa is not configured",
        )

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key

    url = f"{YOOKASSA_API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=YOOKASSA_HTTP_TIMEOUT) as client:
            response = await client.request(
                method,
                url,
                json=json_body,
                headers=headers,
                auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            )
    except httpx.HTTPError as error:
        logger.exception("YooKassa request failed: %s %s", method, path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YooKassa request failed",
        ) from error

    if response.status_code >= 400:
        logger.error(
            "YooKassa error %s %s: %s",
            method,
            path,
            response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YooKassa returned an error",
        )

    return response.json()


def _parse_payment(data: dict[str, Any]) -> YooKassaPaymentResult:
    confirmation = data.get("confirmation") or {}
    return YooKassaPaymentResult(
        payment_id=str(data["id"]),
        status=str(data.get("status", "")),
        confirmation_url=confirmation.get("confirmation_url"),
        paid=bool(data.get("paid")),
    )


def _parse_refund(data: dict[str, Any]) -> YooKassaRefundResult:
    return YooKassaRefundResult(
        refund_id=str(data["id"]),
        status=str(data.get("status", "")),
    )


async def create_payment(
    *,
    checkout_id: int,
    amount_kopecks: int,
    description: str,
    idempotence_key: str | None = None,
    username: str | None = None,
    order_id: int | None = None,
) -> YooKassaPaymentResult:
    metadata: dict[str, str] = {"checkout_id": str(checkout_id)}
    if username:
        metadata["username"] = username.strip().lstrip("@")
    if order_id is not None:
        metadata["order_id"] = str(order_id)

    payload = {
        "amount": {
            "value": kopecks_to_amount_value(amount_kopecks),
            "currency": "RUB",
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": build_return_url(checkout_id=checkout_id),
        },
        "description": description[:128],
        "metadata": metadata,
    }
    data = await _request(
        "POST",
        "/payments",
        json_body=payload,
        idempotence_key=idempotence_key or str(uuid.uuid4()),
    )
    result = _parse_payment(data)
    if not result.confirmation_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YooKassa did not return confirmation_url",
        )
    return result


async def get_payment(payment_id: str) -> YooKassaPaymentResult:
    data = await _request("GET", f"/payments/{payment_id}")
    return _parse_payment(data)


async def cancel_payment(payment_id: str, *, idempotence_key: str | None = None) -> YooKassaPaymentResult:
    """
    Cancel a payment in `waiting_for_capture` or `pending` state.
    For captured payments (`succeeded`) you should use refunds.
    """
    data = await _request(
        "POST",
        f"/payments/{payment_id}/cancel",
        json_body=None,
        idempotence_key=idempotence_key or str(uuid.uuid4()),
    )
    return _parse_payment(data)


async def create_refund(
    *,
    payment_id: str,
    amount_kopecks: int,
    idempotence_key: str | None = None,
) -> YooKassaRefundResult:
    if amount_kopecks <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund amount must be positive",
        )
    payload = {
        "amount": {"value": kopecks_to_amount_value(amount_kopecks), "currency": "RUB"},
        "payment_id": payment_id,
    }
    data = await _request(
        "POST",
        "/refunds",
        json_body=payload,
        idempotence_key=idempotence_key or str(uuid.uuid4()),
    )
    return _parse_refund(data)
