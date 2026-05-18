from fastapi import APIRouter, UploadFile, File, Form

from app.api.auth_routing import RBACRouter
from app.api.dependencies import DatabaseDepends

from app.schemas.api.responses import AdvertBannerResponse
from app.services.advert_banner import AdvertBannerService
from app.schemas.schemas import AdvertBannerCreateForm

router = RBACRouter(prefix="/advert-banner", tags=["Advert Banner"])


@router.get("")
async def get_advert_banner(
    session: DatabaseDepends,
) -> list[AdvertBannerResponse]:
    return await AdvertBannerService(session).get_advert_banners()


@router.post("")
async def create_advert_banner(
    session: DatabaseDepends,
    image: UploadFile = File(...),
    link: str = Form(...),
    text: str = Form(...),
) -> AdvertBannerResponse:
    from app.core import media_client

    data = AdvertBannerCreateForm(
        image=image,
        link=link,
        text=text,
    )
    advert_banner = await AdvertBannerService(session).create_advert_banner(
        data, media_client
    )
    return AdvertBannerResponse(
        id=advert_banner.id,
        image=str(advert_banner.image_uuid),
        href=advert_banner.link,
        title=advert_banner.text,
    )
