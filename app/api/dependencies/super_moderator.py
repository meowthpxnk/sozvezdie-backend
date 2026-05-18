from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import BearerAuthDepends
from app.core.super_moderator import SUPER_MODERATOR_ROLE


def require_super_moderator(token: BearerAuthDepends) -> BearerAuthDepends:
    if token.role != SUPER_MODERATOR_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return token


SuperModeratorDepends = Annotated[
    BearerAuthDepends,
    Depends(require_super_moderator),
]
