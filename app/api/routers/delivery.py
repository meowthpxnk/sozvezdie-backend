from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies.auth import BearerAuthDepends
from app.schemas.api.delivery import (
    DeliveryCalculateRequest,
    DeliveryCalculateResponse,
    AddressSuggestionsListResponse,
    PvzListResponse,
)
from app.services.delivery import DeliveryService

router = APIRouter(prefix="/delivery", tags=["Delivery"])


@router.get("/address/suggest")
async def suggest_address(
    _token: BearerAuthDepends,
    q: str = Query(..., min_length=1, max_length=300),
    restrict_to_house: bool = Query(default=False),
    allow_flat: bool = Query(default=False),
) -> AddressSuggestionsListResponse:
    return await DeliveryService().suggest(
        q,
        restrict_to_house=restrict_to_house,
        allow_flat=allow_flat,
    )


@router.get("/address/geolocate")
async def geolocate_address(
    _token: BearerAuthDepends,
    lat: float = Query(...),
    lon: float = Query(...),
) -> AddressSuggestionsListResponse:
    return await DeliveryService().geolocate(lat, lon)


@router.get("/pvz")
async def list_pvz(
    _token: BearerAuthDepends,
    lat: float = Query(...),
    lon: float = Query(...),
    city_code: int | None = Query(default=None),
) -> PvzListResponse:
    return await DeliveryService().list_pvz(lat, lon, city_code)


@router.post("/calculate")
async def calculate_delivery(
    _token: BearerAuthDepends,
    data: DeliveryCalculateRequest,
) -> DeliveryCalculateResponse:
    print(data)
    try:
        return await DeliveryService().calculate(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
