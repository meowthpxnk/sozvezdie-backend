from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.category import CategoryRepository
from app.schemas.api.responses import CategoryResponse


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CategoryRepository(session)

    async def get_categories(self) -> list[CategoryResponse]:
        categories = await self.repo.get_all()
        return [
            CategoryResponse(slug=category.slug, title=category.title)
            for category in categories
        ]

    async def get_category(self, slug: str) -> CategoryResponse | None:
        category = await self.repo.get_by_slug(slug)
        if category is None:
            return None
        return CategoryResponse(slug=category.slug, title=category.title)
