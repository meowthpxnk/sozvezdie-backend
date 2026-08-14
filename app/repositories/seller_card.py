from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, SellerCard, User
from app.schemas.database import ModerationStatus
from app.core.blocked_1c import is_blocked_1c_users_enabled


class SellerCardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, seller_card: SellerCard) -> SellerCard:
        self.session.add(seller_card)
        return seller_card

    @staticmethod
    def _has_approved_product_clause():
        return exists(
            select(Product.id).where(
                Product.seller_card_id == SellerCard.id,
                Product.status == ModerationStatus.APPROVED,
            )
        )

    @staticmethod
    def _has_one_c_author_clause():
        if not is_blocked_1c_users_enabled():
            return True
        return exists(
            select(User.id).where(
                User.id == SellerCard.user_id,
                User.one_c_author_id.is_not(None),
                User.one_c_author_id != "",
            )
        )

    def _public_author_filters(self):
        filters = [
            SellerCard.status == ModerationStatus.APPROVED,
            SellerCard.is_disabled.is_(False),
            self._has_approved_product_clause(),
        ]
        if is_blocked_1c_users_enabled():
            filters.append(self._has_one_c_author_clause())
        return filters

    async def get_all(self) -> list[SellerCard]:
        stmt = (
            select(SellerCard)
            .where(*self._public_author_filters())
            .order_by(SellerCard.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_approved(self, *, limit: int = 10) -> list[SellerCard]:
        stmt = (
            select(SellerCard)
            .where(*self._public_author_filters())
            .order_by(SellerCard.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_id(self, user_id: int) -> SellerCard | None:
        stmt = select(SellerCard).where(SellerCard.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, author_id: int) -> SellerCard | None:
        stmt = select(SellerCard).where(
            SellerCard.id == author_id,
            *self._public_author_filters(),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_moderator(self, author_id: int) -> SellerCard | None:
        stmt = select(SellerCard).where(
            SellerCard.id == author_id,
            SellerCard.status == ModerationStatus.APPROVED,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(
        self, author_ids: list[int], *, catalog_visible_only: bool = False
    ) -> list[SellerCard]:
        if not author_ids:
            return []
        stmt = select(SellerCard).where(SellerCard.id.in_(author_ids))
        if catalog_visible_only:
            stmt = stmt.where(*self._public_author_filters())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
