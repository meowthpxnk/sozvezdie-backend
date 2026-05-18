from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fandom


class FandomRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[Fandom]:
        stmt = select(Fandom).order_by(Fandom.title.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Fandom | None:
        stmt = select(Fandom).where(Fandom.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
