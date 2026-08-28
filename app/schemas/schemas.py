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

    last_name: str = Field(..., min_length=1, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=128)
    patronymic: str | None = Field(default=None, max_length=128)
    email: str = Field(
        ...,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    phone: str = Field(..., min_length=5, max_length=32)
    author_invite: str | None = None

    @field_validator("last_name", "first_name", "phone")
    @classmethod
    def strip_text_fields(cls, v: str) -> str:
        return v.strip()

    @field_validator("patronymic")
    @classmethod
    def strip_optional_patronymic(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None

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


class SendEmailVerificationForm(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    resend: bool = True

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip().lower()
        if not stripped:
            return None
        if "@" not in stripped or "." not in stripped.split("@")[-1]:
            raise ValueError("Некорректный email")
        return stripped


class VerifyEmailCodeForm(BaseModel):
    code: str = Field(..., min_length=4, max_length=12)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        digits = "".join(ch for ch in v.strip() if ch.isdigit())
        if len(digits) != 6:
            raise ValueError("Код должен состоять из 6 цифр")
        return digits


class ForgotPasswordForm(BaseModel):
    email: str = Field(
        ...,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordForm(BaseModel):
    uid: int = Field(..., ge=1)
    code: str = Field(..., min_length=4, max_length=12)
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters",
    )

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        digits = "".join(ch for ch in v.strip() if ch.isdigit())
        if len(digits) != 6:
            raise ValueError("Код должен состоять из 6 цифр")
        return digits

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


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
    is_adult: bool = False


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
    is_adult: bool = False


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


class AdvertBannerReorderRequest(BaseModel):
    ordered_ids: list[int] = Field(min_length=1)


class FaqItemCreateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1)
    is_published: bool = False


class FaqItemUpdateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1)
    is_published: bool


class FaqItemReorderRequest(BaseModel):
    ordered_ids: list[int] = Field(min_length=1)


class SellerCardCreateRequest(BaseModel):
    name: str
    desc: str
    banner_image: UploadFile = File(...)
    avatar_image: UploadFile = File(...)


class SellerCardCreateForm(SellerCardCreateRequest):
    user_id: int
    tiktok_url: str | None = None
    telegram_channel_url: str | None = None
    vk_url: str | None = None


class SellerCardUpdateForm(BaseModel):
    name: str
    desc: str
    banner_image: UploadFile | None = None
    avatar_image: UploadFile | None = None
    tiktok_url: str | None = None
    telegram_channel_url: str | None = None
    vk_url: str | None = None


# class AdvertBannerUpdateForm(BaseModel):
#     image: UploadFile | None = None
#     link: str | None = None
#     text: str | None = None
