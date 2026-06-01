from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DatabaseDepends
from app.api.dependencies.auth import BearerAuthDepends
from app.schemas.api.delivery import (
    UserAddressCreateRequest,
    UserAddressListResponse,
    UserAddressResponse,
    UserAddressUpdateRequest,
)
from app.services.user import UserService
from app.services.user_address import UserAddressService

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.get("")
async def list_addresses(
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> UserAddressListResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await UserAddressService(session).list_addresses(user.id)


@router.post("")
async def create_address(
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: UserAddressCreateRequest,
) -> UserAddressResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await UserAddressService(session).create_address(user.id, data)


@router.put("/{address_id}")
async def update_address(
    address_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
    data: UserAddressUpdateRequest,
) -> UserAddressResponse:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        return await UserAddressService(session).update_address(
            user.id, address_id, data
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )


@router.delete("/{address_id}")
async def delete_address(
    address_id: int,
    token: BearerAuthDepends,
    session: DatabaseDepends,
) -> dict[str, str]:
    user = await UserService(session).get_user(token.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        await UserAddressService(session).delete_address(user.id, address_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    return {"detail": "deleted"}
