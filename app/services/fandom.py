from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fandom
from app.repositories.fandom import FandomRepository
from app.schemas.api.responses import (
    FandomAdminCreateRequest,
    FandomCreateRequest,
    FandomResponse,
    FandomUpdateRequest,
)
from app.utils.slug import validate_slug


class FandomService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FandomRepository(session)

    def _to_response(self, fandom: Fandom) -> FandomResponse:
        return FandomResponse(
            slug=fandom.slug,
            title=fandom.title,
            isApproved=fandom.is_approved,
        )

    async def get_fandoms(self, search: str | None = None) -> list[FandomResponse]:
        fandoms = await self.repo.get_all(search=search)
        return [self._to_response(fandom) for fandom in fandoms]

    async def create_fandom(
        self,
        data: FandomCreateRequest | FandomAdminCreateRequest,
        *,
        is_approved: bool | None = None,
    ) -> FandomResponse:
        slug = validate_slug(data.slug)
        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        existing = await self.repo.get_by_slug(slug)
        if existing is not None:
            raise ValueError("Fandom slug already exists")

        if is_approved is None:
            if isinstance(data, FandomAdminCreateRequest):
                is_approved = data.is_approved
            else:
                is_approved = False

        fandom = Fandom(slug=slug, title=title, is_approved=is_approved)
        self.repo.add(fandom)
        await self.session.commit()
        await self.session.refresh(fandom)
        return self._to_response(fandom)

    async def update_fandom(
        self, slug: str, data: FandomUpdateRequest
    ) -> FandomResponse:
        fandom = await self.repo.get_by_slug(slug)
        if fandom is None:
            raise ValueError("Fandom not found")

        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        fandom.title = title
        fandom.is_approved = data.is_approved
        await self.session.commit()
        await self.session.refresh(fandom)
        return self._to_response(fandom)

    async def delete_fandom(self, slug: str) -> None:
        fandom = await self.repo.get_by_slug(slug)
        if fandom is None:
            raise ValueError("Fandom not found")
        await self.repo.delete(fandom)
        await self.session.commit()
