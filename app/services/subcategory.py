from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subcategory
from app.repositories.category import CategoryRepository
from app.repositories.subcategory import SubcategoryRepository
from app.schemas.api.responses import SubcategoryCreateRequest, SubcategoryResponse
from app.utils.slug import translit_to_slug, validate_slug


class SubcategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SubcategoryRepository(session)
        self.category_repo = CategoryRepository(session)

    @staticmethod
    def _to_response(subcategory: Subcategory) -> SubcategoryResponse:
        return SubcategoryResponse(
            slug=subcategory.slug,
            title=subcategory.title,
            categorySlug=subcategory.category_slug,
            authorId=str(subcategory.seller_card_id),
        )

    async def get_by_category_slug(
        self, category_slug: str
    ) -> list[SubcategoryResponse]:
        category = await self.category_repo.get_by_slug(category_slug)
        if category is None:
            return []

        subcategories = await self.repo.get_by_category_slug(category_slug)
        return [self._to_response(item) for item in subcategories]

    async def create_subcategory(
        self,
        category_slug: str,
        seller_card_id: int,
        data: SubcategoryCreateRequest,
    ) -> SubcategoryResponse:
        category = await self.category_repo.get_by_slug(category_slug)
        if category is None:
            raise ValueError("Category not found")

        slug = validate_slug(data.slug)
        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        auto_slug = translit_to_slug(title)
        if auto_slug and auto_slug != slug:
            pass

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
