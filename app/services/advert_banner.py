from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdvertBanner
from app.schemas.api.responses import AdvertBannerResponse
from app.schemas.schemas import (
    AdvertBannerCreateForm,
    AdvertBannerReorderRequest,
    AdvertBannerUpdateForm,
)
from app.media_client import MediaClient

from app.repositories.product import ProductRepository
from app.repositories.advert_banner import AdvertBannerRepository

# from app.repositories.user_settings import UserSettingsRepository
from app.repositories.specs.product import ProductSpec


class AdvertBannerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AdvertBannerRepository(session)

    async def create_advert_banner(
        self,
        data: AdvertBannerCreateForm,
        media_client: MediaClient,
    ) -> AdvertBanner:

        content = await data.image.read()

        content_type = data.image.content_type or "image/jpeg"

        image_id = await media_client.upload_image(
            image_bytes=content,
            content_type=content_type,
        )

        advert_banner = AdvertBanner(
            image_uuid=image_id,
            link=data.link,
            text=data.text,
            sort_order=await self.repo.get_next_sort_order(),
        )

        self.repo.add(advert_banner)
        await self.session.commit()
        return advert_banner

    def _to_response(self, advert_banner: AdvertBanner) -> AdvertBannerResponse:
        return AdvertBannerResponse(
            id=advert_banner.id,
            image=str(advert_banner.image_uuid),
            href=advert_banner.link,
            title=advert_banner.text,
        )

    async def get_advert_banners(self) -> list[AdvertBannerResponse]:
        advert_banners = await self.repo.get_all()
        return [self._to_response(advert_banner) for advert_banner in advert_banners]

    async def update_advert_banner(
        self,
        banner_id: int,
        data: AdvertBannerUpdateForm,
        media_client: MediaClient,
    ) -> AdvertBanner:
        advert_banner = await self.repo.get_by_id(banner_id)
        if advert_banner is None:
            raise ValueError("Advert banner not found")

        if data.image is not None:
            content = await data.image.read()
            content_type = data.image.content_type or "image/jpeg"
            advert_banner.image_uuid = await media_client.upload_image(
                image_bytes=content,
                content_type=content_type,
            )

        advert_banner.link = data.link.strip()
        advert_banner.text = data.text.strip()
        await self.session.commit()
        await self.session.refresh(advert_banner)
        return advert_banner

    async def delete_advert_banner(self, banner_id: int) -> None:
        advert_banner = await self.repo.get_by_id(banner_id)
        if advert_banner is None:
            raise ValueError("Advert banner not found")
        await self.repo.delete(advert_banner)
        await self.session.commit()

    async def reorder_advert_banners(
        self, data: AdvertBannerReorderRequest
    ) -> list[AdvertBannerResponse]:
        banners = await self.repo.get_all()
        banners_by_id = {banner.id: banner for banner in banners}
        ordered_ids = data.ordered_ids

        if len(ordered_ids) != len(banners_by_id):
            raise ValueError("Ordered ids must include all banners")

        if len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("Ordered ids must be unique")

        if any(banner_id not in banners_by_id for banner_id in ordered_ids):
            raise ValueError("Unknown banner id in ordered ids")

        for index, banner_id in enumerate(ordered_ids):
            banners_by_id[banner_id].sort_order = index

        await self.session.commit()
        return await self.get_advert_banners()
