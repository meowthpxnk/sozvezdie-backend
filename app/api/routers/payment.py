import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.api.dependencies import DatabaseDepends
from app.services.checkout_payment import CheckoutPaymentService

logger = logging.getLogger("app")

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.post("/webhook")
async def yookassa_webhook(
    request: Request,
    session: DatabaseDepends,
) -> dict[str, str]:
    try:
        body: dict[str, Any] = await request.json()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        ) from error

    if body.get("type") != "notification":
        return {"status": "ignored"}

    event = body.get("event")
    payment_object = body.get("object") or {}
    payment_id = payment_object.get("id")
    if not event or not payment_id:
        return {"status": "ignored"}

    try:
        await CheckoutPaymentService(session).handle_webhook(
            event=str(event),
            payment_id=str(payment_id),
            payment_status=str(payment_object.get("status", "")),
            paid=bool(payment_object.get("paid")),
            metadata=payment_object.get("metadata"),
        )
    except Exception:
        logger.exception("YooKassa webhook processing failed for %s", payment_id)
        raise
    return {"status": "ok"}
