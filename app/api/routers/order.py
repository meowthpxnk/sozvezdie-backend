from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.api.order_errors import raise_http_for_order_error
from app.schemas.api.responses import (
    CancelOrderResponse,
    CheckoutCompleteResponse,
    CheckoutPaymentInitResponse,
    OrderCreateRequest,
    OrdersListResponse,
    SyncPendingPaymentsResponse,
    UserOrderResponse,
)
from app.services.checkout_payment import CheckoutPaymentService
from app.services.order import OrderService, PaymentNotCompletedError
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
        return await OrderService(session).create_order(
            user.id, data, customer=user
        )
    except ValueError as error:
        raise_http_for_order_error(error)


@router.post("/sync-pending-payments")
async def sync_pending_payments(
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> SyncPendingPaymentsResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return await CheckoutPaymentService(session).sync_pending_payments(
        user.id, customer=user
    )


@router.post("/initiate-payment")
async def initiate_payment(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: OrderCreateRequest,
) -> CheckoutPaymentInitResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    try:
        return await CheckoutPaymentService(session).initiate_payment(
            user.id, data, customer=user
        )
    except ValueError as error:
        raise_http_for_order_error(error)


@router.post("/checkout/{checkout_id}/complete")
async def complete_checkout(
    checkout_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> CheckoutCompleteResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    try:
        return await CheckoutPaymentService(session).complete_checkout(
            checkout_id, user.id, customer=user
        )
    except PaymentNotCompletedError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except ValueError as error:
        raise_http_for_order_error(error)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> CancelOrderResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    try:
        order, cdek_result, payment_result = await OrderService(session).cancel_order(
            user_id=user.id,
            order_id=order_id,
            customer=user,
        )
        return CancelOrderResponse(
            order=order,
            cdek=cdek_result,
            payment=payment_result,
        )
    except ValueError as error:
        raise_http_for_order_error(error)
