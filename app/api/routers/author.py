import json

from fastapi import APIRouter, Form, Query, UploadFile, File, HTTPException, status
from app.api.auth_routing import RBACRouter
from pydantic import BaseModel
from fastapi import Response
from app.api.dependencies import DatabaseDepends
from app.api.dependencies import AuthAPIDepends, BearerAuthDepends
from app.schemas.api.responses import (
    AuthorResponse,
    AuthorDashboardResponse,
    SellerCardResponse,
    ProductResponse,
    SellerProductResponse,
)
from app.repositories.specs.user import UserSpec
from app.schemas.database import UserRoleEnum
from app.schemas.permissions import PermissionEnum
from app.schemas.schemas import (
    ProductImageSlotForm,
    ProductUpdateForm,
    SellerCardCreateForm,
    SellerCardUpdateForm,
)
from app.schemas.api.responses import AuthorBrandModerationResponse
from app.services.product import ProductService
from app.services.seller_card import SellerCardService
from app.services.user import UserService

router = RBACRouter(prefix="/author", tags=["Author"])

_RESERVED_AUTHOR_PATHS = frozenset({"me", "bulk"})


@router.get("/me", name="get_my_author_dashboard")
async def get_my_author_dashboard(
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> AuthorDashboardResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return await SellerCardService(session).get_dashboard_for_user(user.id)


@router.get("/me/products", name="get_my_author_products")
async def get_my_author_products(
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> list[SellerProductResponse]:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return await ProductService(session).get_products_for_seller_user(user.id)


@router.get("/me/products/{product_id}", name="get_my_author_product")
async def get_my_author_product(
    product_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> SellerProductResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return await ProductService(session).get_seller_product_by_id(user.id, product_id)


@router.put("/me/products/{product_id}", name="update_my_author_product")
async def update_my_author_product(
    product_id: int,
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

    user = await UserService(session).get_user(
        token.username,
        UserSpec(username=token.username, include_seller_card=True),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    if user.seller_card is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller card not found",
        )

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

    try:
        await ProductService(session).update_product_for_seller(
            product_id,
            ProductUpdateForm(
                name=name,
                desc=desc,
                price=price,
                quantity=quantity,
                seller_card_id=user.seller_card.id,
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

    return await ProductService(session).get_seller_product_by_id(user.id, product_id)


@router.get("/me/brand-moderations", name="get_my_brand_moderations")
async def get_my_brand_moderations(
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> list[AuthorBrandModerationResponse]:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return await SellerCardService(session).get_brand_moderations_for_user(user.id)


@router.put("/me", name="update_my_author_brand")
async def update_my_author_brand(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    name: str = Form(...),
    desc: str = Form(...),
    banner_image: UploadFile | None = File(default=None),
    avatar_image: UploadFile | None = File(default=None),
) -> SellerCardResponse:
    from app.core import media_client

    user = await UserService(session).get_user(
        token.username,
        UserSpec(username=token.username, include_seller_card=True),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    if user.seller_card is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller card not found",
        )

    try:
        seller_card = await SellerCardService(session).update_seller_card(
            user.id,
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

    return SellerCardService(session)._to_response(seller_card)


@router.get("")
async def get_authors(session: DatabaseDepends) -> list[SellerCardResponse]:
    return await SellerCardService(session).get_all()


@router.get("/bulk")
async def get_authors_bulk(
    session: DatabaseDepends,
    ids: str = Query(default=""),
) -> list[SellerCardResponse]:
    author_ids = [
        author_id.strip()
        for author_id in ids.split(",")
        if author_id.strip()
    ]
    return await SellerCardService(session).get_by_ids(author_ids)


@router.get("/{author_id}")
async def get_author(
    author_id: str, session: DatabaseDepends
) -> SellerCardResponse:
    if author_id in _RESERVED_AUTHOR_PATHS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    if not author_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author not found",
        )

    return await SellerCardService(session).get_by_id(author_id)


@router.get("/{author_id}/products")
async def get_author_products(
    author_id: str, session: DatabaseDepends
) -> list[ProductResponse]:
    return await ProductService(session).get_products_by_author_id(author_id)


@router.post(
    "",
    permissions=[
        PermissionEnum.SELLER_CARD_CREATE,
        PermissionEnum.SELLER_CARD_READ,
    ],
)
async def create_author(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    name: str = Form(...),
    desc: str = Form(...),
    banner_image: UploadFile = File(...),
    avatar_image: UploadFile = File(...),
) -> SellerCardResponse:
    from app.core import media_client

    user = await UserService(session).get_user(
        token.username,
        UserSpec(username=token.username, include_seller_card=True),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role != UserRoleEnum.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    if user.seller_card is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller card already exists",
        )

    seller_card = await SellerCardService(session).create_seller_card(
        SellerCardCreateForm(
            user_id=user.id,
            name=name,
            desc=desc,
            banner_image=banner_image,
            avatar_image=avatar_image,
        ),
        media_client,
    )
    return SellerCardService(session)._to_response(seller_card)
