from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.super_moderator import SuperModeratorDepends
from app.schemas.api.responses import (
    AdvertBannerResponse,
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    FandomAdminCreateRequest,
    FandomResponse,
    FandomUpdateRequest,
    FaqItemResponse,
    SubcategoryAdminCreateRequest,
    SubcategoryResponse,
    SubcategoryUpdateRequest,
    SuperAdminAssignOneCRequest,
    SuperAdminAssignRoleRequest,
    SuperAdminAuthorInviteRequest,
    SuperAdminAuthorInviteResponse,
    SuperAdminUserResponse,
)
from app.schemas.database import UserRoleEnum
from app.schemas.schemas import (
    AdvertBannerCreateForm,
    AdvertBannerReorderRequest,
    AdvertBannerUpdateForm,
    FaqItemCreateRequest,
    FaqItemReorderRequest,
    FaqItemUpdateRequest,
)
from app.services.advert_banner import AdvertBannerService
from app.services.category import CategoryService
from app.services.fandom import FandomService
from app.services.faq_item import FaqItemService
from app.services.subcategory import SubcategoryService
from app.services.super_admin import SuperAdminService

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])


@router.get("/users")
async def list_users(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SuperAdminUserResponse]:
    return await SuperAdminService(session).list_users(search=search, limit=limit)


@router.patch("/users/{user_id}/role")
async def assign_user_role(
    user_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: SuperAdminAssignRoleRequest,
) -> SuperAdminUserResponse:
    try:
        return await SuperAdminService(session).assign_role(
            user_id,
            data.role,
            one_c_author_id=data.one_c_author_id,
            delete_from_1c=data.delete_from_1c,
            delete_shop=data.delete_shop,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/users/{user_id}/one-c")
async def delete_user_one_c(
    user_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> SuperAdminUserResponse:
    try:
        return await SuperAdminService(session).delete_from_1c(user_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/users/{user_id}/shop")
async def delete_user_shop(
    user_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> SuperAdminUserResponse:
    try:
        return await SuperAdminService(session).delete_shop(user_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.patch("/users/{user_id}/one-c")
async def assign_user_one_c(
    user_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: SuperAdminAssignOneCRequest,
) -> SuperAdminUserResponse:
    try:
        return await SuperAdminService(session).assign_one_c_author_id(
            user_id, data.one_c_author_id
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.post("/one-c/authors")
async def generate_one_c_author(
    _: SuperModeratorDepends,
):
    from app.integrations.one_c import OneCUnavailable, create_author

    try:
        await create_author()
    except OneCUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.message,
        ) from error
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Нет доступа к 1C введите код вручную",
    )


@router.post("/author-invites", status_code=status.HTTP_201_CREATED)
async def create_author_invite(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: SuperAdminAuthorInviteRequest,
) -> SuperAdminAuthorInviteResponse:
    try:
        invite = await SuperAdminService(session).create_author_invite(
            data.one_c_author_id
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return SuperAdminAuthorInviteResponse(token=invite.token)


@router.get("/banners")
async def list_banners(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> list[AdvertBannerResponse]:
    return await AdvertBannerService(session).get_advert_banners()


@router.post("/banners")
async def create_banner(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    image: UploadFile = File(...),
    link: str = Form(...),
    text: str = Form(...),
) -> AdvertBannerResponse:
    from app.core import media_client

    service = AdvertBannerService(session)
    banner = await service.create_advert_banner(
        AdvertBannerCreateForm(image=image, link=link, text=text),
        media_client,
    )
    return service._to_response(banner)


@router.put("/banners/reorder")
async def reorder_banners(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: AdvertBannerReorderRequest,
) -> list[AdvertBannerResponse]:
    try:
        return await AdvertBannerService(session).reorder_advert_banners(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/banners/{banner_id}")
async def update_banner(
    banner_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    link: str = Form(...),
    text: str = Form(...),
    image: UploadFile | None = File(default=None),
) -> AdvertBannerResponse:
    from app.core import media_client

    service = AdvertBannerService(session)
    try:
        banner = await service.update_advert_banner(
            banner_id,
            AdvertBannerUpdateForm(image=image, link=link, text=text),
            media_client,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return service._to_response(banner)


@router.delete("/banners/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_banner(
    banner_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> None:
    try:
        await AdvertBannerService(session).delete_advert_banner(banner_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/faq")
async def list_faq_items(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    search: str | None = Query(default=None),
) -> list[FaqItemResponse]:
    return await FaqItemService(session).list_items(search=search)


@router.post("/faq", status_code=status.HTTP_201_CREATED)
async def create_faq_item(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: FaqItemCreateRequest,
) -> FaqItemResponse:
    return await FaqItemService(session).create_item(data)


@router.put("/faq/reorder")
async def reorder_faq_items(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: FaqItemReorderRequest,
) -> list[FaqItemResponse]:
    try:
        return await FaqItemService(session).reorder_items(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/faq/{item_id}")
async def update_faq_item(
    item_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: FaqItemUpdateRequest,
) -> FaqItemResponse:
    try:
        return await FaqItemService(session).update_item(item_id, data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/faq/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq_item(
    item_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> None:
    try:
        await FaqItemService(session).delete_item(item_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/fandoms")
async def list_fandoms(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    search: str | None = Query(default=None),
) -> list[FandomResponse]:
    return await FandomService(session).get_fandoms(search=search)


@router.post("/fandoms", status_code=status.HTTP_201_CREATED)
async def create_fandom(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: FandomAdminCreateRequest,
) -> FandomResponse:
    try:
        return await FandomService(session).create_fandom(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/fandoms/{fandom_slug}")
async def update_fandom(
    fandom_slug: str,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: FandomUpdateRequest,
) -> FandomResponse:
    try:
        return await FandomService(session).update_fandom(fandom_slug, data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/fandoms/{fandom_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fandom(
    fandom_slug: str,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> None:
    try:
        await FandomService(session).delete_fandom(fandom_slug)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/categories")
async def list_categories(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    search: str | None = Query(default=None),
) -> list[CategoryResponse]:
    return await CategoryService(session).get_categories(search=search)


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: CategoryCreateRequest,
) -> CategoryResponse:
    try:
        return await CategoryService(session).create_category(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/categories/{category_slug}")
async def update_category(
    category_slug: str,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: CategoryUpdateRequest,
) -> CategoryResponse:
    try:
        return await CategoryService(session).update_category(category_slug, data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/categories/{category_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_slug: str,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> None:
    try:
        await CategoryService(session).delete_category(category_slug)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("/subcategories")
async def list_subcategories(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    search: str | None = Query(default=None),
    category_slug: str | None = Query(default=None),
) -> list[SubcategoryResponse]:
    return await SubcategoryService(session).list_subcategories(
        category_slug=category_slug,
        search=search,
    )


@router.post("/subcategories", status_code=status.HTTP_201_CREATED)
async def create_subcategory(
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: SubcategoryAdminCreateRequest,
) -> SubcategoryResponse:
    try:
        return await SubcategoryService(session).create_admin_subcategory(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put("/subcategories/{subcategory_id}")
async def update_subcategory(
    subcategory_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
    data: SubcategoryUpdateRequest,
) -> SubcategoryResponse:
    try:
        return await SubcategoryService(session).update_subcategory(
            subcategory_id, data
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete(
    "/subcategories/{subcategory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subcategory(
    subcategory_id: int,
    _: SuperModeratorDepends,
    session: DatabaseDepends,
) -> None:
    try:
        await SubcategoryService(session).delete_subcategory(subcategory_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
