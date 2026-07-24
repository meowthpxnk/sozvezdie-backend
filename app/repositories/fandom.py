from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fandom


class FandomRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, search: str | None = None) -> list[Fandom]:
        stmt = select(Fandom)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(Fandom.title.ilike(pattern), Fandom.slug.ilike(pattern))
            )
        stmt = stmt.order_by(Fandom.title.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Fandom | None:
        stmt = select(Fandom).where(Fandom.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, fandom: Fandom) -> Fandom:
        self.session.add(fandom)
        return fandom

    async def delete(self, fandom: Fandom) -> None:
        await self.session.delete(fandom)

    async def mark_approved(self, slug: str | None) -> None:
        if not slug:
            return

        fandom = await self.get_by_slug(slug)
        if fandom is None or fandom.is_approved:
            return

        fandom.is_approved = True
