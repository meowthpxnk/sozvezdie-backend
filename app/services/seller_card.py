from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.product import ProductRepository
from app.repositories.seller_card import SellerCardRepository
from app.repositories.seller_card_moderation import SellerCardModerationRepository
from app.repositories.specs.product import ProductSpec
from app.schemas.schemas import SellerCardCreateForm, SellerCardUpdateForm
from app.models import SellerCard, SellerCardModeration
from app.models.seller_card_moderation import SellerCardModerationAction
from app.media_client import MediaClient
from app.schemas.api.responses import (
    AuthorBrandModerationResponse,
    AuthorDashboardResponse,
    SellerCardResponse,
)
from app.schemas.database import ModerationStatus


class SellerCardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SellerCardRepository(session)
        self.product_repo = ProductRepository(session)
        self.moderation_repo = SellerCardModerationRepository(session)

    async def get_all(self) -> list[SellerCardResponse]:
        seller_cards = await self.repo.get_all()
        return [self._to_response(seller_card) for seller_card in seller_cards]

    async def get_latest_for_landing(self, *, limit: int = 10) -> list[SellerCardResponse]:
        seller_cards = await self.repo.get_latest_approved(limit=limit)
        return [self._to_response(seller_card) for seller_card in seller_cards]

    def _to_response(self, seller_card: SellerCard) -> SellerCardResponse:
        return SellerCardResponse(
            id=str(seller_card.id),
            name=seller_card.name,
            desc=seller_card.desc,
            bannerImage=seller_card.banner_image,
            avatarImage=seller_card.avatar_image,
            moderationStatus=seller_card.status,
            createdAt=seller_card.created_at,
        )

    async def get_by_id(self, author_id: str) -> SellerCardResponse:
        seller_card = await self.repo.get_by_id(int(author_id))
        if seller_card is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Author not found")
        return self._to_response(seller_card)

    async def get_by_ids(self, author_ids: list[str]) -> list[SellerCardResponse]:
        if not author_ids:
            return []

        ids = [int(author_id) for author_id in author_ids]
        seller_cards = await self.repo.get_by_ids(ids)
        cards_by_id = {seller_card.id: seller_card for seller_card in seller_cards}

        return [
            self._to_response(cards_by_id[author_id])
            for author_id in ids
            if author_id in cards_by_id
        ]

    async def get_dashboard_for_user(self, user_id: int) -> AuthorDashboardResponse:
        seller_card = await self.repo.get_by_user_id(user_id)
        if seller_card is None:
            return AuthorDashboardResponse()

        products = await self.product_repo.get_product(
            ProductSpec(
                seller_card_id=str(seller_card.id),
                all=True,
                include_inventory=True,
                include_images=False,
                include_seller_card=False,
                include_subcategory=False,
                approved_only=False,
            )
        )

        stock_total = 0
        pending_count = 0
        approved_count = 0
        rejected_count = 0

        for product in products:
            if product.inventory is not None:
                stock_total += product.inventory.quantity
            if product.status == ModerationStatus.PENDING:
                pending_count += 1
            elif product.status == ModerationStatus.APPROVED:
                approved_count += 1
            elif product.status == ModerationStatus.REJECTED:
                rejected_count += 1

        return AuthorDashboardResponse(
            seller_card=self._to_response(seller_card),
            products_count=len(products),
            stock_total=stock_total,
            pending_count=pending_count,
            approved_count=approved_count,
            rejected_count=rejected_count,
        )

    async def upload_optional_brand_image(
        self,
        file,
        media_client: MediaClient,
        current_value: str | None,
    ) -> str | None:
        return await self._upload_optional_image(file, media_client, current_value)

    async def _upload_optional_image(
        self,
        file,
        media_client: MediaClient,
        current_value: str | None,
    ) -> str | None:
        if file is None:
            return current_value

        content = await file.read()
        content_type = file.content_type or "image/jpeg"
        return await media_client.upload_image(
            image_bytes=content,
            content_type=content_type,
        )

    async def _create_moderation_record(
        self,
        seller_card: SellerCard,
        action_type: SellerCardModerationAction,
        *,
        name: str,
        desc: str,
        banner_image: str | None,
        avatar_image: str | None,
    ) -> SellerCardModeration:
        moderation = SellerCardModeration(
            seller_card_id=seller_card.id,
            action_type=action_type,
            status=ModerationStatus.PENDING,
            proposed_name=name,
            proposed_desc=desc,
            proposed_banner_image=banner_image,
            proposed_avatar_image=avatar_image,
        )
        self.moderation_repo.add(moderation)
        return moderation

    async def create_seller_card(
        self, data: SellerCardCreateForm, media_client: MediaClient
    ) -> SellerCard:
        card = SellerCard(
            user_id=data.user_id,
            name=data.name,
            desc=data.desc,
            status=ModerationStatus.PENDING,
        )
        content = await data.banner_image.read()
        content_type = data.banner_image.content_type or "image/jpeg"
        card.banner_image = await media_client.upload_image(
            image_bytes=content,
            content_type=content_type,
        )
        content = await data.avatar_image.read()
        content_type = data.avatar_image.content_type or "image/jpeg"
        card.avatar_image = await media_client.upload_image(
            image_bytes=content,
            content_type=content_type,
        )

        self.repo.add(card)
        await self.session.flush()

        await self._create_moderation_record(
            card,
            SellerCardModerationAction.CREATE_SHOP,
            name=card.name,
            desc=card.desc,
            banner_image=card.banner_image,
            avatar_image=card.avatar_image,
        )

        await self.session.commit()
        await self.session.refresh(card)
        return card

    async def update_seller_card(
        self,
        user_id: int,
        data: SellerCardUpdateForm,
        media_client: MediaClient,
    ) -> SellerCard:
        seller_card = await self.repo.get_by_user_id(user_id)
        if seller_card is None:
            raise ValueError("Seller card not found")

        proposed_name = data.name.strip()
        proposed_desc = data.desc.strip()
        if not proposed_name or not proposed_desc:
            raise ValueError("Name and description are required")

        proposed_banner = await self._upload_optional_image(
            data.banner_image,
            media_client,
            seller_card.banner_image,
        )
        proposed_avatar = await self._upload_optional_image(
            data.avatar_image,
            media_client,
            seller_card.avatar_image,
        )

        if seller_card.status == ModerationStatus.APPROVED:
            pending_moderation = await self.moderation_repo.get_pending_for_seller_card(
                seller_card.id
            )
            if pending_moderation is not None:
                raise ValueError("Brand changes are already pending moderation")

            await self._create_moderation_record(
                seller_card,
                SellerCardModerationAction.UPDATE_BRAND,
                name=proposed_name,
                desc=proposed_desc,
                banner_image=proposed_banner,
                avatar_image=proposed_avatar,
            )
            await self.session.commit()
            await self.session.refresh(seller_card)
            return seller_card

        seller_card.name = proposed_name
        seller_card.desc = proposed_desc
        seller_card.banner_image = proposed_banner
        seller_card.avatar_image = proposed_avatar
        seller_card.status = ModerationStatus.PENDING

        pending_moderation = await self.moderation_repo.get_pending_for_seller_card(
            seller_card.id
        )
        if pending_moderation is None:
            await self._create_moderation_record(
                seller_card,
                SellerCardModerationAction.CREATE_SHOP,
                name=proposed_name,
                desc=proposed_desc,
                banner_image=proposed_banner,
                avatar_image=proposed_avatar,
            )
        else:
            pending_moderation.proposed_name = proposed_name
            pending_moderation.proposed_desc = proposed_desc
            pending_moderation.proposed_banner_image = proposed_banner
            pending_moderation.proposed_avatar_image = proposed_avatar
            pending_moderation.status = ModerationStatus.PENDING
            pending_moderation.moderator_id = None
            pending_moderation.comment = None

        await self.session.commit()
        await self.session.refresh(seller_card)
        return seller_card

    async def get_seller_card_for_moderator_catalog_edit(
        self, seller_card_id: int
    ) -> SellerCard:
        seller_card = await self.repo.get_by_id(seller_card_id)
        if seller_card is None:
            raise ValueError("Seller card not found")
        if seller_card.status != ModerationStatus.APPROVED:
            raise ValueError("Only approved brands can be edited by a moderator")
        return seller_card

    async def update_seller_card_by_moderator(
        self,
        seller_card_id: int,
        data: SellerCardUpdateForm,
        media_client: MediaClient,
        moderator_id: int,
        comment: str | None,
    ) -> SellerCard:
        seller_card = await self.repo.get_by_id(seller_card_id)
        if seller_card is None:
            raise ValueError("Seller card not found")
        if seller_card.status != ModerationStatus.APPROVED:
            raise ValueError("Only approved brands can be edited by a moderator")

        proposed_name = data.name.strip()
        proposed_desc = data.desc.strip()
        if not proposed_name or not proposed_desc:
            raise ValueError("Name and description are required")

        proposed_banner = await self._upload_optional_image(
            data.banner_image,
            media_client,
            seller_card.banner_image,
        )
        proposed_avatar = await self._upload_optional_image(
            data.avatar_image,
            media_client,
            seller_card.avatar_image,
        )

        moderation_comment = (comment or "Изменение применено модератором.").strip()
        if not moderation_comment:
            raise ValueError("Comment is required")

        moderation = SellerCardModeration(
            seller_card_id=seller_card.id,
            moderator_id=moderator_id,
            action_type=SellerCardModerationAction.UPDATE_BRAND,
            status=ModerationStatus.APPROVED,
            comment=moderation_comment,
            proposed_name=proposed_name,
            proposed_desc=proposed_desc,
            proposed_banner_image=proposed_banner,
            proposed_avatar_image=proposed_avatar,
        )
        self.moderation_repo.add(moderation)

        seller_card.name = proposed_name
        seller_card.desc = proposed_desc
        seller_card.banner_image = proposed_banner
        seller_card.avatar_image = proposed_avatar

        await self.session.commit()
        await self.session.refresh(seller_card)
        return seller_card

    async def get_brand_moderations_for_user(
        self, user_id: int
    ) -> list[AuthorBrandModerationResponse]:
        moderations = await self.moderation_repo.list_for_user(user_id)
        return [self._to_brand_moderation_response(moderation) for moderation in moderations]

    def _to_brand_moderation_response(
        self, moderation: SellerCardModeration
    ) -> AuthorBrandModerationResponse:
        action_label = (
            "Создание магазина"
            if moderation.action_type == SellerCardModerationAction.CREATE_SHOP
            else "Изменение бренда"
        )
        details = [
            f"Тип: {action_label}",
            f"Название: {moderation.proposed_name}",
        ]
        comment = moderation.comment.strip() if moderation.comment else None

        return AuthorBrandModerationResponse(
            id=str(moderation.id),
            createdAt=moderation.created_at,
            actionType=moderation.action_type.value,
            status=moderation.status,
            title=(
                f"Магазин «{moderation.proposed_name}»"
                if moderation.action_type == SellerCardModerationAction.CREATE_SHOP
                else f"Бренд «{moderation.proposed_name}»"
            ),
            details=details,
            moderatorComment=comment,
        )
