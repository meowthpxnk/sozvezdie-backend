from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSettings, Cart, SellerCard
from app.schemas.database import UserRoleEnum
from app.schemas.api.responses import UserProfileUpdateRequest
from app.exceptions.security import WrongSecret
from app.schemas.schemas import (
    ChangePasswordForm,
    UserCreateForm,
    SellerCardForm,
    SellerCardUpdateForm,
    UserSettingsUpdateForm,
)
from app.utils import security
from app.utils.security import verify_secret

from app.repositories.user import UserRepository

# from app.repositories.user_settings import UserSettingsRepository
from app.repositories.specs.user import UserSpec

# from app.repositories.specs.user_settings import UserSettingsSpec
# from app.services.seller_card import SellerCardService


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)
        # self.settings_repo = UserSettingsRepository(session)
        # self.seller_card_service = SellerCardService(session)

    async def get_user(
        self, username: str, spec: UserSpec | None = None
    ) -> User | None:
        if spec is None:
            spec = UserSpec(username=username)
        return await self.repo.get_user(spec)

    async def get_user_by_id(self, user_id: int) -> User | None:
        spec = UserSpec(id=user_id)
        return await self.repo.get_user(spec)

    async def create_user(
        self,
        data: UserCreateForm,
    ) -> User:

        user = User(
            username=data.username,
            password_hash=security.hash_secret(data.password),
            role=data.role,
            full_name=data.full_name,
            email=data.email,
            phone=data.phone,
            settings=UserSettings(),
        )

        # if data.role == UserRoleEnum.CUSTOMER:
        user.cart = Cart()

        self.repo.add(user)

        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def change_password(
        self,
        username: str,
        data: ChangePasswordForm,
    ) -> None:
        user = await self.get_user(username)
        if user is None:
            raise ValueError("User not found")

        if data.current_password == data.new_password:
            raise ValueError("New password must differ from current password")

        try:
            verify_secret(data.current_password, user.password_hash)
        except WrongSecret:
            raise WrongSecret("Current password is incorrect") from None

        await self.repo.update_password_hash(
            user,
            security.hash_secret(data.new_password),
        )
        await self.session.commit()

    async def update_user_profile(
        self,
        username: str,
        data: UserProfileUpdateRequest,
    ) -> User | None:
        user = await self.get_user(username)
        if user is None:
            return None

        updated = await self.repo.update_profile(
            user,
            full_name=data.full_name,
            email=data.email,
            phone=data.phone,
        )
        await self.session.commit()
        await self.session.refresh(updated)
        return updated

    async def delete_user(
        self,
        username: str,
    ) -> None:

        user = await self.get_user(username)
        if user is None:
            return
        await self.repo.delete(user)
        await self.session.commit()

    async def delete_user_by_id(self, user_id: int) -> None:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return
        await self.repo.delete(user)
        await self.session.commit()

    async def create_seller_card(
        self, user: User, data: SellerCardForm
    ) -> SellerCard:
        return await self.seller_card_service.create_for_user(user, data)

    async def update_seller_card(
        self, user_id: int, data: SellerCardUpdateForm
    ) -> SellerCard:
        return await self.seller_card_service.update_for_user(user_id, data)

    # async def get_user_settings(self, user_id: int) -> UserSettings | None:
    #     return await self.settings_repo.get_by_spec(UserSettingsSpec(user_id=user_id))

    async def update_user_settings(
        self, user_id: int, data: UserSettingsUpdateForm
    ) -> UserSettings:
        settings = await self.get_user_settings(user_id)
        if settings is None:
            raise ValueError("User settings not found")
        if data.theme is not None:
            settings.theme = data.theme
        if data.ava_path is not None:
            settings.ava_path = data.ava_path
        await self.session.commit()
        await self.session.refresh(settings)
        return settings
