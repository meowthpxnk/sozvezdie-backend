from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.database import DeliveryMethod


class AddressSuggestionResponse(BaseModel):
    value: str | None
    unrestricted_value: str | None
    city: str | None
    street: str | None
    house: str | None
    flat: str | None
    postal_code: str | None
    geo_lat: str | None
    geo_lon: str | None
    fias_level: str | None
    qc_geo: str | None


class AddressSuggestionsListResponse(BaseModel):
    items: list[AddressSuggestionResponse]


class PvzPointResponse(BaseModel):
    code: str
    name: str
    address: str
    lat: float
    lon: float
    distance_m: float


class PvzListResponse(BaseModel):
    items: list[PvzPointResponse]


class DeliveryCalculateItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)


class DeliveryAddressInput(BaseModel):
    formatted_address: str
    city: str | None = None
    street: str | None = None
    house: str | None = None
    flat: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    cdek_city_code: int | None = None
    user_address_id: int | None = None


class DeliveryCalculateRequest(BaseModel):
    delivery_method: DeliveryMethod
    address: DeliveryAddressInput
    items: list[DeliveryCalculateItemRequest] = Field(default_factory=list)


class DeliveryCalculateResponse(BaseModel):
    delivery_cost: int
    tariff_code: int
    period_min: int
    period_max: int
    available_dates: list[str]
    delivery_date_min: str | None = None
    delivery_date_max: str | None = None
    shipment_date: str | None = None
    pvz_code: str | None = None
    pvz_name: str | None = None
    pvz_address: str | None = None
    pvz_lat: float | None = None
    pvz_lon: float | None = None
    pvz_distance_m: float | None = None
    pvz_search_city_code: int | None = None


class OrderDeliveryAddressPayload(BaseModel):
    formatted_address: str
    city: str | None = None
    street: str | None = None
    house: str | None = None
    flat: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    cdek_city_code: int | None = None
    pvz_code: str | None = None
    user_address_id: int | None = None
    dadata_raw: dict[str, Any] | None = None


class UserAddressResponse(BaseModel):
    id: int
    label: str | None
    formatted_address: str
    city: str | None
    street: str | None
    house: str | None
    flat: str | None
    lat: float | None
    lon: float | None
    postal_code: str | None
    is_default: bool


class UserAddressListResponse(BaseModel):
    items: list[UserAddressResponse]


class UserAddressCreateRequest(BaseModel):
    label: str | None = None
    formatted_address: str
    city: str | None = None
    street: str | None = None
    house: str | None = None
    flat: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    cdek_city_code: int | None = None
    is_default: bool = False
    dadata_raw: dict[str, Any] | None = None


class UserAddressUpdateRequest(BaseModel):
    label: str | None = None
    is_default: bool | None = None
