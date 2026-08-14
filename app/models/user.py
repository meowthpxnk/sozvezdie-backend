from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.mixins import WithIDMixin
from app.schemas.database import UserRoleEnum
from app.utils.text import format_person_name

if TYPE_CHECKING:
    from . import (
        UserSettings,
        SellerCard,
        Cart,
        Review,
        Order,
        ProductModeration,
        SellerCardModeration,
        FavouriteProduct,
        FavouriteAuthor,
        UserAddress,
    )


class User(Base, WithIDMixin):
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(
        Enum(UserRoleEnum), nullable=False
    )
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    patronymic: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    one_c_author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    age_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    seller_card: Mapped["SellerCard"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    cart: Mapped["Cart"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    product_moderations: Mapped[list["ProductModeration"]] = relationship(
        back_populates="moderator",
        cascade="all, delete-orphan",
    )
    seller_card_moderations: Mapped[list["SellerCardModeration"]] = relationship(
        back_populates="moderator",
        foreign_keys="SellerCardModeration.moderator_id",
        cascade="all, delete-orphan",
    )
    favourite_products: Mapped[list["FavouriteProduct"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    favourite_authors: Mapped[list["FavouriteAuthor"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    addresses: Mapped[list["UserAddress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str | None:
        return format_person_name(self.last_name, self.first_name, self.patronymic)
