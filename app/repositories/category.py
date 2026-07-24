from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category


class CategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, search: str | None = None) -> list[Category]:
        stmt = select(Category)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(Category.title.ilike(pattern), Category.slug.ilike(pattern))
            )
        stmt = stmt.order_by(Category.title.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, category: Category) -> Category:
        self.session.add(category)
        return category

    async def delete(self, category: Category) -> None:
        await self.session.delete(category)
