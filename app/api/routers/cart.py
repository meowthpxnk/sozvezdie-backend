from fastapi import APIRouter

from app.api.auth_routing import RBACRouter
from app.services.cart import CartService
from app.services.user import UserService
from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.schemas.api.responses import CartAddRequest, CartResponse


router = APIRouter(prefix="/cart", tags=["Cart"])


@router.put("")
async def add_to_cart(
    session: DatabaseDepends,
    token: BearerAuthDepends,
    request: CartAddRequest,
):
    username = token.username
    user = await UserService(session).get_user(username=token.username)
    user_id = user.id

    cart_item = await CartService(session).change_cart_item_quantity(
        user_id, request.product_id, request.quantity
    )


@router.get("")
async def get_cart(
    session: DatabaseDepends,
    token: BearerAuthDepends,
) -> CartResponse:
    user = await UserService(session).get_user(username=token.username)
    user_id = user.id

    return await CartService(session).get_cart(user_id)
