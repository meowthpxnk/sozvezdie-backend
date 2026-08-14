import json
import logging
import math
import os
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.schemas.database import DeliveryMethod

logger = logging.getLogger("app")

CDEK_CLIENT_ID = os.getenv("CDEK_CLIENT_ID", "")
CDEK_CLIENT_SECRET = os.getenv("CDEK_CLIENT_SECRET", "")
CDEK_API_BASE = os.getenv("CDEK_API_BASE", "https://api.edu.cdek.ru").rstrip(
    "/"
)
CDEK_FROM_CITY_CODE = int(os.getenv("CDEK_FROM_CITY_CODE", "137"))
CDEK_FROM_ADDRESS = os.getenv(
    "CDEK_FROM_ADDRESS",
    "г. Санкт-Петербург, ул. Печатника Григорьева, д. 8",
)
CDEK_DEFAULT_WEIGHT_G = int(os.getenv("CDEK_DEFAULT_WEIGHT_G", "1000"))
CDEK_DEFAULT_LENGTH_CM = int(os.getenv("CDEK_DEFAULT_LENGTH_CM", "20"))
CDEK_DEFAULT_WIDTH_CM = int(os.getenv("CDEK_DEFAULT_WIDTH_CM", "20"))
CDEK_DEFAULT_HEIGHT_CM = int(os.getenv("CDEK_DEFAULT_HEIGHT_CM", "10"))
CDEK_HTTP_TIMEOUT = 15.0
CDEK_PVZ_PAGE_SIZE = int(os.getenv("CDEK_PVZ_PAGE_SIZE", "1000"))
CDEK_PVZ_MAX_PAGES = int(os.getenv("CDEK_PVZ_MAX_PAGES", "20"))
# Days after today when the seller plans to hand the parcel to CDEK (for calculator `date`)
CDEK_SHIPMENT_DAYS_OFFSET = int(os.getenv("CDEK_SHIPMENT_DAYS_OFFSET", "0"))

# Common tariff codes (edu/prod may differ; calculator returns available ones)
COURIER_TARIFF_CODES = {121, 122, 137, 138, 480, 481, 482, 483}
PVZ_TARIFF_CODES = {136, 234, 366, 368, 376, 378}

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}

_cdek_request_trace: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "cdek_request_trace", default=None
)


def begin_cdek_request_trace() -> None:
    _cdek_request_trace.set([])


def _record_cdek_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    note: str | None = None,
) -> None:
    trace = _cdek_request_trace.get()
    if trace is None:
        return
    entry: dict[str, Any] = {
        "method": method.upper(),
        "url": f"{CDEK_API_BASE}{path}",
        "path": path,
    }
    if params:
        entry["params"] = params
    if json_body is not None:
        entry["body"] = json_body
    if note:
        entry["note"] = note
    trace.append(entry)


def flush_cdek_request_trace_log(
    order_id: int,
    *,
    delivery_method: str | None = None,
) -> None:
    trace = _cdek_request_trace.get()
    _cdek_request_trace.set(None)
    if not trace:
        return
    logger.info(
        "CDEK requests for order %s (delivery_method=%s), count=%d: %s",
        order_id,
        delivery_method,
        len(trace),
        json.dumps(trace, ensure_ascii=False, default=str),
    )


@dataclass(frozen=True)
class CdekTariffResult:
    delivery_cost: int
    tariff_code: int
    period_min: int
    period_max: int
    delivery_date_min: date | None = None
    delivery_date_max: date | None = None


@dataclass(frozen=True)
class CdekPvzPoint:
    code: str
    name: str
    address: str
    lat: float
    lon: float
    distance_m: float


@dataclass(frozen=True)
class CdekNearestPvzResult:
    point: CdekPvzPoint
    resolved_city_code: int | None
    pvz_candidates_count: int


def _configured() -> bool:
    return bool(CDEK_CLIENT_ID and CDEK_CLIENT_SECRET)


def _require_configured() -> None:
    if not _configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CDEK is not configured on server",
        )


async def _get_access_token() -> str:
    _require_configured()
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["access_token"]

    _record_cdek_request(
        "POST",
        "/v2/oauth/token",
        note="grant_type=client_credentials (client_secret omitted)",
    )

    url = f"{CDEK_API_BASE}/v2/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CDEK_CLIENT_ID,
        "client_secret": CDEK_CLIENT_SECRET,
    }

    try:
        async with httpx.AsyncClient(timeout=CDEK_HTTP_TIMEOUT) as client:
            response = await client.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.exception("CDEK OAuth failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="CDEK authorization failed",
        ) from exc

    token = payload.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="CDEK authorization returned no token",
        )

    expires_in = int(payload.get("expires_in", 3600))
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + expires_in
    return token


async def _api_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    _record_cdek_request(method, path, params=params, json_body=json_body)

    token = await _get_access_token()
    url = f"{CDEK_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=CDEK_HTTP_TIMEOUT) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                params=params,
            )
            response.raise_for_status()
            trace = _cdek_request_trace.get()
            if trace is not None and trace:
                trace[-1]["status"] = response.status_code
            if response.content:
                return response.json()
            return {}
    except httpx.HTTPStatusError as exc:
        trace = _cdek_request_trace.get()
        if trace is not None and trace:
            trace[-1]["status"] = exc.response.status_code
            trace[-1]["error"] = exc.response.text[:500]
        logger.error(
            "CDEK API error %s %s: %s",
            method,
            path,
            exc.response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="CDEK service error",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("CDEK request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="CDEK service is temporarily unavailable",
        ) from exc


def _default_package() -> dict[str, int]:
    return {
        "weight": CDEK_DEFAULT_WEIGHT_G,
        "length": CDEK_DEFAULT_LENGTH_CM,
        "width": CDEK_DEFAULT_WIDTH_CM,
        "height": CDEK_DEFAULT_HEIGHT_CM,
    }


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _extract_delivery_date_range(
    item: dict[str, Any],
) -> tuple[date | None, date | None]:
    raw = item.get("delivery_date_range")
    if not isinstance(raw, dict):
        return None, None
    return _parse_iso_date(raw.get("min")), _parse_iso_date(raw.get("max"))


def _tariff_item_to_result(item: dict[str, Any]) -> CdekTariffResult:
    date_min, date_max = _extract_delivery_date_range(item)
    return CdekTariffResult(
        delivery_cost=int(round(float(item["delivery_sum"]) * 100)),
        tariff_code=int(item["tariff_code"]),
        period_min=int(item.get("period_min", 1)),
        period_max=int(item.get("period_max", item.get("period_min", 3))),
        delivery_date_min=date_min,
        delivery_date_max=date_max,
    )


def _pick_tariff(
    tariffs: list[dict[str, Any]],
    delivery_method: DeliveryMethod,
) -> CdekTariffResult | None:
    allowed = (
        PVZ_TARIFF_CODES
        if delivery_method == DeliveryMethod.PICKUP_POINT
        else COURIER_TARIFF_CODES
    )
    candidates: list[CdekTariffResult] = []
    for item in tariffs:
        code = item.get("tariff_code")
        if code not in allowed:
            continue
        if item.get("delivery_sum") is None:
            continue
        candidates.append(_tariff_item_to_result(item))
    if not candidates:
        forbidden = (
            COURIER_TARIFF_CODES
            if delivery_method == DeliveryMethod.PICKUP_POINT
            else PVZ_TARIFF_CODES
        )
        for item in tariffs:
            cost = item.get("delivery_sum")
            code = item.get("tariff_code")
            if cost is None or code is None or code in forbidden:
                continue
            candidates.append(_tariff_item_to_result(item))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t.delivery_cost)


def planned_shipment_date(*, days_offset: int | None = None) -> date:
    offset = CDEK_SHIPMENT_DAYS_OFFSET if days_offset is None else days_offset
    return date.today() + timedelta(days=max(offset, 0))


def format_shipment_datetime(shipment_date: date | None = None) -> str:
    """CDEK calculator `date`: yyyy-MM-dd'T'HH:mm:ss+0300 (no colon in offset)."""
    day = shipment_date or planned_shipment_date()
    return f"{day.isoformat()}T10:00:00+0300"


def build_available_dates(
    period_min: int,
    period_max: int,
    *,
    delivery_date_min: date | None = None,
    delivery_date_max: date | None = None,
    days_ahead: int = 14,
) -> list[str]:
    if (
        delivery_date_min
        and delivery_date_max
        and delivery_date_min <= delivery_date_max
    ):
        start, end = delivery_date_min, delivery_date_max
        max_days = (end - start).days + 1
    else:
        start = date.today() + timedelta(days=max(period_min, 1))
        end = date.today() + timedelta(
            days=max(period_max, period_min) + days_ahead
        )
        max_days = days_ahead

    dates: list[str] = []
    current = start
    while current <= end and len(dates) < max_days:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def is_delivery_date_available(
    selected: date,
    *,
    delivery_date_min: date | None,
    delivery_date_max: date | None,
    period_min: int,
    period_max: int,
) -> bool:
    if delivery_date_min and delivery_date_max:
        return delivery_date_min <= selected <= delivery_date_max
    fallback_dates = build_available_dates(
        period_min,
        period_max,
        delivery_date_min=None,
        delivery_date_max=None,
    )
    return selected.isoformat() in fallback_dates


async def calculate_tariff(
    delivery_method: DeliveryMethod,
    *,
    address: str,
    postal_code: str | None = None,
    city_code: int | None = None,
    lat: float | None = None,
    lon: float | None = None,
    shipment_date: date | None = None,
) -> CdekTariffResult:
    to_location: dict[str, Any] = {"address": address}
    if postal_code:
        to_location["postal_code"] = postal_code
    if city_code:
        to_location["code"] = city_code

    body = {
        "type": 1,
        "date": format_shipment_datetime(shipment_date),
        "from_location": {
            "code": CDEK_FROM_CITY_CODE,
            "address": CDEK_FROM_ADDRESS,
        },
        "to_location": to_location,
        "packages": [_default_package()],
    }

    payload = await _api_request(
        "POST", "/v2/calculator/tarifflist", json_body=body
    )

    if isinstance(payload, dict):
        raw_tariffs = payload.get("tariff_codes") or []
    elif isinstance(payload, list):
        raw_tariffs = payload
    else:
        raw_tariffs = []

    result = _pick_tariff(raw_tariffs, delivery_method)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CDEK tariff available for this address",
        )
    return result


def _city_search_queries(city_name: str) -> list[str]:
    name = city_name.strip()
    if not name:
        return []
    queries = [name]
    lower = name.lower()
    if lower in {
        "спб",
        "питер",
        "петербург",
        "saint petersburg",
        "st petersburg",
    }:
        queries.append("Санкт-Петербург")
    elif lower.startswith("санкт"):
        queries.append("Петербург")
    elif lower in {"мск", "moscow"}:
        queries.append("Москва")
    return list(dict.fromkeys(queries))


def _pick_nearest_city_code(
    cities: list[dict[str, Any]],
    lat: float,
    lon: float,
) -> int | None:
    best_code: int | None = None
    best_dist = float("inf")
    for item in cities:
        code = item.get("code")
        if code is None:
            continue
        clat = item.get("latitude")
        clon = item.get("longitude")
        if clat is None or clon is None:
            continue
        dist = _haversine_m(lat, lon, float(clat), float(clon))
        if dist < best_dist:
            best_dist = dist
            best_code = int(code)
    return best_code


async def _fetch_cities(params: dict[str, Any]) -> list[dict[str, Any]]:
    payload = await _api_request("GET", "/v2/location/cities", params=params)
    if isinstance(payload, list):
        return payload
    return []


async def resolve_city_code(
    *,
    lat: float,
    lon: float,
    postal_code: str | None = None,
    city_name: str | None = None,
) -> int | None:
    candidates: list[dict[str, Any]] = []
    seen_codes: set[int] = set()

    def _add(items: list[dict[str, Any]]) -> None:
        for item in items:
            code = item.get("code")
            if code is None:
                continue
            code_int = int(code)
            if code_int in seen_codes:
                continue
            seen_codes.add(code_int)
            candidates.append(item)

    if postal_code:
        _add(
            await _fetch_cities(
                {
                    "country_codes": "RU",
                    "postal_code": postal_code,
                    "size": 20,
                }
            )
        )

    if city_name:
        for query in _city_search_queries(city_name):
            _add(
                await _fetch_cities(
                    {
                        "country_codes": "RU",
                        "city": query,
                        "size": 50,
                    }
                )
            )

    if not candidates:
        return None

    return _pick_nearest_city_code(candidates, lat, lon)


def _parse_delivery_point(
    point: dict[str, Any],
    *,
    lat: float,
    lon: float,
) -> CdekPvzPoint | None:
    location = point.get("location") or {}
    plat = location.get("latitude")
    plon = location.get("longitude")
    if plat is None or plon is None:
        return None
    plat_f, plon_f = float(plat), float(plon)
    return CdekPvzPoint(
        code=str(point.get("code", "")),
        name=str(point.get("name", "")),
        address=str(location.get("address", "")),
        lat=plat_f,
        lon=plon_f,
        distance_m=_haversine_m(lat, lon, plat_f, plon_f),
    )


async def _fetch_pvz_pages(
    params: dict[str, Any], *, lat: float, lon: float
) -> list[CdekPvzPoint]:
    result: list[CdekPvzPoint] = []
    for page in range(CDEK_PVZ_MAX_PAGES):
        page_params = {
            **params,
            "type": "PVZ",
            "size": CDEK_PVZ_PAGE_SIZE,
            "page": page,
        }
        payload = await _api_request(
            "GET", "/v2/deliverypoints", params=page_params
        )
        points = payload if isinstance(payload, list) else []
        if not points:
            break

        for point in points:
            parsed = _parse_delivery_point(point, lat=lat, lon=lon)
            if parsed is not None:
                result.append(parsed)

        if len(points) < CDEK_PVZ_PAGE_SIZE:
            break

    return result


async def _collect_pvz_candidates(
    *,
    lat: float,
    lon: float,
    city_code: int | None = None,
    postal_code: str | None = None,
    city_name: str | None = None,
) -> tuple[list[CdekPvzPoint], int | None]:
    resolved_city = city_code
    if resolved_city is None:
        resolved_city = await resolve_city_code(
            lat=lat,
            lon=lon,
            postal_code=postal_code,
            city_name=city_name,
        )

    all_points: list[CdekPvzPoint] = []

    if resolved_city is not None:
        all_points = await _fetch_pvz_pages(
            {"city_code": resolved_city},
            lat=lat,
            lon=lon,
        )

    if not all_points and postal_code:
        all_points = await _fetch_pvz_pages(
            {"postal_code": postal_code},
            lat=lat,
            lon=lon,
        )

    if not all_points:
        logger.warning(
            "CDEK PVZ not found: lat=%.5f lon=%.5f city_code=%s postal=%s city=%s",
            lat,
            lon,
            resolved_city,
            postal_code,
            city_name,
        )

    all_points.sort(key=lambda p: p.distance_m)
    return all_points, resolved_city


async def get_delivery_points(
    *,
    lat: float,
    lon: float,
    city_code: int | None = None,
    postal_code: str | None = None,
    city_name: str | None = None,
    limit: int = 20,
) -> list[CdekPvzPoint]:
    all_points, resolved_city = await _collect_pvz_candidates(
        lat=lat,
        lon=lon,
        city_code=city_code,
        postal_code=postal_code,
        city_name=city_name,
    )
    if not all_points:
        return []

    logger.debug(
        "CDEK PVZ search: city_code=%s candidates=%d nearest_dist=%.0fm",
        resolved_city,
        len(all_points),
        all_points[0].distance_m,
    )
    return all_points[:limit]


async def find_nearest_pvz(
    lat: float,
    lon: float,
    *,
    city_code: int | None = None,
    postal_code: str | None = None,
    city_name: str | None = None,
) -> CdekNearestPvzResult | None:
    all_points, resolved_city = await _collect_pvz_candidates(
        lat=lat,
        lon=lon,
        city_code=city_code,
        postal_code=postal_code,
        city_name=city_name,
    )
    if not all_points:
        return None

    nearest = all_points[0]
    logger.info(
        "CDEK nearest PVZ: code=%s dist=%.0fm city_code=%s candidates=%d "
        "pvz=(%.5f, %.5f) address=(%.5f, %.5f)",
        nearest.code,
        nearest.distance_m,
        resolved_city,
        len(all_points),
        nearest.lat,
        nearest.lon,
        lat,
        lon,
    )

    return CdekNearestPvzResult(
        point=nearest,
        resolved_city_code=resolved_city,
        pvz_candidates_count=len(all_points),
    )


async def create_order(
    *,
    tariff_code: int,
    delivery_method: DeliveryMethod,
    recipient_name: str,
    recipient_phone: str,
    address: str,
    postal_code: str | None,
    city_code: int | None,
    pvz_code: str | None = None,
    flat: str | None = None,
    order_number: str,
) -> str | None:
    to_location: dict[str, Any] = {"address": address}
    if postal_code:
        to_location["postal_code"] = postal_code
    if city_code:
        to_location["code"] = city_code

    recipient: dict[str, Any] = {
        "name": recipient_name,
        "phones": [{"number": recipient_phone}],
    }

    delivery_point = (
        pvz_code if delivery_method == DeliveryMethod.PICKUP_POINT else None
    )
    if flat and delivery_method == DeliveryMethod.COURIER:
        to_location["address"] = f"{address}, кв {flat}"

    body: dict[str, Any] = {
        "type": 1,
        "number": order_number,
        "tariff_code": tariff_code,
        "comment": f"Order {order_number}",
        "from_location": {
            "code": CDEK_FROM_CITY_CODE,
            "address": CDEK_FROM_ADDRESS,
        },
        "to_location": to_location,
        "recipient": recipient,
        "packages": [_default_package()],
    }
    if delivery_point:
        body["delivery_point"] = delivery_point

    try:
        payload = await _api_request("POST", "/v2/orders", json_body=body)
    except HTTPException:
        logger.exception(
            "CDEK order creation failed for order %s", order_number
        )
        return None

    if isinstance(payload, dict):
        entity = payload.get("entity") or payload
        uuid = entity.get("uuid") if isinstance(entity, dict) else None
        return str(uuid) if uuid else None
    return None


async def create_delivery_appointment(
    *,
    order_uuid: str,
    delivery_date: date,
    pvz_code: str | None = None,
) -> str | None:
    """
    Register delivery agreement with CDEK (recipient date / PVZ handover window).
    Requires an existing CDEK order UUID.
    """
    body: dict[str, Any] = {
        "order_uuid": order_uuid,
        "date": delivery_date.isoformat(),
    }
    if pvz_code:
        body["delivery_point"] = pvz_code

    try:
        payload = await _api_request(
            "POST", "/v2/delivery_appointment", json_body=body
        )
    except HTTPException:
        logger.exception(
            "CDEK delivery appointment failed for order %s", order_uuid
        )
        return None

    if isinstance(payload, dict):
        entity = payload.get("entity") or payload
        uuid = entity.get("uuid") if isinstance(entity, dict) else None
        if uuid:
            logger.info(
                "CDEK delivery appointment: order_uuid=%s appointment_uuid=%s date=%s",
                order_uuid,
                uuid,
                delivery_date.isoformat(),
            )
            return str(uuid)
    return None


async def cancel_order(*, order_uuid: str) -> bool:
    """
    Cancel (delete) an order by UUID in CDEK API v2.
    Note: CDEK typically allows cancellation only before final statuses.
    """
    if not order_uuid:
        return False
    try:
        await _api_request("DELETE", f"/v2/orders/{order_uuid}")
        return True
    except HTTPException:
        logger.exception("CDEK order cancel failed for %s", order_uuid)
        return False
