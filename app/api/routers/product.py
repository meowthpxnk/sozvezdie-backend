from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import BaseModel
from fastapi import Response
from app.api.dependencies import DatabaseDepends
from app.api.dependencies import AuthAPIDepends, BearerAuthDepends
from app.repositories.specs.user import UserSpec
from app.schemas.api.responses import (
    ProductFacetsResponse,
    ProductResponse,
    ProductCreateRequest,
    ProductsPageResponse,
)
from datetime import datetime
from app.schemas.schemas import ProductCreateForm
from app.services import ProductService
from app.services.user import UserService

router = APIRouter()


# @router.get("/product")
# async def get_products() -> list[ProductResponse]:
#     return [
#         ProductResponse(
#             id="1",
#             name="Product 1",
#             description="Description 1",
#             price=10000,
#             mainImage="https://example.com/image.jpg",
#             images=[
#                 "https://example.com/image.jpg",
#                 "https://example.com/image.jpg",
#             ],
#             authorId="1",
#             stockCount=24,
#         )
#     ]


@router.get("/product")
async def get_product(
    session: DatabaseDepends,
    category_slug: str | None = Query(default=None),
    subcategory_slug: str | None = Query(default=None),
    fandom_slug: str | None = Query(default=None),
    after_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="popular"),
    starts_with: str | None = Query(default=None, max_length=120),
) -> ProductsPageResponse:
    if sort not in {"popular", "price-asc", "price-desc", "newest", "oldest"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid sort value")

    return await ProductService(session).get_products_page(
        category_slug=category_slug,
        subcategory_slug=subcategory_slug,
        fandom_slug=fandom_slug,
        after_id=after_id,
        limit=limit,
        sort=sort,
        starts_with=starts_with,
    )


@router.get("/product/facets/categories")
async def get_category_facets(
    session: DatabaseDepends,
    fandom_slug: str | None = Query(default=None),
) -> ProductFacetsResponse:
    return await ProductService(session).get_category_facets(fandom_slug)


@router.get("/product/facets/subcategories")
async def get_subcategory_facets(
    session: DatabaseDepends,
    category_slug: str = Query(...),
    fandom_slug: str | None = Query(default=None),
) -> ProductFacetsResponse:
    return await ProductService(session).get_subcategory_facets(
        category_slug, fandom_slug
    )


@router.get("/product/facets/fandoms")
async def get_fandom_facets(
    session: DatabaseDepends,
    category_slug: str | None = Query(default=None),
    subcategory_slug: str | None = Query(default=None),
) -> ProductFacetsResponse:
    return await ProductService(session).get_fandom_facets(
        category_slug, subcategory_slug
    )


@router.get("/product/bulk")
async def get_products_bulk(
    session: DatabaseDepends,
    ids: str = Query(default=""),
) -> list[ProductResponse]:
    product_ids = [
        product_id.strip()
        for product_id in ids.split(",")
        if product_id.strip()
    ]
    return await ProductService(session).get_products_by_ids(product_ids)


@router.get("/product/{product_id}/similar")
async def get_similar_products(
    session: DatabaseDepends,
    product_id: int,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[ProductResponse]:
    return await ProductService(session).get_similar_products(
        product_id, limit=limit
    )


@router.get("/product/{product_id}")
async def get_product_by_id(
    session: DatabaseDepends, product_id: int
) -> ProductResponse:
    return await ProductService(session).get_product(product_id)


@router.post("/product")
async def create_product(
    session: DatabaseDepends,
    bearer_token: BearerAuthDepends,
    name: str = Form(...),
    desc: str = Form(...),
    price: int = Form(...),
    quantity: int = Form(...),
    category_slug: str | None = Form(default=None),
    subcategory_slug: str | None = Form(default=None),
    fandom_slug: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
) -> None:
    from app.core import media_client

    from fastapi import HTTPException

    user = await UserService(session).get_user(
        bearer_token.username,
        UserSpec(username=bearer_token.username, include_seller_card=True),
    )
    if user.seller_card is None:
        raise HTTPException(status_code=400, detail="Seller card not found")

    from app.schemas.database import ModerationStatus

    if user.seller_card.status != ModerationStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Seller card must be approved before creating products",
        )

    seller_card_id = user.seller_card.id

    form = ProductCreateForm(
        name=name,
        desc=desc,
        price=price,
        seller_card_id=seller_card_id,
        images=files,
        quantity=quantity,
        category_slug=category_slug,
        subcategory_slug=subcategory_slug,
        fandom_slug=fandom_slug,
    )

    try:
        await ProductService(session).create_product(form, media_client)
    except ValueError as error:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(error)) from error

    # return ProductResponse(
    #     id=product.id,
    #     name="Product 1",
    #     description="Description 1",
    #     price=10000,
    #     mainImage="https://example.com/image.jpg",
    #     images=[
    #         "https://example.com/image.jpg",
    #         "https://example.com/image.jpg",
    #     ],
    #     authorId="1",
    #     stockCount=24,
    # )
