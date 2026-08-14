from sqlalchemy.ext.asyncio import AsyncSession

from app.core.super_moderator import is_super_moderator_username
from app.integrations.one_c import OneCUnavailable, delete_author
from app.models import User
from app.repositories.author_invite import normalize_one_c_author_id
from app.repositories.specs.user import UserSpec
from app.repositories.user import UserRepository
from app.schemas.api.responses import SuperAdminUserResponse
from app.schemas.database import UserRoleEnum
from app.services.author_invite import AuthorInviteService, OneCAuthorIdTaken
from app.services.seller_card import SellerCardService


ASSIGNABLE_ROLES = {
    UserRoleEnum.CUSTOMER,
    UserRoleEnum.SELLER,
    UserRoleEnum.MODERATOR,
}


class SuperAdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.invite_service = AuthorInviteService(session)
        self.seller_card_service = SellerCardService(session)

    def _to_response(
        self, user: User, *, one_c_warning: str | None = None
    ) -> SuperAdminUserResponse:
        seller_card = user.seller_card
        return SuperAdminUserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            is_super_moderator=is_super_moderator_username(user.username),
            one_c_author_id=user.one_c_author_id,
            one_c_warning=one_c_warning,
            has_seller_card=seller_card is not None,
            seller_card_disabled=bool(
                seller_card is not None and seller_card.is_disabled
            ),
        )

    async def list_users(
        self, *, search: str | None = None, limit: int = 50
    ) -> list[SuperAdminUserResponse]:
        users = await self.user_repo.list_users(search=search, limit=limit)
        return [self._to_response(user) for user in users]

    async def _get_editable_user(self, user_id: int) -> User:
        user = await self.user_repo.get_user(
            UserSpec(id=user_id, include_seller_card=True)
        )
        if user is None:
            raise ValueError("User not found")
        if is_super_moderator_username(user.username):
            raise ValueError("Cannot change role for super moderator account")
        return user

    async def _reload_user(self, user_id: int) -> User:
        user = await self.user_repo.get_user(
            UserSpec(id=user_id, include_seller_card=True)
        )
        if user is None:
            raise ValueError("User not found")
        return user

    async def _try_delete_from_1c(self, user: User) -> str | None:
        one_c_id = normalize_one_c_author_id(user.one_c_author_id)
        if one_c_id is None:
            return None
        warning = None
        try:
            await delete_author(one_c_id)
        except OneCUnavailable as error:
            warning = error.message
        user.one_c_author_id = None
        return warning

    async def assign_role(
        self,
        user_id: int,
        role: UserRoleEnum,
        *,
        one_c_author_id: str | None = None,
        delete_from_1c: bool = False,
        delete_shop: bool = False,
    ) -> SuperAdminUserResponse:
        if role not in ASSIGNABLE_ROLES:
            raise ValueError("Role can only be CUSTOMER, SELLER or MODERATOR")

        user = await self._get_editable_user(user_id)
        previous_role = user.role
        one_c_warning: str | None = None

        if role == UserRoleEnum.SELLER:
            resolved_id = normalize_one_c_author_id(
                one_c_author_id
            ) or normalize_one_c_author_id(user.one_c_author_id)
            if resolved_id is None:
                raise ValueError("Для роли продавца нужен ID 1C")
            await self.invite_service.assert_one_c_id_available(
                resolved_id,
                exclude_user_id=user.id,
            )
            user.one_c_author_id = resolved_id
            if user.seller_card is not None:
                await self.seller_card_service.enable_shop(user.seller_card)

        if previous_role == UserRoleEnum.SELLER and role != UserRoleEnum.SELLER:
            if delete_from_1c:
                one_c_warning = await self._try_delete_from_1c(user)
            if delete_shop:
                if user.seller_card is not None:
                    await self.seller_card_service.delete_shop_for_user(user.id)
            elif user.seller_card is not None:
                await self.seller_card_service.disable_shop(user.seller_card)

        updated = await self.user_repo.update_role(user, role)
        await self.session.commit()
        refreshed = await self._reload_user(updated.id)
        return self._to_response(refreshed, one_c_warning=one_c_warning)

    async def assign_one_c_author_id(
        self, user_id: int, one_c_author_id: str
    ) -> SuperAdminUserResponse:
        user = await self._get_editable_user(user_id)
        if user.role != UserRoleEnum.SELLER:
            raise ValueError("ID 1C можно присвоить только продавцу")

        normalized = await self.invite_service.assert_one_c_id_available(
            one_c_author_id,
            exclude_user_id=user.id,
        )
        user.one_c_author_id = normalized
        await self.session.flush()
        await self.session.commit()
        refreshed = await self._reload_user(user.id)
        return self._to_response(refreshed)

    async def delete_from_1c(self, user_id: int) -> SuperAdminUserResponse:
        user = await self._get_editable_user(user_id)
        if normalize_one_c_author_id(user.one_c_author_id) is None:
            raise ValueError("У пользователя нет ID 1C")
        one_c_warning = await self._try_delete_from_1c(user)
        await self.session.commit()
        refreshed = await self._reload_user(user.id)
        return self._to_response(refreshed, one_c_warning=one_c_warning)

    async def delete_shop(self, user_id: int) -> SuperAdminUserResponse:
        user = await self._get_editable_user(user_id)
        await self.seller_card_service.delete_shop_for_user(user.id)
        await self.session.commit()
        refreshed = await self._reload_user(user.id)
        return self._to_response(refreshed)

    async def create_author_invite(self, one_c_author_id: str):
        try:
            return await self.invite_service.create_invite(one_c_author_id)
        except OneCAuthorIdTaken as error:
            raise ValueError(str(error)) from error
