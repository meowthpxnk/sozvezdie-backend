from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.favourite import FavouriteRepository
from app.repositories.specs.favourite import FavouriteSpec
from app.schemas.api.responses import (
    FavouriteAuthorItemResponse,
    FavouriteAuthorsResponse,
    FavouriteProductItemResponse,
    FavouriteProductsResponse,
)


class FavouriteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FavouriteRepository(session)

    async def toggle_favourite_product(
        self,
        user_id: int,
        product_id: int,
        liked: bool,
    ):
        if not liked:
            await self.repo.delete_favourite_product(user_id, product_id)
        else:
            await self.repo.add_favourite_product(user_id, product_id)

        await self.session.commit()

    async def toggle_favourite_author(
        self,
        user_id: int,
        author_id: int,
        liked: bool,
    ):
        if not liked:
            await self.repo.delete_favourite_author(user_id, author_id)
        else:
            await self.repo.add_favourite_author(user_id, author_id)

        await self.session.commit()

    async def get_favourite_products(
        self, user_id: int
    ) -> FavouriteProductsResponse:
        favourites = await self.repo.get_favourite_products(
            FavouriteSpec(user_id=user_id)
        )
        return FavouriteProductsResponse(
            items=[
                FavouriteProductItemResponse(
                    product_id=str(item.product_id),
                    created_at=item.created_at,
                )
                for item in favourites
            ]
        )

    async def get_favourite_authors(
        self, user_id: int
    ) -> FavouriteAuthorsResponse:
        favourites = await self.repo.get_favourite_authors(
            FavouriteSpec(user_id=user_id)
        )
        return FavouriteAuthorsResponse(
            items=[
                FavouriteAuthorItemResponse(
                    author_id=str(item.seller_card_id),
                    created_at=item.created_at,
                )
                for item in favourites
            ]
        )
