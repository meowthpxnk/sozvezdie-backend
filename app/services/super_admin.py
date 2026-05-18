from sqlalchemy.ext.asyncio import AsyncSession

from app.core.super_moderator import is_super_moderator_username
from app.repositories.specs.user import UserSpec
from app.repositories.user import UserRepository
from app.schemas.api.responses import SuperAdminUserResponse
from app.schemas.database import UserRoleEnum


ASSIGNABLE_ROLES = {
    UserRoleEnum.CUSTOMER,
    UserRoleEnum.SELLER,
    UserRoleEnum.MODERATOR,
}


class SuperAdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def list_users(
        self, *, search: str | None = None, limit: int = 50
    ) -> list[SuperAdminUserResponse]:
        users = await self.user_repo.list_users(search=search, limit=limit)
        return [
            SuperAdminUserResponse(
                id=user.id,
                username=user.username,
                role=user.role,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                is_super_moderator=is_super_moderator_username(user.username),
            )
            for user in users
        ]

    async def assign_role(self, user_id: int, role: UserRoleEnum) -> SuperAdminUserResponse:
        if role not in ASSIGNABLE_ROLES:
            raise ValueError("Role can only be CUSTOMER, SELLER or MODERATOR")

        user = await self.user_repo.get_user(UserSpec(id=user_id))
        if user is None:
            raise ValueError("User not found")
        if is_super_moderator_username(user.username):
            raise ValueError("Cannot change role for super moderator account")

        updated = await self.user_repo.update_role(user, role)
        await self.session.commit()
        await self.session.refresh(updated)

        return SuperAdminUserResponse(
            id=updated.id,
            username=updated.username,
            role=updated.role,
            full_name=updated.full_name,
            email=updated.email,
            phone=updated.phone,
            is_super_moderator=is_super_moderator_username(updated.username),
        )
