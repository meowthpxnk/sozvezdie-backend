from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models import AdvertBanner


class AdvertBannerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, advert_banner: AdvertBanner) -> AdvertBanner:
        self.session.add(advert_banner)
        return advert_banner

    async def delete(self, advert_banner: AdvertBanner) -> None:
        await self.session.delete(advert_banner)

    async def get_all(self) -> list[AdvertBanner]:
        stmt = select(AdvertBanner).order_by(AdvertBanner.id.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, banner_id: int) -> AdvertBanner | None:
        stmt = select(AdvertBanner).where(AdvertBanner.id == banner_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
