import json

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.api.dependencies.moderation_access import ModerationAccessDepends, require_moderation_access
from app.schemas.api.responses import (
    AuthorBrandModerationResponse,
    ModerationDecisionRequest,
    ModerationEditResponse,
    ModerationProposalResponse,
    ModeratorCatalogProductDeleteRequest,
    ModeratorOrderDetailResponse,
    ModeratorOrderStatusUpdateRequest,
    ModeratorOrdersListResponse,
    SellerProductResponse,
)
from app.schemas.database import ModerationStatus, OrderStatus
from app.services.order import OrderService
from app.schemas.schemas import ProductImageSlotForm, ProductUpdateForm, SellerCardUpdateForm
from app.services.moderation import ModerationService
from app.services.product import ProductService
from app.services.seller_card import SellerCardService

router = APIRouter(prefix="/moderation", tags=["Moderation"])


@router.get("/proposals")
async def get_moderation_proposals(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    status_filter: ModerationStatus | None = Query(default=None, alias="status"),
) -> list[ModerationProposalResponse]:
    await require_moderation_access(token, session)
    return await ModerationService(session).list_proposals(status_filter)


@router.get("/proposals/{proposal_id}")
async def get_moderation_proposal_edit(
    proposal_id: str,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> ModerationEditResponse:
    await require_moderation_access(token, session)

    try:
        return await ModerationService(session).get_proposal_edit(proposal_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/proposals/{proposal_id}/product")
async def update_moderation_proposal_product(
    proposal_id: str,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    name: str = Form(...),
    desc: str = Form(...),
    price: int = Form(...),
    quantity: int = Form(...),
    image_slots: str = Form(...),
    category_slug: str | None = Form(default=None),
    subcategory_slug: str | None = Form(default=None),
    fandom_slug: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
) -> SellerProductResponse:
    from app.core import media_client

    await require_moderation_access(token, session)

    try:
        entity_type, entity_id = ModerationService.parse_proposal_id(proposal_id)
        if entity_type != ModerationService.PRODUCT_PREFIX:
            raise ValueError("Not a product proposal")
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    try:
        slots_payload = json.loads(image_slots)
        image_slot_forms = [
            ProductImageSlotForm(
                type=slot["type"],
                uuid=slot.get("uuid"),
            )
            for slot in slots_payload
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image_slots payload",
        ) from error

    product_service = ProductService(session)
    try:
        await product_service.update_product_for_moderation(
            entity_id,
            ProductUpdateForm(
                name=name,
                desc=desc,
                price=price,
                quantity=quantity,
                seller_card_id=0,
                image_slots=image_slot_forms,
                new_images=files,
                category_slug=category_slug,
                subcategory_slug=subcategory_slug,
                fandom_slug=fandom_slug,
            ),
            media_client,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    try:
        return await product_service.get_product_for_moderation(entity_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/proposals/{proposal_id}/brand")
async def update_moderation_proposal_brand(
    proposal_id: str,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    name: str = Form(...),
    desc: str = Form(...),
    banner_image: UploadFile | None = File(default=None),
    avatar_image: UploadFile | None = File(default=None),
    tiktok_url: str = Form(default=""),
    telegram_channel_url: str = Form(default=""),
    vk_url: str = Form(default=""),
) -> ModerationEditResponse:
    from app.core import media_client

    await require_moderation_access(token, session)

    try:
        return await ModerationService(session).update_brand_proposal(
            proposal_id,
            SellerCardUpdateForm(
                name=name,
                desc=desc,
                banner_image=banner_image,
                avatar_image=avatar_image,
                tiktok_url=tiktok_url,
                telegram_channel_url=telegram_channel_url,
                vk_url=vk_url,
            ),
            media_client,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/catalog/products/{product_id}")
async def get_moderator_catalog_product_edit(
    product_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> ModerationEditResponse:
    await require_moderation_access(token, session)

    try:
        return await ModerationService(session).get_catalog_product_edit(product_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/catalog/products/{product_id}")
async def update_moderator_catalog_product(
    product_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    name: str = Form(...),
    desc: str = Form(...),
    price: int = Form(...),
    quantity: int = Form(...),
    image_slots: str = Form(...),
    comment: str | None = Form(default=None),
    category_slug: str | None = Form(default=None),
    subcategory_slug: str | None = Form(default=None),
    fandom_slug: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
) -> SellerProductResponse:
    from app.core import media_client

    moderator = await require_moderation_access(token, session)

    try:
        slots_payload = json.loads(image_slots)
        image_slot_forms = [
            ProductImageSlotForm(
                type=slot["type"],
                uuid=slot.get("uuid"),
            )
            for slot in slots_payload
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image_slots payload",
        ) from error

    product_service = ProductService(session)
    try:
        await product_service.update_product_by_moderator(
            product_id,
            ProductUpdateForm(
                name=name,
                desc=desc,
                price=price,
                quantity=quantity,
                seller_card_id=0,
                image_slots=image_slot_forms,
                new_images=files,
                category_slug=category_slug,
                subcategory_slug=subcategory_slug,
                fandom_slug=fandom_slug,
            ),
            media_client,
            moderator_id=moderator.id,
            comment=comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    try:
        return await product_service.get_product_for_moderator_catalog_edit(product_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.post("/catalog/products/{product_id}/delete")
async def delete_moderator_catalog_product(
    product_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: ModeratorCatalogProductDeleteRequest,
) -> SellerProductResponse:
    moderator = await require_moderation_access(token, session)

    try:
        return await ProductService(session).delete_catalog_product_by_moderator(
            product_id,
            moderator_id=moderator.id,
            comment=data.comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.post("/catalog/brands/{seller_card_id}/delete")
async def delete_moderator_catalog_brand(
    seller_card_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: ModeratorCatalogProductDeleteRequest,
) -> AuthorBrandModerationResponse:
    moderator = await require_moderation_access(token, session)

    try:
        return await SellerCardService(session).delete_catalog_brand_by_moderator(
            seller_card_id,
            moderator_id=moderator.id,
            comment=data.comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/catalog/brands/{seller_card_id}")
async def get_moderator_catalog_brand_edit(
    seller_card_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> ModerationEditResponse:
    await require_moderation_access(token, session)

    try:
        return await ModerationService(session).get_catalog_brand_edit(seller_card_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/catalog/brands/{seller_card_id}")
async def update_moderator_catalog_brand(
    seller_card_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    name: str = Form(...),
    desc: str = Form(...),
    comment: str | None = Form(default=None),
    banner_image: UploadFile | None = File(default=None),
    avatar_image: UploadFile | None = File(default=None),
    tiktok_url: str = Form(default=""),
    telegram_channel_url: str = Form(default=""),
    vk_url: str = Form(default=""),
) -> ModerationEditResponse:
    from app.core import media_client

    moderator = await require_moderation_access(token, session)

    try:
        await SellerCardService(session).update_seller_card_by_moderator(
            seller_card_id,
            SellerCardUpdateForm(
                name=name,
                desc=desc,
                banner_image=banner_image,
                avatar_image=avatar_image,
                tiktok_url=tiktok_url,
                telegram_channel_url=telegram_channel_url,
                vk_url=vk_url,
            ),
            media_client,
            moderator_id=moderator.id,
            comment=comment,
        )
        return await ModerationService(session).get_catalog_brand_edit(seller_card_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/orders")
async def list_moderation_orders(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    archive: bool = Query(default=False),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ModeratorOrdersListResponse:
    await require_moderation_access(token, session)
    return await OrderService(session).list_orders_for_moderation(
        status_filter=status_filter,
        archive=archive,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/orders/{order_id}")
async def get_moderation_order(
    order_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> ModeratorOrderDetailResponse:
    await require_moderation_access(token, session)
    try:
        return await OrderService(session).get_order_for_moderation(order_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.patch("/orders/{order_id}/status")
async def update_moderation_order_status(
    order_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: ModeratorOrderStatusUpdateRequest,
) -> ModeratorOrderDetailResponse:
    await require_moderation_access(token, session)
    try:
        return await OrderService(session).update_order_status_for_moderation(
            order_id,
            data.status,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.post("/proposals/{proposal_id}/decide")
async def decide_moderation_proposal(
    proposal_id: str,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: ModerationDecisionRequest,
) -> ModerationProposalResponse:
    moderator = await require_moderation_access(token, session)

    try:
        return await ModerationService(session).decide(
            proposal_id=proposal_id,
            moderator_id=moderator.id,
            status=data.status,
            comment=data.comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
