from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserAddress


class UserAddressRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: int) -> list[UserAddress]:
        stmt = (
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(
                UserAddress.is_default.desc(),
                UserAddress.last_used_at.desc().nullslast(),
                UserAddress.id.desc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, address_id: int, user_id: int) -> UserAddress | None:
        stmt = select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, address: UserAddress) -> UserAddress:
        self.session.add(address)
        return address

    async def clear_default(self, user_id: int) -> None:
        await self.session.execute(
            update(UserAddress)
            .where(UserAddress.user_id == user_id)
            .values(is_default=False)
        )

    async def delete(self, address: UserAddress) -> None:
        await self.session.delete(address)
