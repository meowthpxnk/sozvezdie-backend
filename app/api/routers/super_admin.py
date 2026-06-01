from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.super_moderator import SuperModeratorDepends
from app.schemas.api.responses import (
    AdvertBannerResponse,
    FaqItemResponse,
    SuperAdminAssignRoleRequest,
    SuperAdminUserResponse,
)
from app.schemas.database import UserRoleEnum
from app.schemas.schemas import (
    AdvertBannerCreateForm,
    AdvertBannerUpdateForm,
    FaqItemCreateRequest,
    FaqItemReorderRequest,
    FaqItemUpdateRequest,
)
from app.services.advert_banner import AdvertBannerService
from app.services.faq_item import FaqItemService
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
        return await SuperAdminService(session).assign_role(user_id, data.role)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


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
