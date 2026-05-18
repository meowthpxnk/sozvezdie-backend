from fastapi import APIRouter, HTTPException

from app.api.dependencies import BearerAuthDepends, DatabaseDepends
from app.repositories.specs.user import UserSpec
from app.schemas.api.responses import (
    CategoryResponse,
    SubcategoryCreateRequest,
    SubcategoryResponse,
)
from app.services.category import CategoryService
from app.services.subcategory import SubcategoryService
from app.services.user import UserService

router = APIRouter()


@router.get("/category")
async def get_categories(session: DatabaseDepends) -> list[CategoryResponse]:
    return await CategoryService(session).get_categories()


@router.get("/category/{category_slug}")
async def get_category(
    category_slug: str, session: DatabaseDepends
) -> CategoryResponse:
    category = await CategoryService(session).get_category(category_slug)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("/category/{category_slug}/subcategory")
async def get_subcategories(
    category_slug: str, session: DatabaseDepends
) -> list[SubcategoryResponse]:
    return await SubcategoryService(session).get_by_category_slug(category_slug)


@router.post("/category/{category_slug}/subcategory")
async def create_subcategory(
    category_slug: str,
    request: SubcategoryCreateRequest,
    session: DatabaseDepends,
    bearer_token: BearerAuthDepends,
) -> SubcategoryResponse:
    user = await UserService(session).get_user(
        bearer_token.username,
        UserSpec(username=bearer_token.username, include_seller_card=True),
    )
    if user.seller_card is None:
        raise HTTPException(status_code=403, detail="Seller card required")

    try:
        return await SubcategoryService(session).create_subcategory(
            category_slug=category_slug,
            seller_card_id=user.seller_card.id,
            data=request,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
