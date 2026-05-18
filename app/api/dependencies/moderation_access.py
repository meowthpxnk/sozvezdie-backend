from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import BearerAuthDepends
from app.api.dependencies import DatabaseDepends
from app.core.super_moderator import SUPER_MODERATOR_ROLE, is_super_moderator_username
from app.models import User
from app.schemas.database import UserRoleEnum
from app.services.user import UserService


def can_access_moderation(
    token_role: str,
    user: User,
) -> bool:
    if token_role == SUPER_MODERATOR_ROLE or is_super_moderator_username(user.username):
        return True
    return user.role == UserRoleEnum.MODERATOR


async def require_moderation_access(
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> User:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not can_access_moderation(token.role, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return user


ModerationAccessDepends = Annotated[User, Depends(require_moderation_access)]
