import logging
import os
import uuid
from typing import Any

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("app")

RUSENDER_API_TOKEN = os.getenv("RUSENDER_API_TOKEN", "")
RUSENDER_KEY_ID = os.getenv("RUSENDER_KEY_ID", "")
RUSENDER_FROM_EMAIL = os.getenv(
    "RUSENDER_FROM_EMAIL", "support@constellationshop.ru"
)
RUSENDER_FROM_NAME = os.getenv("RUSENDER_FROM_NAME", "Команда Созвездие")
RUSENDER_API_BASE = os.getenv(
    "RUSENDER_API_BASE", "https://api.rusender.ru"
).rstrip("/")
RUSENDER_HTTP_TIMEOUT = 20.0


def is_configured() -> bool:
    return bool(RUSENDER_API_TOKEN and RUSENDER_KEY_ID)


async def send_mail(
    *,
    to_email: str,
    to_name: str | None,
    subject: str,
    html: str,
    idempotency_key: str | None = None,
) -> str:
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Почтовый сервис не настроен",
        )

    payload: dict[str, Any] = {
        "idempotencyKey": (idempotency_key or str(uuid.uuid4()))[:150],
        "mail": {
            "to": {
                "email": to_email,
                "name": (to_name or "").strip() or to_email,
            },
            "from": {
                "email": RUSENDER_FROM_EMAIL,
                "name": RUSENDER_FROM_NAME,
            },
            "subject": subject[:255],
            "html": html,
        },
    }

    url = (
        f"{RUSENDER_API_BASE}/api/v1/external-mails/send/{RUSENDER_KEY_ID}"
    )
    try:
        async with httpx.AsyncClient(timeout=RUSENDER_HTTP_TIMEOUT) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {RUSENDER_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as error:
        logger.exception("RuSender request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить письмо",
        ) from error

    if response.status_code >= 400:
        logger.error(
            "RuSender error %s: %s",
            response.status_code,
            response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить письмо",
        )

    data = response.json()
    return str(data.get("uuid") or "")
