from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Product,
    ProductModeration,
    SellerCard,
    SellerCardModeration,
)
from app.models.seller_card_moderation import SellerCardModerationAction
from app.repositories.product import ProductRepository
from app.repositories.seller_card_moderation import (
    SellerCardModerationRepository,
)
from app.repositories.specs.product import ProductSpec
from app.schemas.api.responses import (
    ModerationEditResponse,
    ModerationFieldDiffResponse,
    ModerationProposalResponse,
)
from app.schemas.database import ModerationStatus
from app.schemas.schemas import SellerCardUpdateForm

if TYPE_CHECKING:
    from app.media_client import MediaClient


def _format_rubles(price_kopecks: int) -> str:
    rubles = price_kopecks / 100
    if rubles.is_integer():
        formatted = f"{int(rubles):,}".replace(",", " ")
    else:
        formatted = f"{rubles:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} ₽"


class ModerationService:
    PRODUCT_PREFIX = "product"
    BRAND_PREFIX = "brand"
    PRODUCT_EDIT_PREFIX = "product-edit"
    _DECISION_COMMENTS = {
        "Заявка принята модератором.",
        "Заявка отклонена модератором.",
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.product_repo = ProductRepository(session)
        self.brand_moderation_repo = SellerCardModerationRepository(session)

    @staticmethod
    def parse_proposal_id(proposal_id: str) -> tuple[str, int]:
        if proposal_id.startswith(f"{ModerationService.PRODUCT_PREFIX}-"):
            return (
                ModerationService.PRODUCT_PREFIX,
                int(
                    proposal_id.removeprefix(
                        f"{ModerationService.PRODUCT_PREFIX}-"
                    )
                ),
            )
        if proposal_id.startswith(f"{ModerationService.BRAND_PREFIX}-"):
            return (
                ModerationService.BRAND_PREFIX,
                int(
                    proposal_id.removeprefix(
                        f"{ModerationService.BRAND_PREFIX}-"
                    )
                ),
            )
        raise ValueError("Invalid proposal id")

    @staticmethod
    def _latest_product_moderation(
        product: Product,
    ) -> ProductModeration | None:
        if not product.moderations:
            return None
        return max(
            product.moderations, key=lambda moderation: moderation.created_at
        )

    def _build_product_changes(
        self, product: Product
    ) -> list[ModerationFieldDiffResponse]:
        stock_count = product.inventory.quantity if product.inventory else 0
        cover_uuid = product.images[0].image_uuid if product.images else None
        changes = [
            ModerationFieldDiffResponse(
                label="Название", before="—", after=product.name
            ),
            ModerationFieldDiffResponse(
                label="Цена", before="—", after=_format_rubles(product.price)
            ),
            ModerationFieldDiffResponse(
                label="Описание", before="—", after=product.desc
            ),
            ModerationFieldDiffResponse(
                label="Количество", before="—", after=f"{stock_count} шт."
            ),
        ]

        if product.category_slug:
            changes.append(
                ModerationFieldDiffResponse(
                    label="Категория",
                    before="—",
                    after=product.category_slug,
                )
            )

        if product.fandom_slug:
            changes.append(
                ModerationFieldDiffResponse(
                    label="Фандом",
                    before="—",
                    after=product.fandom_slug,
                )
            )

        if cover_uuid:
            changes.append(
                ModerationFieldDiffResponse(
                    label="Обложка",
                    before="—",
                    after=str(cover_uuid),
                    afterImageUrl=str(cover_uuid),
                )
            )

        return changes

    def _build_brand_changes(
        self,
        moderation: SellerCardModeration,
        seller_card: SellerCard,
    ) -> list[ModerationFieldDiffResponse]:
        if moderation.action_type == SellerCardModerationAction.CREATE_SHOP:
            changes = [
                ModerationFieldDiffResponse(
                    label="Название магазина",
                    before="—",
                    after=moderation.proposed_name,
                ),
                ModerationFieldDiffResponse(
                    label="Описание",
                    before="—",
                    after=moderation.proposed_desc,
                ),
            ]
        else:
            changes = [
                ModerationFieldDiffResponse(
                    label="Название бренда",
                    before=seller_card.name,
                    after=moderation.proposed_name,
                ),
                ModerationFieldDiffResponse(
                    label="Описание бренда",
                    before=seller_card.desc,
                    after=moderation.proposed_desc,
                ),
            ]

        if moderation.action_type == SellerCardModerationAction.UPDATE_BRAND:
            if seller_card.banner_image != moderation.proposed_banner_image:
                changes.append(
                    ModerationFieldDiffResponse(
                        label="Баннер",
                        before=seller_card.banner_image or "—",
                        after=moderation.proposed_banner_image or "—",
                        beforeImageUrl=seller_card.banner_image,
                        afterImageUrl=moderation.proposed_banner_image,
                    )
                )
            if seller_card.avatar_image != moderation.proposed_avatar_image:
                changes.append(
                    ModerationFieldDiffResponse(
                        label="Аватар",
                        before=seller_card.avatar_image or "—",
                        after=moderation.proposed_avatar_image or "—",
                        beforeImageUrl=seller_card.avatar_image,
                        afterImageUrl=moderation.proposed_avatar_image,
                    )
                )
        else:
            if moderation.proposed_banner_image:
                changes.append(
                    ModerationFieldDiffResponse(
                        label="Баннер",
                        before="—",
                        after=moderation.proposed_banner_image,
                        afterImageUrl=moderation.proposed_banner_image,
                    )
                )
            if moderation.proposed_avatar_image:
                changes.append(
                    ModerationFieldDiffResponse(
                        label="Аватар",
                        before="—",
                        after=moderation.proposed_avatar_image,
                        afterImageUrl=moderation.proposed_avatar_image,
                    )
                )

        return changes

    def _product_to_proposal(
        self, product: Product
    ) -> ModerationProposalResponse:
        seller_card = product.seller_card
        seller_user = seller_card.user if seller_card else None
        submitted_by = seller_card.name if seller_card else "Неизвестный автор"
        if seller_user:
            submitted_by = f"{submitted_by} (@{seller_user.username})"

        latest_moderation = self._latest_product_moderation(product)
        moderated_by = None
        moderation_comment = None
        if latest_moderation and product.status != ModerationStatus.PENDING:
            moderated_by = f"@{latest_moderation.moderator.username}"
            moderation_comment = latest_moderation.comment

        cover_uuid = product.images[0].image_uuid if product.images else None

        return ModerationProposalResponse(
            id=f"{self.PRODUCT_PREFIX}-{product.id}",
            createdAt=product.created_at,
            title=f"Товар «{product.name}»",
            type="CREATE_PRODUCT",
            status=product.status,
            submittedBy=submitted_by,
            moderatedBy=moderated_by,
            moderationComment=moderation_comment,
            previewImageUrl=str(cover_uuid) if cover_uuid else None,
            changes=self._build_product_changes(product),
        )

    def _brand_to_proposal(
        self, moderation: SellerCardModeration
    ) -> ModerationProposalResponse:
        seller_card = moderation.seller_card
        seller_user = seller_card.user if seller_card else None
        submitted_by = seller_card.name if seller_card else "Неизвестный автор"
        if seller_user:
            submitted_by = f"{seller_user.username}"

        moderated_by = None
        moderation_comment = None
        if (
            moderation.moderator
            and moderation.status != ModerationStatus.PENDING
        ):
            moderated_by = f"@{moderation.moderator.username}"
            moderation_comment = moderation.comment

        action_type = moderation.action_type.value
        title = (
            f"Магазин «{moderation.proposed_name}»"
            if moderation.action_type == SellerCardModerationAction.CREATE_SHOP
            else f"Бренд «{moderation.proposed_name}»"
        )

        return ModerationProposalResponse(
            id=f"{self.BRAND_PREFIX}-{moderation.id}",
            createdAt=moderation.created_at,
            title=title,
            type=action_type,
            status=moderation.status,
            submittedBy=submitted_by,
            moderatedBy=moderated_by,
            moderationComment=moderation_comment,
            previewBannerUrl=moderation.proposed_banner_image,
            previewAvatarUrl=moderation.proposed_avatar_image,
            changes=self._build_brand_changes(moderation, seller_card),
        )

    def _product_moderation_to_proposal(
        self, moderation: ProductModeration
    ) -> ModerationProposalResponse:
        product = moderation.product
        seller_card = product.seller_card
        seller_user = seller_card.user if seller_card else None
        submitted_by = seller_card.name if seller_card else "Неизвестный автор"
        if seller_user:
            submitted_by = f"{submitted_by} (@{seller_user.username})"

        moderated_by = (
            f"@{moderation.moderator.username}" if moderation.moderator else None
        )
        cover_uuid = product.images[0].image_uuid if product.images else None

        return ModerationProposalResponse(
            id=f"{self.PRODUCT_EDIT_PREFIX}-{moderation.id}",
            createdAt=moderation.created_at,
            title=f"Изменение товара «{product.name}»",
            type="MODERATOR_PRODUCT_EDIT",
            status=moderation.status,
            submittedBy=submitted_by,
            moderatedBy=moderated_by,
            moderationComment=moderation.comment,
            previewImageUrl=str(cover_uuid) if cover_uuid else None,
            changes=self._build_product_changes(product),
        )

    async def list_proposals(
        self, status: ModerationStatus | None = None
    ) -> list[ModerationProposalResponse]:
        products = await self.product_repo.list_for_moderation(status)
        brand_moderations = (
            await self.brand_moderation_repo.list_for_moderation(status)
        )

        proposals = [
            self._product_to_proposal(product) for product in products
        ]
        proposals.extend(
            self._brand_to_proposal(moderation)
            for moderation in brand_moderations
        )

        if status in {None, ModerationStatus.APPROVED}:
            product_moderations = (
                await self.product_repo.list_product_moderations_for_feed(status)
            )
            proposals.extend(
                self._product_moderation_to_proposal(moderation)
                for moderation in product_moderations
                if moderation.comment not in self._DECISION_COMMENTS
            )

        proposals.sort(key=lambda proposal: proposal.createdAt, reverse=True)
        return proposals

    async def get_catalog_product_edit(self, product_id: int) -> ModerationEditResponse:
        from app.services.product import ProductService

        product_response = await ProductService(
            self.session
        ).get_product_for_moderator_catalog_edit(product_id)

        product = await self.product_repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_seller_card=True,
                include_subcategory=True,
                include_moderations=True,
                approved_only=False,
            )
        )
        if product is None:
            raise ValueError("Product not found")

        return ModerationEditResponse(
            kind="product",
            proposal=ModerationProposalResponse(
                id=f"{self.PRODUCT_PREFIX}-{product.id}",
                createdAt=product.created_at,
                title=f"Товар «{product.name}»",
                type="MODERATOR_PRODUCT_EDIT",
                status=product.status,
                submittedBy=product.seller_card.name if product.seller_card else "",
                changes=self._build_product_changes(product),
            ),
            product=product_response,
        )

    async def get_catalog_brand_edit(self, seller_card_id: int) -> ModerationEditResponse:
        from app.services.seller_card import SellerCardService

        seller_card = await SellerCardService(
            self.session
        ).get_seller_card_for_moderator_catalog_edit(seller_card_id)

        return ModerationEditResponse(
            kind="brand",
            proposal=ModerationProposalResponse(
                id=f"{self.BRAND_PREFIX}-seller-{seller_card.id}",
                createdAt=seller_card.created_at,
                title=f"Бренд «{seller_card.name}»",
                type="UPDATE_BRAND",
                status=seller_card.status,
                submittedBy=seller_card.name,
                changes=[],
            ),
            brandName=seller_card.name,
            brandDescription=seller_card.desc,
            avatarImage=seller_card.avatar_image,
            bannerImage=seller_card.banner_image,
            actionType=SellerCardModerationAction.UPDATE_BRAND.value,
        )

    async def get_proposal_edit(
        self, proposal_id: str
    ) -> ModerationEditResponse:
        entity_type, entity_id = self.parse_proposal_id(proposal_id)

        if entity_type == self.PRODUCT_PREFIX:
            product = await self.product_repo.get_product(
                ProductSpec(
                    id=entity_id,
                    include_images=True,
                    include_inventory=True,
                    include_seller_card=True,
                    include_subcategory=True,
                    include_moderations=True,
                    approved_only=False,
                )
            )
            if product is None:
                raise ValueError("Product not found")
            if product.status != ModerationStatus.PENDING:
                raise ValueError("Product is not pending moderation")

            from app.services.product import ProductService

            product_response = await ProductService(
                self.session
            ).get_product_for_moderation(entity_id)
            return ModerationEditResponse(
                kind="product",
                proposal=self._product_to_proposal(product),
                product=product_response,
            )

        moderation = await self.brand_moderation_repo.get_by_id(entity_id)
        if moderation is None:
            raise ValueError("Brand moderation not found")
        if moderation.status != ModerationStatus.PENDING:
            raise ValueError("Brand moderation is not pending")

        return ModerationEditResponse(
            kind="brand",
            proposal=self._brand_to_proposal(moderation),
            brandName=moderation.proposed_name,
            brandDescription=moderation.proposed_desc,
            avatarImage=moderation.proposed_avatar_image,
            bannerImage=moderation.proposed_banner_image,
            actionType=moderation.action_type.value,
        )

    async def update_brand_proposal(
        self,
        proposal_id: str,
        data: SellerCardUpdateForm,
        media_client: "MediaClient",
    ) -> ModerationEditResponse:
        from app.services.seller_card import SellerCardService

        entity_type, entity_id = self.parse_proposal_id(proposal_id)
        if entity_type != self.BRAND_PREFIX:
            raise ValueError("Not a brand proposal")

        moderation = await self.brand_moderation_repo.get_by_id(entity_id)
        if moderation is None:
            raise ValueError("Brand moderation not found")
        if moderation.status != ModerationStatus.PENDING:
            raise ValueError("Brand moderation is not pending")

        seller_card = moderation.seller_card
        seller_card_service = SellerCardService(self.session)
        fallback_banner = moderation.proposed_banner_image or (
            seller_card.banner_image if seller_card else None
        )
        fallback_avatar = moderation.proposed_avatar_image or (
            seller_card.avatar_image if seller_card else None
        )

        moderation.proposed_name = data.name.strip()
        moderation.proposed_desc = data.desc.strip()
        moderation.proposed_banner_image = (
            await seller_card_service.upload_optional_brand_image(
                data.banner_image,
                media_client,
                fallback_banner,
            )
        )
        moderation.proposed_avatar_image = (
            await seller_card_service.upload_optional_brand_image(
                data.avatar_image,
                media_client,
                fallback_avatar,
            )
        )

        await self.session.commit()

        refreshed = await self.brand_moderation_repo.get_by_id(entity_id)
        if refreshed is None:
            raise ValueError("Brand moderation not found")

        return ModerationEditResponse(
            kind="brand",
            proposal=self._brand_to_proposal(refreshed),
            brandName=refreshed.proposed_name,
            brandDescription=refreshed.proposed_desc,
            avatarImage=refreshed.proposed_avatar_image,
            bannerImage=refreshed.proposed_banner_image,
            actionType=refreshed.action_type.value,
        )

    async def decide(
        self,
        proposal_id: str,
        moderator_id: int,
        status: ModerationStatus,
        comment: str | None = None,
    ) -> ModerationProposalResponse:
        if status not in {
            ModerationStatus.APPROVED,
            ModerationStatus.REJECTED,
        }:
            raise ValueError("Status must be APPROVED or REJECTED")

        entity_type, entity_id = self.parse_proposal_id(proposal_id)
        if entity_type == self.PRODUCT_PREFIX:
            return await self._decide_product(
                entity_id, moderator_id, status, comment
            )
        return await self._decide_brand(
            entity_id, moderator_id, status, comment
        )

    async def _decide_product(
        self,
        product_id: int,
        moderator_id: int,
        status: ModerationStatus,
        comment: str | None,
    ) -> ModerationProposalResponse:
        product = await self.product_repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_seller_card=True,
                include_subcategory=True,
                include_moderations=True,
            )
        )
        if product is None:
            raise ValueError("Product not found")

        if product.status != ModerationStatus.PENDING:
            raise ValueError("Product is not pending moderation")

        default_comment = (
            "Заявка принята модератором."
            if status == ModerationStatus.APPROVED
            else "Заявка отклонена модератором."
        )
        moderation_comment = (comment or default_comment).strip()
        if not moderation_comment:
            raise ValueError("Comment is required")

        product.status = status
        moderation = ProductModeration(
            product_id=product.id,
            moderator_id=moderator_id,
            status=status,
            comment=moderation_comment,
        )
        self.session.add(moderation)
        await self.session.commit()

        refreshed_product = await self.product_repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_seller_card=True,
                include_subcategory=True,
                include_moderations=True,
            )
        )
        if refreshed_product is None:
            raise ValueError("Product not found")

        return self._product_to_proposal(refreshed_product)

    async def _decide_brand(
        self,
        moderation_id: int,
        moderator_id: int,
        status: ModerationStatus,
        comment: str | None,
    ) -> ModerationProposalResponse:
        moderation = await self.brand_moderation_repo.get_by_id(moderation_id)
        if moderation is None:
            raise ValueError("Brand moderation not found")

        if moderation.status != ModerationStatus.PENDING:
            raise ValueError("Brand moderation is not pending")

        default_comment = (
            "Заявка принята модератором."
            if status == ModerationStatus.APPROVED
            else "Заявка отклонена модератором."
        )
        moderation_comment = (comment or default_comment).strip()
        if not moderation_comment:
            raise ValueError("Comment is required")

        seller_card = moderation.seller_card
        moderation.status = status
        moderation.moderator_id = moderator_id
        moderation.comment = moderation_comment

        if status == ModerationStatus.APPROVED:
            seller_card.name = moderation.proposed_name
            seller_card.desc = moderation.proposed_desc
            seller_card.banner_image = moderation.proposed_banner_image
            seller_card.avatar_image = moderation.proposed_avatar_image
            seller_card.status = ModerationStatus.APPROVED
        elif moderation.action_type == SellerCardModerationAction.CREATE_SHOP:
            seller_card.status = ModerationStatus.REJECTED

        await self.session.commit()

        refreshed = await self.brand_moderation_repo.get_by_id(moderation_id)
        if refreshed is None:
            raise ValueError("Brand moderation not found")

        return self._brand_to_proposal(refreshed)
