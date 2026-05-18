from fastapi import HTTPException, status

from app.api.auth_routing import RBACRouter
from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.schemas.api.responses import UserProfileResponse, UserProfileUpdateRequest
from app.schemas.permissions import PermissionEnum
from app.services.user import UserService

router = RBACRouter(prefix="/user", tags=["User"])


def _to_profile_response(user) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
    )


@router.get("/{user_id}", permissions=PermissionEnum.USER_READ)
async def get_user(session: DatabaseDepends, user_id: int):
    user = await UserService(session).get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _to_profile_response(user)


@router.put("/profile")
async def update_profile(
    session: DatabaseDepends,
    token: BearerAuthDepends,
    data: UserProfileUpdateRequest,
) -> UserProfileResponse:
    user = await UserService(session).update_user_profile(
        token.username,
        data,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _to_profile_response(user)
