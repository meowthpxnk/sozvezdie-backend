from fastapi import APIRouter

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.schemas.api.responses import (
    FavouriteAuthorRequest,
    FavouriteAuthorsResponse,
    FavouriteProductRequest,
    FavouriteProductsResponse,
)
from app.services.favourite import FavouriteService
from app.services.user import UserService

router = APIRouter(prefix="/favourite", tags=["Favourite"])


@router.put("/product")
async def toggle_favourite_product(
    session: DatabaseDepends,
    token: BearerAuthDepends,
    request: FavouriteProductRequest,
):
    user = await UserService(session).get_user(username=token.username)

    await FavouriteService(session).toggle_favourite_product(
        user.id, int(request.product_id), request.liked
    )


@router.get("/product")
async def get_favourite_products(
    session: DatabaseDepends,
    token: BearerAuthDepends,
) -> FavouriteProductsResponse:
    user = await UserService(session).get_user(username=token.username)

    return await FavouriteService(session).get_favourite_products(user.id)


@router.put("/author")
async def toggle_favourite_author(
    session: DatabaseDepends,
    token: BearerAuthDepends,
    request: FavouriteAuthorRequest,
):
    user = await UserService(session).get_user(username=token.username)

    await FavouriteService(session).toggle_favourite_author(
        user.id, int(request.author_id), request.liked
    )


@router.get("/author")
async def get_favourite_authors(
    session: DatabaseDepends,
    token: BearerAuthDepends,
) -> FavouriteAuthorsResponse:
    user = await UserService(session).get_user(username=token.username)

    return await FavouriteService(session).get_favourite_authors(user.id)
