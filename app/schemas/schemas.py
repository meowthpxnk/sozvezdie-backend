import re

from fastapi import File, UploadFile
from pydantic import BaseModel, Field, field_validator

from .database import (
    AppTheme,
    ModerationStatus,
    UserRoleEnum,
)


def validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password too short")

    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one digit")

    return v


class SellerCardForm(BaseModel):
    name: str
    desc: str


class SellerCardUpdateForm(BaseModel):
    name: str | None = None
    desc: str | None = None


class UserSettingsUpdateForm(BaseModel):
    theme: AppTheme | None = None
    ava_path: str | None = None


class UserCreateForm(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Username must be 3-32 chars, alphanumeric + underscore",
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters",
    )

    role: UserRoleEnum = Field(
        default=UserRoleEnum.CUSTOMER, description="User role"
    )

    full_name: str = Field(..., min_length=1, max_length=128)
    email: str = Field(
        ...,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    phone: str = Field(..., min_length=5, max_length=32)

    @field_validator("full_name", "phone")
    @classmethod
    def strip_text_fields(cls, v: str) -> str:
        return v.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    # 🔥 кастомная валидация пароля
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip().lower()


class ChangePasswordForm(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters",
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ProductCreateForm(BaseModel):
    name: str
    desc: str
    price: int = Field(..., ge=0)
    seller_card_id: int
    status: ModerationStatus = ModerationStatus.PENDING
    images: list[UploadFile] = File(...)
    quantity: int = Field(default=1, ge=0)
    category_slug: str | None = None
    subcategory_slug: str | None = None
    fandom_slug: str | None = None


class ProductImageSlotForm(BaseModel):
    type: str
    uuid: str | None = None


class ProductUpdateForm(BaseModel):
    name: str
    desc: str
    price: int = Field(..., ge=0)
    quantity: int = Field(default=1, ge=0)
    seller_card_id: int
    image_slots: list[ProductImageSlotForm]
    new_images: list[UploadFile] = Field(default_factory=list)
    category_slug: str | None = None
    subcategory_slug: str | None = None
    fandom_slug: str | None = None


class InventoryCreateForm(BaseModel):
    quantity: int = Field(..., ge=0)


class ProductImageCreateForm(BaseModel):
    image_url: str


class ProductAlternativeCreateForm(BaseModel):
    alt_product_id: int


class ProductModerationCreateForm(BaseModel):
    moderator_id: int
    status: ModerationStatus
    comment: str


class ReviewCreateForm(BaseModel):
    order_item_id: int
    body: str
    rating: int = Field(..., ge=1, le=5)


class CartItemCreateForm(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class AdvertBannerCreateForm(BaseModel):
    image: UploadFile = File(...)
    link: str
    text: str


class AdvertBannerUpdateForm(BaseModel):
    image: UploadFile | None = None
    link: str
    text: str


class SellerCardCreateRequest(BaseModel):
    name: str
    desc: str
    banner_image: UploadFile = File(...)
    avatar_image: UploadFile = File(...)


class SellerCardCreateForm(SellerCardCreateRequest):
    user_id: int


class SellerCardUpdateForm(BaseModel):
    name: str
    desc: str
    banner_image: UploadFile | None = None
    avatar_image: UploadFile | None = None


# class AdvertBannerUpdateForm(BaseModel):
#     image: UploadFile | None = None
#     link: str | None = None
#     text: str | None = None
