from fastapi import HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_routing import AuthAPI
from app.integrations.vk import fetch_vk_user
from app.models import Cart, User, UserSettings, VkIdMapping
from app.repositories.specs.user import UserSpec
from app.repositories.user import UserRepository
from app.repositories.vk_id_mapping import VkIdMappingRepository
from app.schemas.database import UserRoleEnum
from app.utils import security
from app.utils.random_password import generate_random_password
from app.utils.vk_username import allocate_username


class VkAuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapping_repo = VkIdMappingRepository(session)
        self.user_repo = UserRepository(session)

    async def login_or_register(
        self,
        vk_access_token: str,
        auth_api: AuthAPI,
        response: Response,
    ) -> str:
        vk_user = await fetch_vk_user(vk_access_token)

        mapping = await self.mapping_repo.get_by_vk_id(vk_user.id)
        if mapping is not None:
            user = await self.user_repo.get_user(UserSpec(id=mapping.user_id))
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            return await auth_api.authorize_vk_user(user, response)

        try:
            user = await self._create_vk_user(vk_user)
        except IntegrityError as error:
            await self.session.rollback()
            mapping = await self.mapping_repo.get_by_vk_id(vk_user.id)
            if mapping is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not create VK user mapping",
                ) from error
            user = await self.user_repo.get_user(UserSpec(id=mapping.user_id))
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                ) from error

        return await auth_api.authorize_vk_user(user, response)

    async def _create_vk_user(self, vk_user) -> User:
        username = await allocate_username(
            self.session,
            screen_name=vk_user.screen_name,
            first_name=vk_user.first_name,
            last_name=vk_user.last_name,
        )
        password = generate_random_password()
        full_name = f"{vk_user.first_name} {vk_user.last_name}".strip()

        user = User(
            username=username,
            password_hash=security.hash_secret(password),
            role=UserRoleEnum.CUSTOMER,
            full_name=full_name or None,
            email=None,
            phone=None,
            settings=UserSettings(),
        )
        user.cart = Cart()

        self.user_repo.add(user)
        await self.session.flush()

        self.mapping_repo.add(
            VkIdMapping(vk_id=vk_user.id, user_id=user.id),
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user
