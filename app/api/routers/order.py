from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.schemas.api.responses import OrderCreateRequest, OrdersListResponse, UserOrderResponse
from app.services.order import OrderService
from app.services.user import UserService

router = APIRouter(prefix="/order", tags=["Order"])

@router.get("")
async def get_orders(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    archive: bool = Query(default=False),
) -> OrdersListResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return await OrderService(session).get_orders_for_user(
        user.id,
        archive=archive,
    )

@router.post("")
async def create_order(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: OrderCreateRequest,
) -> UserOrderResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    try:
        return await OrderService(session).create_order(user.id, data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
