from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subcategory


class SubcategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        *,
        category_slug: str | None = None,
        search: str | None = None,
    ) -> list[Subcategory]:
        stmt = select(Subcategory)
        if category_slug:
            stmt = stmt.where(Subcategory.category_slug == category_slug)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Subcategory.title.ilike(pattern),
                    Subcategory.slug.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Subcategory.category_slug.asc(), Subcategory.title.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category_slug(self, category_slug: str) -> list[Subcategory]:
        return await self.get_all(category_slug=category_slug)

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

    async def mark_approved(self, subcategory_id: int | None) -> None:
        if subcategory_id is None:
            return

        subcategory = await self.get_by_id(subcategory_id)
        if subcategory is None or subcategory.is_approved:
            return

        subcategory.is_approved = True

    def add(self, subcategory: Subcategory) -> Subcategory:
        self.session.add(subcategory)
        return subcategory

    async def delete(self, subcategory: Subcategory) -> None:
        await self.session.delete(subcategory)
