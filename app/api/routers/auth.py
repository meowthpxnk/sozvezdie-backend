import logging
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi import Response, Request
from fastapi import UploadFile, File
from app.api.dependencies import (
    DatabaseDepends,
    BearerAuthDepends,
    AuthAPIDepends,
)

from app.core.super_moderator import resolve_auth_role
from app.schemas.api.responses import MeResponse
from app.exceptions.security import WrongSecret
from app.schemas.schemas import ChangePasswordForm, UserCreateForm
from app.schemas.vk import VkAuthoriseRequest
from app.services import UserService
from app.services.vk_auth import VkAuthService

logger = logging.getLogger("app")


class LoginRequest(BaseModel):
    username: str
    password: str


router = APIRouter()


@router.post("/authorisate")
async def login(
    response: Response,
    data: LoginRequest,
    auth_api: AuthAPIDepends,
    db_session: DatabaseDepends,
):
    access_token = await auth_api.authorize_user(
        data.username, data.password, response=response, db_session=db_session
    )
    return {"Access-Token": access_token}


@router.post("/authorise_vk")
async def authorise_vk(
    response: Response,
    data: VkAuthoriseRequest,
    auth_api: AuthAPIDepends,
    db_session: DatabaseDepends,
):
    logger.info(
        "POST /authorise_vk code_len=%s device_id_len=%s verifier_len=%s",
        len(data.code),
        len(data.device_id),
        len(data.code_verifier),
    )

    try:
        access_token = await VkAuthService(db_session).login_or_register(
            data,
            auth_api,
            response,
        )
    except HTTPException as exc:
        logger.warning(
            "POST /authorise_vk failed status=%s detail=%s",
            exc.status_code,
            exc.detail,
        )
        raise
    except Exception:
        logger.exception("POST /authorise_vk unexpected error")
        raise

    logger.info("POST /authorise_vk success")
    return {"Access-Token": access_token}


@router.post("/refresh-session")
async def refresh_token(
    auth_api: AuthAPIDepends, request: Request, response: Response
):
    BAD_TOKEN = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not valid refresh token.",
        headers={
            "set-cookie": "Refresh-Token=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/refresh-session"
        },
    )
    token = request.cookies.get("Refresh-Token")
    access_token = await auth_api.refresh_session(token, response=response)

    return {"Access-Token": access_token}


@router.post("/create-user")
async def create_user(
    data: UserCreateForm,
    db_session: DatabaseDepends,
):
    # TODO: remove this after testing
    await UserService(db_session).create_user(data)


@router.get("/me")
async def get_me(
    token: BearerAuthDepends,
    db_session: DatabaseDepends,
) -> MeResponse:
    user = await UserService(db_session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return MeResponse(
        id=user.id,
        username=user.username,
        role=resolve_auth_role(user.username, user.role),
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
    )


@router.patch("/change-password")
async def change_password(
    token: BearerAuthDepends,
    db_session: DatabaseDepends,
    data: ChangePasswordForm,
):
    try:
        await UserService(db_session).change_password(token.username, data)
    except WrongSecret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    return {"detail": "Password changed successfully"}


@router.patch("/logout")
async def logout(
    token: BearerAuthDepends,
    auth_api: AuthAPIDepends,
):
    await auth_api.revoke_session(token.username, token.session_id)
