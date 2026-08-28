import logging
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, status, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from app.api.dependencies import (
    DatabaseDepends,
    BearerAuthDepends,
    AuthAPIDepends,
)

from app.core.super_moderator import resolve_auth_role
from app.core.blocked_1c import is_user_blocked_without_1c
from app.schemas.api.responses import (
    EmailVerificationResponse,
    EmailVerifiedResponse,
    MeResponse,
)
from app.exceptions.security import WrongSecret
from app.schemas.schemas import (
    ChangePasswordForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    SendEmailVerificationForm,
    UserCreateForm,
    VerifyEmailCodeForm,
)
from app.schemas.vk import VkAuthoriseRequest
from app.services import UserService
from app.services.email_otp import EmailOtpService
from app.services.vk_auth import VkAuthService

logger = logging.getLogger("app")


class LoginRequest(BaseModel):
    username: str
    password: str


class UsernameAvailableResponse(BaseModel):
    available: bool


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
    )
    token = request.cookies.get("Refresh-Token")
    logger.info(
        "POST /refresh-session url_path=%s cookie_path=%s cookie_names=%s "
        "refresh_token=%s",
        request.url.path,
        auth_api.refresh_cookie_path(),
        list(request.cookies.keys()),
        "present" if token else "missing",
    )
    if not token:
        auth_api.clear_refresh_token_cookie(response)
        raise BAD_TOKEN

    try:
        access_token = await auth_api.refresh_session(token, response=response)
    except ValueError:
        auth_api.clear_refresh_token_cookie(response)
        raise BAD_TOKEN from None
    except Exception:
        logger.exception("POST /refresh-session failed")
        auth_api.clear_refresh_token_cookie(response)
        raise BAD_TOKEN from None

    return {"Access-Token": access_token}


@router.get("/username-available", response_model=UsernameAvailableResponse)
async def username_available(
    db_session: DatabaseDepends,
    username: str = Query(..., min_length=1, max_length=32),
):
    normalized = username.strip().lower()
    if not normalized:
        return UsernameAvailableResponse(available=False)
    user = await UserService(db_session).get_user(normalized)
    return UsernameAvailableResponse(available=user is None)


@router.post("/create-user")
async def create_user(
    data: UserCreateForm,
    db_session: DatabaseDepends,
):
    try:
        user = await UserService(db_session).create_user(data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except IntegrityError as error:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Это имя пользователя уже занято",
        ) from error

    try:
        await EmailOtpService(db_session).send_verification_code(user)
    except Exception:
        logger.exception(
            "Failed to send verification email after registration"
        )


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
        last_name=user.last_name,
        first_name=user.first_name,
        patronymic=user.patronymic,
        email=user.email,
        phone=user.phone,
        one_c_author_id=user.one_c_author_id,
        is_blocked_without_1c=is_user_blocked_without_1c(
            role=user.role,
            one_c_author_id=user.one_c_author_id,
        ),
        age_confirmed=bool(user.age_confirmed),
        email_verified=bool(user.email_verified),
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


@router.post("/email/send-verification-code")
async def send_email_verification_code(
    token: BearerAuthDepends,
    db_session: DatabaseDepends,
    data: SendEmailVerificationForm,
) -> EmailVerificationResponse:
    user = await UserService(db_session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    email = await EmailOtpService(db_session).send_verification_code(
        user,
        data.email,
        resend=data.resend,
    )
    return EmailVerificationResponse(email=email, email_verified=False)


@router.post("/email/verify-code")
async def verify_email_code(
    token: BearerAuthDepends,
    db_session: DatabaseDepends,
    data: VerifyEmailCodeForm,
) -> EmailVerifiedResponse:
    user = await UserService(db_session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    verified = await EmailOtpService(db_session).confirm_verification_code(
        user,
        data.code,
    )
    return EmailVerifiedResponse(
        email=verified.email,
        email_verified=True,
    )


@router.get("/email/verify")
async def verify_email_by_link(
    db_session: DatabaseDepends,
    uid: int = Query(..., ge=1),
    code: str = Query(..., min_length=4, max_length=12),
) -> EmailVerifiedResponse:
    user = await UserService(db_session).get_user_by_id(uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверная или устаревшая ссылка",
        )
    verified = await EmailOtpService(db_session).confirm_verification_code(
        user,
        code,
    )
    return EmailVerifiedResponse(
        email=verified.email,
        email_verified=True,
    )


@router.post("/password/forgot")
async def forgot_password(
    data: ForgotPasswordForm,
    db_session: DatabaseDepends,
) -> dict[str, str]:
    try:
        await EmailOtpService(db_session).send_password_reset_code(data.email)
    except HTTPException as error:
        if error.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        if error.status_code >= 500:
            logger.exception("Failed to send password reset email")
    except Exception:
        logger.exception("Failed to send password reset email")
    return {
        "detail": (
            "Если аккаунт с такой почтой существует, "
            "мы отправили ссылку для смены пароля. "
            "Если письма нет во входящих, проверьте папку «Спам»"
        )
    }


@router.post("/password/change-request")
async def request_password_change(
    token: BearerAuthDepends,
    db_session: DatabaseDepends,
) -> dict[str, str]:
    user = await UserService(db_session).get_user(token.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    email = await EmailOtpService(db_session).send_password_reset_for_user(user)
    return {
        "detail": (
            f"Мы отправили ссылку на {email}. "
            "Если письма нет во входящих, проверьте папку «Спам»"
        ),
        "email": email,
    }


@router.post("/password/reset")
async def reset_password(
    data: ResetPasswordForm,
    db_session: DatabaseDepends,
    auth_api: AuthAPIDepends,
    response: Response,
) -> dict[str, str]:
    user = await EmailOtpService(db_session).reset_password(
        user_id=data.uid,
        code=data.code,
        new_password=data.new_password,
    )
    await auth_api.revoke_all_sessions(user.username)
    access_token = await auth_api.issue_session(user, response)
    return {"Access-Token": access_token}


@router.patch("/logout")
async def logout(
    token: BearerAuthDepends,
    auth_api: AuthAPIDepends,
):
    await auth_api.revoke_session(token.username, token.session_id)
