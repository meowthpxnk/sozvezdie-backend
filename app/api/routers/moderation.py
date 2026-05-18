import json

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.api.dependencies.moderation_access import ModerationAccessDepends, require_moderation_access
from app.schemas.api.responses import (
    ModerationDecisionRequest,
    ModerationEditResponse,
    ModerationProposalResponse,
    SellerProductResponse,
)
from app.schemas.database import ModerationStatus
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
