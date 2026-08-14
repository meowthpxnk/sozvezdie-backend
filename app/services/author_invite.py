from datetime import datetime

import secrets
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthorInvite, User
from app.repositories.author_invite import (
    AuthorInviteRepository,
    normalize_one_c_author_id,
)
from app.repositories.specs.user import UserSpec
from app.repositories.user import UserRepository
from app.schemas.database import UserRoleEnum


class OneCAuthorIdTaken(ValueError):
    def __init__(self):
        super().__init__("Этот ID 1C уже занят")


class AuthorInviteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.invite_repo = AuthorInviteRepository(session)
        self.user_repo = UserRepository(session)

    async def assert_one_c_id_available(
        self,
        one_c_author_id: str,
        *,
        exclude_user_id: int | None = None,
        exclude_invite_id: int | None = None,
    ) -> str:
        normalized = normalize_one_c_author_id(one_c_author_id)
        if normalized is None:
            raise ValueError("Нужно указать ID автора 1C")

        existing_user = await self.user_repo.get_by_one_c_author_id(normalized)
        if existing_user is not None and existing_user.id != exclude_user_id:
            raise OneCAuthorIdTaken()

        existing_invite = await self.invite_repo.get_unused_by_one_c_author_id(
            normalized
        )
        if (
            existing_invite is not None
            and existing_invite.id != exclude_invite_id
        ):
            raise OneCAuthorIdTaken()

        return normalized

    async def create_invite(self, one_c_author_id: str) -> AuthorInvite:
        normalized = await self.assert_one_c_id_available(one_c_author_id)
        invite = AuthorInvite(
            token=secrets.token_urlsafe(32),
            one_c_author_id=normalized,
            created_at=datetime.now(),
        )
        self.invite_repo.add(invite)
        await self.session.commit()
        await self.session.refresh(invite)
        return invite

    async def apply_invite_to_new_user(
        self, user: User, token: str | None
    ) -> None:
        normalized_token = (token or "").strip()
        if not normalized_token:
            return

        invite = await self.invite_repo.get_unused_by_token(normalized_token)
        if invite is None:
            raise ValueError("Недействительная или уже использованная ссылка")

        await self.assert_one_c_id_available(
            invite.one_c_author_id,
            exclude_invite_id=invite.id,
        )
        user.role = UserRoleEnum.SELLER
        user.one_c_author_id = invite.one_c_author_id
        await self.invite_repo.delete(invite)
