from datetime import datetime
from typing import Type

from fastapi import Form
from inspect import Parameter, signature

from pydantic import BaseModel, Field

from app.schemas.database import (
    AppTheme,
    ModerationStatus,
    OrderStatus,
    PaymentMethod,
    DeliveryMethod,
    UserRoleEnum,
)


# class FormBaseModel(BaseModel):
#     @classmethod
#     def as_form(cls: Type["FormBaseModel"]):
#         new_params = []

#         for field_name, model_field in cls.model_fields.items():
#             field_info = model_field

#             default = (
#                 Form(...)
#                 if field_info.is_required()
#                 else Form(field_info.default)
#             )

#             new_params.append(
#                 Parameter(
#                     field_name,
#                     Parameter.POSITIONAL_ONLY,
#                     default=default,
#                     annotation=field_info.annotation,
#                 )
#             )

#         async def _as_form(**data):
#             return cls(**data)

#         sig = signature(_as_form).replace(parameters=new_params)
#         _as_form.__signature__ = sig

#         return _as_form


class AuthorResponse(BaseModel):
    id: str
    name: str
    avatarImage: str | None
    bannerImage: str | None
    description: str | None


class UserSettingsResponse(BaseModel):
    id: int
    user_id: int
    theme: AppTheme
    ava_path: str | None


class SellerCardResponse(BaseModel):
    id: str
    name: str
    desc: str
    bannerImage: str | None
    avatarImage: str | None
    moderationStatus: ModerationStatus = ModerationStatus.APPROVED
    createdAt: datetime | None = None


class AuthorBrandModerationResponse(BaseModel):
    id: str
    createdAt: datetime
    actionType: str
    status: ModerationStatus
    title: str
    details: list[str]
    moderatorComment: str | None = None


class AuthorDashboardResponse(BaseModel):
    seller_card: SellerCardResponse | None = None
    products_count: int = 0
    stock_total: int = 0
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0


class ProductCreateRequest(BaseModel):
    name: str
    price: int
    description: str
    authorId: str
    stockCount: int


class FandomResponse(BaseModel):
    slug: str
    title: str


class CategoryResponse(BaseModel):
    slug: str
    title: str


class SubcategoryResponse(BaseModel):
    slug: str
    title: str
    categorySlug: str
    authorId: str


class SubcategoryCreateRequest(BaseModel):
    title: str
    slug: str


class FandomCreateRequest(BaseModel):
    title: str
    slug: str


class ProductResponse(BaseModel):
    id: str
    name: str
    price: int
    description: str
    images: list[str]
    authorId: str
    stockCount: int
    categorySlug: str | None = None
    subcategorySlug: str | None = None
    fandomSlug: str | None = None


class SellerProductResponse(ProductResponse):
    moderationStatus: ModerationStatus
    createdAt: datetime
    moderatorComment: str | None = None


class ProductFacetCountItem(BaseModel):
    slug: str
    count: int


class ProductFacetsResponse(BaseModel):
    total: int
    items: list[ProductFacetCountItem]


class ProductsPageResponse(BaseModel):
    items: list[ProductResponse]
    nextCursorId: str | None
    hasMore: bool


class ProductBulkRequest(BaseModel):
    ids: list[str]


class InventoryResponse(BaseModel):
    id: int
    product_id: int
    quantity: int


class ProductImageResponse(BaseModel):
    id: int
    product_id: int
    image_url: str


class ProductAlternativeResponse(BaseModel):
    id: int
    product_id: int
    alt_product_id: int


class ProductModerationResponse(BaseModel):
    id: int
    product_id: int
    moderator_id: int
    status: ModerationStatus
    comment: str
    created_at: datetime
    updated_at: datetime


class ModerationFieldDiffResponse(BaseModel):
    label: str
    before: str
    after: str
    beforeImageUrl: str | None = None
    afterImageUrl: str | None = None


class ModerationProposalResponse(BaseModel):
    id: str
    createdAt: datetime
    title: str
    type: str
    status: ModerationStatus
    submittedBy: str
    moderatedBy: str | None = None
    moderationComment: str | None = None
    previewImageUrl: str | None = None
    previewBannerUrl: str | None = None
    previewAvatarUrl: str | None = None
    changes: list[ModerationFieldDiffResponse]


class ModerationDecisionRequest(BaseModel):
    status: ModerationStatus
    comment: str | None = None


class ModerationEditResponse(BaseModel):
    kind: str
    proposal: ModerationProposalResponse
    product: SellerProductResponse | None = None
    brandName: str | None = None
    brandDescription: str | None = None
    avatarImage: str | None = None
    bannerImage: str | None = None
    actionType: str | None = None


class CartItemResponse(BaseModel):
    product_id: str
    quantity: int


class CartResponse(BaseModel):
    items: list[CartItemResponse]


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    status: OrderStatus


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    price_at_time: int


class OrderLineItemResponse(BaseModel):
    product_id: int
    name: str
    price_at_time: int
    line_total: int
    image: str | None
    quantity: int


class UserOrderResponse(BaseModel):
    id: int
    status: OrderStatus
    payment_method: PaymentMethod
    delivery_method: DeliveryMethod
    items_total: int
    delivery_cost: int
    total: int
    created_at: datetime
    items: list[OrderLineItemResponse]


class OrdersListResponse(BaseModel):
    items: list[UserOrderResponse]


class ReviewResponse(BaseModel):
    id: int
    order_item_id: int
    body: str
    rating: int


class MessageResponse(BaseModel):
    detail: str


class AdvertBannerResponse(BaseModel):
    id: int
    image: str
    href: str
    title: str


class UserProfileUpdateRequest(BaseModel):
    full_name: str | None
    email: str | None
    phone: str | None


class UserProfileResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    email: str | None
    phone: str | None


class MeResponse(UserProfileResponse):
    role: str


class SuperAdminUserResponse(BaseModel):
    id: int
    username: str
    role: UserRoleEnum
    full_name: str | None
    email: str | None
    phone: str | None
    is_super_moderator: bool = False


class SuperAdminAssignRoleRequest(BaseModel):
    role: UserRoleEnum


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: UserRoleEnum


class CartAddRequest(BaseModel):
    product_id: int
    quantity: int


class OrderCreateItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)


class OrderCreateRequest(BaseModel):
    payment_method: PaymentMethod
    delivery_method: DeliveryMethod
    delivery_cost: int = Field(default=0, ge=0)
    items: list[OrderCreateItemRequest] = Field(..., min_length=1)


class FavouriteProductRequest(BaseModel):
    product_id: str
    liked: bool


class FavouriteAuthorRequest(BaseModel):
    author_id: str
    liked: bool


class FavouriteProductItemResponse(BaseModel):
    product_id: str
    created_at: datetime


class FavouriteProductsResponse(BaseModel):
    items: list[FavouriteProductItemResponse]


class FavouriteAuthorItemResponse(BaseModel):
    author_id: str
    created_at: datetime


class FavouriteAuthorsResponse(BaseModel):
    items: list[FavouriteAuthorItemResponse]
