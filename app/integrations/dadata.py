import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("app")

DADATA_API_KEY = os.getenv("DADATA_API_KEY", "")
DADATA_SUGGEST_URL = (
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
)
DADATA_GEOLOCATE_URL = (
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address"
)
DADATA_HTTP_TIMEOUT = 10.0


def _headers() -> dict[str, str]:
    if not DADATA_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DaData is not configured on server",
        )
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {DADATA_API_KEY}",
    }


def normalize_suggestion(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data") or {}
    return {
        "value": item.get("value"),
        "unrestricted_value": item.get("unrestricted_value"),
        "city": data.get("city"),
        "street": data.get("street"),
        "house": data.get("house"),
        "flat": data.get("flat"),
        "postal_code": data.get("postal_code"),
        "geo_lat": data.get("geo_lat"),
        "geo_lon": data.get("geo_lon"),
        "fias_level": data.get("fias_level"),
        "qc_geo": data.get("qc_geo"),
        "data": data,
    }


async def suggest_address(
    query: str,
    *,
    count: int = 10,
    restrict_to_house: bool = False,
    allow_flat: bool = False,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"query": query, "count": min(count, 20)}
    if restrict_to_house:
        body["from_bound"] = {"value": "city"}
        body["to_bound"] = {"value": "house"}
    elif allow_flat:
        body["from_bound"] = {"value": "city"}
        body["to_bound"] = {"value": "flat"}

    try:
        async with httpx.AsyncClient(timeout=DADATA_HTTP_TIMEOUT) as client:
            response = await client.post(
                DADATA_SUGGEST_URL,
                headers=_headers(),
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.exception("DaData suggest failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Address suggestions are temporarily unavailable",
        ) from exc

    suggestions = payload.get("suggestions") or []
    return [normalize_suggestion(item) for item in suggestions]


async def geolocate_address(
    lat: float,
    lon: float,
    *,
    count: int = 5,
    radius_meters: int = 100,
) -> list[dict[str, Any]]:
    body = {
        "lat": lat,
        "lon": lon,
        "count": min(count, 20),
        "radius_meters": min(radius_meters, 1000),
    }

    try:
        async with httpx.AsyncClient(timeout=DADATA_HTTP_TIMEOUT) as client:
            response = await client.post(
                DADATA_GEOLOCATE_URL,
                headers=_headers(),
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.exception("DaData geolocate failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Geolocation address lookup is temporarily unavailable",
        ) from exc

    suggestions = payload.get("suggestions") or []
    return [normalize_suggestion(item) for item in suggestions]
