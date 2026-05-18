from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavouriteAuthor, FavouriteProduct

from .specs.favourite import FavouriteSpec


class FavouriteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_favourite_products(
        self, spec: FavouriteSpec
    ) -> list[FavouriteProduct]:
        stmt = (
            select(FavouriteProduct)
            .where(FavouriteProduct.user_id == spec.user_id)
            .order_by(FavouriteProduct.created_at.desc())
        )
        if spec.product_id is not None:
            stmt = stmt.where(FavouriteProduct.product_id == spec.product_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_favourite_authors(
        self, spec: FavouriteSpec
    ) -> list[FavouriteAuthor]:
        stmt = (
            select(FavouriteAuthor)
            .where(FavouriteAuthor.user_id == spec.user_id)
            .order_by(FavouriteAuthor.created_at.desc())
        )
        if spec.seller_card_id is not None:
            stmt = stmt.where(
                FavouriteAuthor.seller_card_id == spec.seller_card_id
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_favourite_product(self, user_id: int, product_id: int):
        stmt = insert(FavouriteProduct).values(
            user_id=user_id,
            product_id=product_id,
        )
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_favourite_product_user_product"
        )
        await self.session.execute(stmt)

    async def add_favourite_author(self, user_id: int, seller_card_id: int):
        stmt = insert(FavouriteAuthor).values(
            user_id=user_id,
            seller_card_id=seller_card_id,
        )
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_favourite_author_user_seller_card"
        )
        await self.session.execute(stmt)

    async def delete_favourite_product(self, user_id: int, product_id: int):
        stmt = delete(FavouriteProduct).where(
            FavouriteProduct.user_id == user_id,
            FavouriteProduct.product_id == product_id,
        )
        await self.session.execute(stmt)

    async def delete_favourite_author(self, user_id: int, seller_card_id: int):
        stmt = delete(FavouriteAuthor).where(
            FavouriteAuthor.user_id == user_id,
            FavouriteAuthor.seller_card_id == seller_card_id,
        )
        await self.session.execute(stmt)
