from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.database import UserRoleEnum

from .specs.user import UserSpec


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, spec: UserSpec):
        if spec.id is None and spec.username is None:
            raise ValueError("UserSpec requires id or username")

        stmt = select(User)
        if spec.id is not None:
            stmt = stmt.where(User.id == spec.id)
        if spec.username is not None:
            stmt = stmt.where(User.username == spec.username)

        options = []

        if spec.include_settings:
            options.append(selectinload(User.settings))

        if spec.include_orders:
            options.append(selectinload(User.orders))

        if spec.include_seller_card:
            options.append(selectinload(User.seller_card))

        if spec.include_cart:
            options.append(selectinload(User.cart))

        if options:
            stmt = stmt.options(*options)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

    async def update_profile(
        self,
        user: User,
        *,
        full_name: str | None,
        email: str | None,
        phone: str | None,
    ) -> User:
        user.full_name = full_name
        user.email = email
        user.phone = phone
        await self.session.flush()
        return user

    async def update_password_hash(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        await self.session.flush()
        return user

    async def update_role(self, user: User, role: UserRoleEnum) -> User:
        user.role = role
        await self.session.flush()
        return user

    async def list_users(
        self,
        *,
        search: str | None = None,
        limit: int = 50,
    ) -> list[User]:
        stmt = select(User).order_by(User.id.desc()).limit(limit)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    User.username.ilike(pattern),
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
