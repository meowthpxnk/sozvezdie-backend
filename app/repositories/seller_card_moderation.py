from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import SellerCard, SellerCardModeration, User
from app.schemas.database import ModerationStatus


class SellerCardModerationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, moderation: SellerCardModeration) -> SellerCardModeration:
        self.session.add(moderation)
        return moderation

    async def get_pending_for_seller_card(
        self, seller_card_id: int
    ) -> SellerCardModeration | None:
        stmt = (
            select(SellerCardModeration)
            .where(
                SellerCardModeration.seller_card_id == seller_card_id,
                SellerCardModeration.status == ModerationStatus.PENDING,
            )
            .order_by(SellerCardModeration.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_moderation(
        self, status: ModerationStatus | None = None
    ) -> list[SellerCardModeration]:
        stmt = select(SellerCardModeration).order_by(
            SellerCardModeration.created_at.desc()
        )
        if status is not None:
            stmt = stmt.where(SellerCardModeration.status == status)

        stmt = stmt.options(
            selectinload(SellerCardModeration.seller_card).selectinload(
                SellerCard.user
            ),
            selectinload(SellerCardModeration.moderator),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_user(self, user_id: int) -> list[SellerCardModeration]:
        stmt = (
            select(SellerCardModeration)
            .join(SellerCard)
            .where(SellerCard.user_id == user_id)
            .order_by(SellerCardModeration.created_at.desc())
            .options(
                selectinload(SellerCardModeration.seller_card),
                selectinload(SellerCardModeration.moderator),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, moderation_id: int) -> SellerCardModeration | None:
        stmt = (
            select(SellerCardModeration)
            .where(SellerCardModeration.id == moderation_id)
            .options(
                selectinload(SellerCardModeration.seller_card).selectinload(
                    SellerCard.user
                ),
                selectinload(SellerCardModeration.moderator),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
