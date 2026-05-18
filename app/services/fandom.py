from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fandom
from app.repositories.fandom import FandomRepository
from app.schemas.api.responses import FandomCreateRequest, FandomResponse
from app.utils.slug import validate_slug


class FandomService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FandomRepository(session)

    async def get_fandoms(self) -> list[FandomResponse]:
        fandoms = await self.repo.get_all()
        return [
            FandomResponse(slug=fandom.slug, title=fandom.title) for fandom in fandoms
        ]

    async def create_fandom(self, data: FandomCreateRequest) -> FandomResponse:
        slug = validate_slug(data.slug)
        title = data.title.strip()
        if not title:
            raise ValueError("Title is required")

        existing = await self.repo.get_by_slug(slug)
        if existing is not None:
            raise ValueError("Fandom slug already exists")

        fandom = Fandom(slug=slug, title=title)
        self.session.add(fandom)
        await self.session.commit()
        await self.session.refresh(fandom)
        return FandomResponse(slug=fandom.slug, title=fandom.title)
