from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserAddress
from app.utils.address_flat import extract_flat_from_text
from app.repositories.user_address import UserAddressRepository
from app.schemas.api.delivery import (
    OrderDeliveryAddressPayload,
    UserAddressCreateRequest,
    UserAddressListResponse,
    UserAddressResponse,
    UserAddressUpdateRequest,
)


class UserAddressService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserAddressRepository(session)

    def _to_response(self, address: UserAddress) -> UserAddressResponse:
        return UserAddressResponse(
            id=address.id,
            label=address.label,
            formatted_address=address.formatted_address,
            city=address.city,
            street=address.street,
            house=address.house,
            flat=address.flat,
            lat=address.lat,
            lon=address.lon,
            postal_code=address.postal_code,
            is_default=address.is_default,
        )

    async def list_addresses(self, user_id: int) -> UserAddressListResponse:
        addresses = await self.repo.list_for_user(user_id)
        return UserAddressListResponse(
            items=[self._to_response(a) for a in addresses]
        )

    async def create_address(
        self,
        user_id: int,
        data: UserAddressCreateRequest,
    ) -> UserAddressResponse:
        if data.is_default:
            await self.repo.clear_default(user_id)

        address = UserAddress(
            user_id=user_id,
            label=data.label,
            formatted_address=data.formatted_address,
            city=data.city,
            street=data.street,
            house=data.house,
            flat=data.flat,
            lat=data.lat,
            lon=data.lon,
            postal_code=data.postal_code,
            cdek_city_code=data.cdek_city_code,
            dadata_raw=data.dadata_raw,
            is_default=data.is_default,
            last_used_at=datetime.now(),
        )
        self.repo.add(address)
        await self.session.commit()
        await self.session.refresh(address)
        return self._to_response(address)

    async def update_address(
        self,
        user_id: int,
        address_id: int,
        data: UserAddressUpdateRequest,
    ) -> UserAddressResponse:
        address = await self.repo.get_by_id(address_id, user_id)
        if address is None:
            raise ValueError("Address not found")

        if data.label is not None:
            address.label = data.label
        if data.is_default is not None:
            if data.is_default:
                await self.repo.clear_default(user_id)
            address.is_default = data.is_default

        await self.session.commit()
        await self.session.refresh(address)
        return self._to_response(address)

    async def delete_address(self, user_id: int, address_id: int) -> None:
        address = await self.repo.get_by_id(address_id, user_id)
        if address is None:
            raise ValueError("Address not found")
        await self.repo.delete(address)
        await self.session.commit()

    async def save_from_order(
        self,
        user_id: int,
        payload: OrderDeliveryAddressPayload,
    ) -> UserAddress:
        if payload.user_address_id:
            existing = await self.repo.get_by_id(payload.user_address_id, user_id)
            if existing:
                existing.last_used_at = datetime.now()
                parsed_flat = extract_flat_from_text(payload.formatted_address)
                if parsed_flat:
                    existing.flat = parsed_flat
                return existing

        address = UserAddress(
            user_id=user_id,
            formatted_address=payload.formatted_address,
            city=payload.city,
            street=payload.street,
            house=payload.house,
            flat=extract_flat_from_text(payload.formatted_address),
            lat=payload.lat,
            lon=payload.lon,
            postal_code=payload.postal_code,
            cdek_city_code=payload.cdek_city_code,
            dadata_raw=payload.dadata_raw,
            is_default=False,
            last_used_at=datetime.now(),
        )
        self.repo.add(address)
        await self.session.flush()
        return address
