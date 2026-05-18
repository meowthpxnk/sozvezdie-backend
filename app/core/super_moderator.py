import os
from functools import lru_cache

from app.schemas.database import UserRoleEnum

SUPER_MODERATOR_ROLE = "SUPER_MODERATOR"


@lru_cache
def get_super_moderator_credentials() -> tuple[str, str] | None:
    username = os.getenv("SUPER_MODERATOR_USERNAME", "").strip()
    password = os.getenv("SUPER_MODERATOR_PASSWORD", "").strip()
    if not username or not password:
        return None
    return username, password


def is_super_moderator_username(username: str) -> bool:
    credentials = get_super_moderator_credentials()
    if credentials is None:
        return False
    return username == credentials[0]


def resolve_auth_role(username: str, db_role: UserRoleEnum) -> str:
    if is_super_moderator_username(username):
        return SUPER_MODERATOR_ROLE
    return db_role.value
