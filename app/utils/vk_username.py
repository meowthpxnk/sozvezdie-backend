import random
import re

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.specs.user import UserSpec
from app.repositories.user import UserRepository
from app.utils.slug import translit_to_slug

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
_MAX_ATTEMPTS = 5


def _normalize_username_base(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if len(normalized) < 3:
        normalized = f"user_{normalized}" if normalized else "user"
    return normalized[:32]


def _base_from_names(first_name: str, last_name: str) -> str:
    first = translit_to_slug(first_name).replace("-", "_")
    last = translit_to_slug(last_name).replace("-", "_")
    parts = [part for part in (first, last) if part]
    if not parts:
        return "vk_user"
    return _normalize_username_base("_".join(parts))


async def allocate_username(
    session: AsyncSession,
    *,
    screen_name: str | None,
    first_name: str,
    last_name: str,
) -> str:
    if screen_name:
        base = _normalize_username_base(screen_name)
    else:
        base = _base_from_names(first_name, last_name)

    repo = UserRepository(session)

    for attempt in range(_MAX_ATTEMPTS):
        candidate = base if attempt == 0 else f"{base}_{random.randint(1000, 9999)}"
        candidate = candidate[:32]
        if not _USERNAME_RE.fullmatch(candidate):
            continue
        existing = await repo.get_user(UserSpec(username=candidate))
        if existing is None:
            return candidate

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Could not allocate username",
    )
