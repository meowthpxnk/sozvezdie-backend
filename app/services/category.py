from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category
from app.repositories.category import CategoryRepository
from app.schemas.api.responses import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.utils.slug import validate_slug


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CategoryRepository(session)

    def _to_response(self, category: Category) -> CategoryResponse:
        return CategoryResponse(slug=category.slug, title=category.title)

    async def get_categories(self, search: str | None = None) -> list[CategoryResponse]:
        categories = await self.repo.get_all(search=search)
        return [self._to_response(category) for category in categories]

    async def get_category(self, slug: str) -> CategoryResponse | None:
        category = await self.repo.get_by_slug(slug)
        if category is None:
            return None
        return self._to_response(category)

    async def create_category(self, data: CategoryCreateRequest) -> CategoryResponse:
        slug = validate_slug(data.slug)
        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        existing = await self.repo.get_by_slug(slug)
        if existing is not None:
            raise ValueError("Category slug already exists")

        category = Category(slug=slug, title=title)
        self.repo.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return self._to_response(category)

    async def update_category(
        self, slug: str, data: CategoryUpdateRequest
    ) -> CategoryResponse:
        category = await self.repo.get_by_slug(slug)
        if category is None:
            raise ValueError("Category not found")

        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        category.title = title
        await self.session.commit()
        await self.session.refresh(category)
        return self._to_response(category)

    async def delete_category(self, slug: str) -> None:
        category = await self.repo.get_by_slug(slug)
        if category is None:
            raise ValueError("Category not found")
        await self.repo.delete(category)
        await self.session.commit()
