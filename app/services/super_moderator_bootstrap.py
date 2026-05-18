import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.super_moderator import get_super_moderator_credentials
from app.schemas.database import UserRoleEnum
from app.schemas.schemas import UserCreateForm
from app.services.user import UserService
from app.utils import security

logger = logging.getLogger("app")


async def ensure_super_moderator_user(session: AsyncSession) -> None:
    credentials = get_super_moderator_credentials()
    if credentials is None:
        logger.warning(
            "SUPER_MODERATOR_USERNAME or SUPER_MODERATOR_PASSWORD is not set; "
            "super moderator account was not created"
        )
        return

    username, password = credentials
    user_service = UserService(session)
    existing = await user_service.get_user(username)

    if existing is None:
        await user_service.create_user(
            UserCreateForm(
                username=username,
                password=password,
                role=UserRoleEnum.CUSTOMER,
                full_name="Super Moderator",
                email=f"{username}@super.local",
                phone="+70000000000",
            )
        )
        logger.info("Super moderator user '%s' created", username)
        return

    await user_service.repo.update_password_hash(
        existing,
        security.hash_secret(password),
    )
    await session.commit()
    logger.info("Super moderator user '%s' password synced from ENV", username)
