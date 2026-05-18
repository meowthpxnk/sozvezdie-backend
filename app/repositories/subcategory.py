from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Subcategory


class SubcategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_category_slug(self, category_slug: str) -> list[Subcategory]:
        stmt = (
            select(Subcategory)
            .where(Subcategory.category_slug == category_slug)
            .order_by(Subcategory.title)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slugs(
        self, category_slug: str, subcategory_slug: str
    ) -> Subcategory | None:
        stmt = select(Subcategory).where(
            Subcategory.category_slug == category_slug,
            Subcategory.slug == subcategory_slug,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, subcategory_id: int) -> Subcategory | None:
        stmt = select(Subcategory).where(Subcategory.id == subcategory_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, subcategory: Subcategory) -> Subcategory:
        self.session.add(subcategory)
        return subcategory
