"""Minimal CDEK API client for the debug tracker (test / prod via env)."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

CDEK_CLIENT_ID = os.getenv("CDEK_CLIENT_ID", "")
CDEK_CLIENT_SECRET = os.getenv("CDEK_CLIENT_SECRET", "")
CDEK_API_BASE = os.getenv("CDEK_API_BASE", "https://api.edu.cdek.ru").rstrip("/")
CDEK_HTTP_TIMEOUT = 20.0

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class CdekClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


async def _get_access_token() -> str:
    if not CDEK_CLIENT_ID or not CDEK_CLIENT_SECRET:
        raise CdekClientError(
            "CDEK_CLIENT_ID / CDEK_CLIENT_SECRET not set (load backend/.env)"
        )

    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["access_token"]

    url = f"{CDEK_API_BASE}/v2/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CDEK_CLIENT_ID,
        "client_secret": CDEK_CLIENT_SECRET,
    }

    async with httpx.AsyncClient(timeout=CDEK_HTTP_TIMEOUT) as client:
        response = await client.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code >= 400:
        raise CdekClientError(
            "CDEK OAuth failed",
            status_code=response.status_code,
            body=_safe_json(response),
        )

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise CdekClientError("CDEK OAuth returned no access_token", body=payload)

    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + int(payload.get("expires_in", 3600))
    return token


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


async def _api_get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    token = await _get_access_token()
    url = f"{CDEK_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=CDEK_HTTP_TIMEOUT) as client:
        response = await client.get(url, headers=headers, params=params)

    if response.status_code >= 400:
        raise CdekClientError(
            f"CDEK GET {path} failed",
            status_code=response.status_code,
            body=_safe_json(response),
        )

    if not response.content:
        return {}
    return response.json()


async def get_order_by_uuid(order_uuid: str) -> dict[str, Any]:
    return await _api_get(f"/v2/orders/{order_uuid}")


async def get_order_by_cdek_number(cdek_number: str) -> dict[str, Any]:
    return await _api_get("/v2/orders", params={"cdek_number": cdek_number})


def api_base() -> str:
    return CDEK_API_BASE
