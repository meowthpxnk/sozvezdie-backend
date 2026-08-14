from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthorInvite


def normalize_one_c_author_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class AuthorInviteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, invite: AuthorInvite) -> AuthorInvite:
        self.session.add(invite)
        return invite

    async def get_unused_by_token(self, token: str) -> AuthorInvite | None:
        stmt = select(AuthorInvite).where(
            AuthorInvite.token == token,
            AuthorInvite.used_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_unused_by_one_c_author_id(
        self, one_c_author_id: str
    ) -> AuthorInvite | None:
        stmt = select(AuthorInvite).where(
            AuthorInvite.one_c_author_id == one_c_author_id,
            AuthorInvite.used_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, invite: AuthorInvite) -> None:
        await self.session.delete(invite)
        await self.session.flush()
