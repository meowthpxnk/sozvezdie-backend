from app.integrations import cdek, dadata
from app.schemas.api.delivery import (
    AddressSuggestionResponse,
    AddressSuggestionsListResponse,
    DeliveryAddressInput,
    DeliveryCalculateRequest,
    DeliveryCalculateResponse,
    PvzListResponse,
    PvzPointResponse,
)
from app.schemas.database import DeliveryMethod
from app.utils.address_flat import require_flat_for_courier


def _to_suggestion(item: dict) -> AddressSuggestionResponse:
    return AddressSuggestionResponse(
        value=item.get("value"),
        unrestricted_value=item.get("unrestricted_value"),
        city=item.get("city"),
        street=item.get("street"),
        house=item.get("house"),
        flat=item.get("flat"),
        postal_code=item.get("postal_code"),
        geo_lat=item.get("geo_lat"),
        geo_lon=item.get("geo_lon"),
        fias_level=item.get("fias_level"),
        qc_geo=item.get("qc_geo"),
    )


def _validate_address_for_delivery(address: DeliveryAddressInput) -> None:
    if not address.formatted_address.strip():
        raise ValueError("Address is required")
    if address.lat is None or address.lon is None:
        raise ValueError("Address coordinates are required")
    if not address.house:
        raise ValueError("Please select an address with house number")


class DeliveryService:
    async def suggest(
        self,
        query: str,
        *,
        restrict_to_house: bool = False,
        allow_flat: bool = False,
    ) -> AddressSuggestionsListResponse:
        items = await dadata.suggest_address(
            query,
            restrict_to_house=restrict_to_house,
            allow_flat=allow_flat,
        )
        return AddressSuggestionsListResponse(
            items=[_to_suggestion(item) for item in items]
        )

    async def geolocate(self, lat: float, lon: float) -> AddressSuggestionsListResponse:
        items = await dadata.geolocate_address(lat, lon)
        return AddressSuggestionsListResponse(
            items=[_to_suggestion(item) for item in items]
        )

    async def list_pvz(
        self,
        lat: float,
        lon: float,
        city_code: int | None = None,
        postal_code: str | None = None,
        city_name: str | None = None,
    ) -> PvzListResponse:
        points = await cdek.get_delivery_points(
            lat=lat,
            lon=lon,
            city_code=city_code,
            postal_code=postal_code,
            city_name=city_name,
        )
        return PvzListResponse(
            items=[
                PvzPointResponse(
                    code=p.code,
                    name=p.name,
                    address=p.address,
                    lat=p.lat,
                    lon=p.lon,
                    distance_m=p.distance_m,
                )
                for p in points
            ]
        )

    async def calculate(self, data: DeliveryCalculateRequest) -> DeliveryCalculateResponse:
        if data.delivery_method not in (
            DeliveryMethod.COURIER,
            DeliveryMethod.PICKUP_POINT,
        ):
            raise ValueError("Delivery calculation is only for CDEK methods")

        _validate_address_for_delivery(data.address)

        if data.delivery_method == DeliveryMethod.COURIER:
            require_flat_for_courier(data.address.formatted_address)

        recipient_city_code = data.address.cdek_city_code
        if recipient_city_code is None:
            recipient_city_code = await cdek.resolve_city_code(
                lat=data.address.lat,
                lon=data.address.lon,
                postal_code=data.address.postal_code,
                city_name=data.address.city,
            )

        shipment_date = cdek.planned_shipment_date()
        tariff = await cdek.calculate_tariff(
            data.delivery_method,
            address=data.address.formatted_address,
            postal_code=data.address.postal_code,
            city_code=recipient_city_code,
            lat=data.address.lat,
            lon=data.address.lon,
            shipment_date=shipment_date,
        )

        pvz_code = None
        pvz_name = None
        pvz_address = None
        pvz_lat = None
        pvz_lon = None
        pvz_distance_m = None
        pvz_search_city_code = None

        if data.delivery_method == DeliveryMethod.PICKUP_POINT:
            nearest_result = await cdek.find_nearest_pvz(
                data.address.lat,
                data.address.lon,
                city_code=recipient_city_code,
                postal_code=data.address.postal_code,
                city_name=data.address.city,
            )
            if nearest_result is None:
                raise ValueError("No pickup points found near this address")
            nearest = nearest_result.point
            pvz_search_city_code = nearest_result.resolved_city_code
            pvz_code = nearest.code
            pvz_name = nearest.name
            pvz_address = nearest.address
            pvz_lat = nearest.lat
            pvz_lon = nearest.lon
            pvz_distance_m = nearest.distance_m

        return DeliveryCalculateResponse(
            delivery_cost=tariff.delivery_cost,
            tariff_code=tariff.tariff_code,
            period_min=tariff.period_min,
            period_max=tariff.period_max,
            available_dates=cdek.build_available_dates(
                tariff.period_min,
                tariff.period_max,
                delivery_date_min=tariff.delivery_date_min,
                delivery_date_max=tariff.delivery_date_max,
            ),
            delivery_date_min=(
                tariff.delivery_date_min.isoformat()
                if tariff.delivery_date_min
                else None
            ),
            delivery_date_max=(
                tariff.delivery_date_max.isoformat()
                if tariff.delivery_date_max
                else None
            ),
            shipment_date=shipment_date.isoformat(),
            pvz_code=pvz_code,
            pvz_name=pvz_name,
            pvz_address=pvz_address,
            pvz_lat=pvz_lat,
            pvz_lon=pvz_lon,
            pvz_distance_m=pvz_distance_m,
            pvz_search_city_code=pvz_search_city_code,
        )
