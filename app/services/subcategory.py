from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subcategory
from app.repositories.category import CategoryRepository
from app.repositories.subcategory import SubcategoryRepository
from app.schemas.api.responses import (
    SubcategoryAdminCreateRequest,
    SubcategoryCreateRequest,
    SubcategoryResponse,
    SubcategoryUpdateRequest,
)
from app.utils.slug import validate_slug


class SubcategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SubcategoryRepository(session)
        self.category_repo = CategoryRepository(session)

    @staticmethod
    def _to_response(subcategory: Subcategory) -> SubcategoryResponse:
        return SubcategoryResponse(
            id=subcategory.id,
            slug=subcategory.slug,
            title=subcategory.title,
            categorySlug=subcategory.category_slug,
            authorId=(
                str(subcategory.seller_card_id)
                if subcategory.seller_card_id is not None
                else None
            ),
        )

    async def list_subcategories(
        self,
        *,
        category_slug: str | None = None,
        search: str | None = None,
    ) -> list[SubcategoryResponse]:
        subcategories = await self.repo.get_all(
            category_slug=category_slug,
            search=search,
        )
        return [self._to_response(item) for item in subcategories]

    async def get_by_category_slug(
        self, category_slug: str
    ) -> list[SubcategoryResponse]:
        category = await self.category_repo.get_by_slug(category_slug)
        if category is None:
            return []

        return await self.list_subcategories(category_slug=category_slug)

    async def create_subcategory(
        self,
        category_slug: str,
        data: SubcategoryCreateRequest,
        *,
        seller_card_id: int | None = None,
    ) -> SubcategoryResponse:
        category = await self.category_repo.get_by_slug(category_slug)
        if category is None:
            raise ValueError("Category not found")

        slug = validate_slug(data.slug)
        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        existing = await self.repo.get_by_slugs(category_slug, slug)
        if existing is not None:
            raise ValueError("Subcategory slug already exists in this category")

        subcategory = Subcategory(
            slug=slug,
            title=title,
            category_slug=category_slug,
            seller_card_id=seller_card_id,
        )
        self.repo.add(subcategory)
        await self.session.commit()
        await self.session.refresh(subcategory)
        return self._to_response(subcategory)

    async def create_admin_subcategory(
        self, data: SubcategoryAdminCreateRequest
    ) -> SubcategoryResponse:
        return await self.create_subcategory(
            category_slug=data.category_slug,
            data=SubcategoryCreateRequest(title=data.title, slug=data.slug),
            seller_card_id=None,
        )

    async def update_subcategory(
        self, subcategory_id: int, data: SubcategoryUpdateRequest
    ) -> SubcategoryResponse:
        subcategory = await self.repo.get_by_id(subcategory_id)
        if subcategory is None:
            raise ValueError("Subcategory not found")

        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        subcategory.title = title
        await self.session.commit()
        await self.session.refresh(subcategory)
        return self._to_response(subcategory)

    async def delete_subcategory(self, subcategory_id: int) -> None:
        subcategory = await self.repo.get_by_id(subcategory_id)
        if subcategory is None:
            raise ValueError("Subcategory not found")
        await self.repo.delete(subcategory)
        await self.session.commit()
