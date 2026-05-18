import inspect
from typing import Any, Callable, ClassVar

from fastapi import APIRouter, Depends

from app.schemas.permissions import PermissionEnum
import jwt

import datetime
import os
import redis.asyncio as redis
from app.core.super_moderator import resolve_auth_role
from app.schemas.auth import (
    TokenPayloadSchema,
    TokenDataSchema,
    JWTTokenTypeEnum,
    User,
)
from app.settings import JWTAuthSettings


from fastapi import Depends


from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession as AsyncDBSession
from app.services.user import UserService
from app.utils.security import verify_secret

import uuid


class SessionException(Exception):
    username: str
    session_id: str

    def __init__(self, username: str, session_id: str | None = None) -> None:
        self.username = username
        self.session_id = session_id
        super().__init__(
            f"Session exception for username: {username} and session_id: {session_id if session_id else 'None'}"
        )


class AuthJWTProvider:
    private_key: bytes
    public_key: bytes

    # Initialize methods

    def __init__(self, settings: JWTAuthSettings) -> None:
        self.settings = settings
        self.PUBLIC_KEY_PATH = os.path.join(
            self.settings.keys_path, "public.pem"
        )
        self.PRIVATE_KEY_PATH = os.path.join(
            self.settings.keys_path, "private.pem"
        )
        self._set_keys()

    def _set_keys(self) -> None:
        with open(self.PUBLIC_KEY_PATH, "rb") as f:
            self.public_key = f.read()
        with open(self.PRIVATE_KEY_PATH, "rb") as f:
            self.private_key = f.read()

    # JWT encoding methods

    def encode(self, payload: TokenPayloadSchema) -> tuple[str, str]:
        if not self.private_key:
            raise ValueError(
                "Not able to encode JWT tokens. Private key is not set"
            )
        now = datetime.datetime.now(datetime.UTC)
        access_token = self._encode_access_token(payload, now)
        refresh_token = self._encode_refresh_token(payload, now)
        return access_token, refresh_token

    def decode(self, token: str) -> TokenDataSchema:
        data = jwt.decode(
            token, self.public_key, algorithms=[self.settings.algorithm]
        )
        return TokenDataSchema(**data)

    # Private methods

    def _gen_exp_time(self, ttl: int, now: datetime.datetime) -> int:
        return jwt.api_jwt.timegm(
            (now + datetime.timedelta(seconds=ttl)).utctimetuple()
        )

    def _gen_payload(
        self,
        payload: TokenPayloadSchema,
        token_type: JWTTokenTypeEnum,
        ttl: int,
        now: datetime.datetime,
    ) -> TokenDataSchema:
        return TokenDataSchema(
            **payload.model_dump(),
            type=token_type,
            exp=self._gen_exp_time(ttl, now),
        )

    def _encode_token(self, payload: TokenDataSchema) -> str:
        return jwt.encode(
            payload.model_dump(mode="json"),
            key=self.private_key,
            algorithm=self.settings.algorithm,
        )

    def _encode_refresh_token(
        self, payload: TokenPayloadSchema, now: datetime.datetime
    ) -> str:
        refresh_payload = self._gen_payload(
            payload, JWTTokenTypeEnum.REFRESH, self.settings.refresh_ttl, now
        )
        return self._encode_token(refresh_payload)

    def _encode_access_token(
        self, payload: TokenPayloadSchema, now: datetime.datetime
    ) -> str:
        access_payload = self._gen_payload(
            payload, JWTTokenTypeEnum.ACCESS, self.settings.access_ttl, now
        )
        return self._encode_token(access_payload)


class NotFoundSession(SessionException):
    pass


class NotValidSession(SessionException):
    pass


class NoMaxSessions(SessionException):
    pass


class FailedRefreshSession(SessionException):
    pass


class NotValidTokenType(SessionException):
    pass


class SessionString:
    sessions_f: str = "userSession.{USERNAME}."
    current_session_f: str = sessions_f + "{SESSION_UUID}"

    username: str
    session_id: str | None

    def __init__(self, username: str, session_id: str | None = None) -> None:
        self.username = username
        self.session_id = session_id

    @classmethod
    def create(cls, username: str) -> "SessionString":
        return cls(username=username, session_id=str(uuid.uuid4()))

    @property
    def key(self) -> str:
        if self.session_id is None:
            raise ValueError("Session ID is required")

        return self.current_session_f.format(
            USERNAME=self.username, SESSION_UUID=self.session_id
        )

    @property
    def keys(self) -> list[str]:
        return self.sessions_f.format(USERNAME=self.username) + "*"


class RedisSessionRepository:
    def __init__(self, redis: redis.Redis) -> None:
        self.redis = redis

    async def get_session_token(self, session: SessionString) -> str:
        token = await self.redis.get(session.key)
        if token is None:
            raise NotFoundSession(session.username, session.session_id)
        return token

    async def validate_session(self, session: SessionString) -> None:
        try:
            await self.get_session_token(session)
        except NotFoundSession as err:
            raise NotValidSession(
                session.username, session.session_id
            ) from err

    async def get_session_keys(self, session: SessionString) -> list[str]:
        keys = await self.redis.keys(session.keys)
        return keys

    async def get_sessions(self, session: SessionString) -> list[str]:
        return [
            await self.redis.get(key)
            for key in await self.get_session_keys(session)
        ]

    async def close_session(self, session: SessionString) -> None:
        await self.validate_session(session)
        await self.redis.delete(session.key)

    async def close_sessions(
        self, session: SessionString, exclude_session_id: str = None
    ) -> None:
        keys = await self.get_session_keys(session)

        if exclude_session_id:
            exclude_session = SessionString(
                session.username, exclude_session_id
            )
            keys = list(filter(lambda key: key != exclude_session.key, keys))

        for key in keys:
            await self.redis.delete(key)

    async def set_session(
        self,
        session: SessionString,
        refresh_token: str,
        refresh_ttl: int,
    ) -> None:
        """
        Creates or update jwt cache data for user and session_id.
        """
        await self.redis.set(
            session.key,
            refresh_token,
            refresh_ttl,
        )


class RBACDependency:
    def __init__(self, permissions: list[PermissionEnum]) -> None:
        self.permissions = permissions

    def __call__(self) -> Any:
        print(f"RBACDependency: {self.permissions}")
        return self.permissions


class RBACRouter(APIRouter):
    _rbac_dependency: ClassVar[RBACDependency] = RBACDependency

    def _wrap_method(self, method: str) -> Callable:
        original_method = getattr(super(), method)

        def wrapper(
            path: str,
            *,
            permissions: list[PermissionEnum] | PermissionEnum | None = None,
            **kwargs: dict[str, Any],
        ) -> Callable[[Callable], Callable]:
            if not permissions:
                return original_method(path, **kwargs)
            dependencies = kwargs.pop("dependencies", [])
            dependencies.append(
                Depends(
                    self._rbac_dependency(
                        permissions=(
                            [permissions]
                            if isinstance(permissions, PermissionEnum)
                            else permissions
                        )
                    )
                )
            )
            kwargs["dependencies"] = dependencies

            permission_note = f"### Permissions\n"
            if isinstance(permissions, PermissionEnum):
                permissions = [permissions]
            for permission in permissions:
                permission_note += f"- {permission.value}\n"
            permission_note += "\n"

            def decorator(func: Callable) -> Callable:
                existing_description = (
                    kwargs.get("description") or inspect.getdoc(func) or ""
                )
                kwargs["description"] = (
                    f"{existing_description}\n\n{permission_note}".strip()
                    if existing_description
                    else permission_note
                )
                return original_method(path, **kwargs)(func)

            return decorator

        return wrapper

    def __init__(self, *args: list, **kwargs: dict[str, Any]):
        super().__init__(*args, **kwargs)

        for m in ["get", "post", "put", "delete", "patch", "options", "head"]:
            setattr(self, m, self._wrap_method(m))


class AuthService:

    def __init__(
        self,
        redis_session_service: RedisSessionRepository,
        jwt_service: AuthJWTProvider,
    ):
        self.redis_session_service = redis_session_service
        self.jwt_service = jwt_service

    # Session management methods

    async def create_session(
        self, data: User | TokenDataSchema
    ) -> tuple[str, str]:
        session_string, access_token, refresh_token = (
            await self._generate_session_tokens(data)
        )
        await self._save_session(session_string, refresh_token)
        return access_token, refresh_token

    async def refresh_session(self, refresh_token: str) -> tuple[str, str]:
        data = self._get_refresh_token_data(refresh_token)
        await self._validate_refresh_token(data, refresh_token)
        return await self.create_session(data)

    async def close_session(self, session: SessionString) -> None:
        await self.redis_session_service.close_session(session)

    async def close_sessions(
        self, session: SessionString, exclude_session_id: str = None
    ) -> None:
        await self.redis_session_service.close_sessions(
            session, exclude_session_id
        )

    def decode_access_token(self, access_token: str) -> TokenDataSchema:
        data = self.jwt_service.decode(access_token)
        if not data.type == JWTTokenTypeEnum.ACCESS:
            raise NotValidTokenType(data.username, data.session_id)
        return data

    # Private methods

    async def _save_session(
        self, session_string: SessionString, refresh_token: str
    ) -> None:
        await self.redis_session_service.set_session(
            session_string,
            refresh_token,
            self.jwt_service.settings.refresh_ttl,
        )

    def _get_last_session(
        self, previous_sessions: list[TokenDataSchema]
    ) -> SessionString:
        previous_sessions.sort(key=lambda session: session.exp)
        session_to_close = previous_sessions[0]
        return SessionString(
            session_to_close.username, session_to_close.session_id
        )

    async def _remove_last_session(self, session: SessionString) -> None:
        previous_sessions = await self.redis_session_service.get_sessions(
            session
        )
        total_sessions = len(previous_sessions)

        if total_sessions < self.jwt_service.settings.max_user_sessions:
            raise NoMaxSessions(session.username)

        previous_sessions = [
            self.jwt_service.decode(session) for session in previous_sessions
        ]
        session_to_close = self._get_last_session(previous_sessions)
        await self.redis_session_service.close_session(session_to_close)

    async def _generate_session_tokens(
        self, data: User | TokenDataSchema
    ) -> tuple[SessionString, str, str]:
        if isinstance(data, TokenDataSchema):
            session_string = SessionString(data.username, data.session_id)
        elif isinstance(data, User):
            try:
                await self._remove_last_session(SessionString(data.username))
            except NoMaxSessions:
                pass
            session_string = SessionString.create(data.username)
        else:
            raise ValueError("Invalid user type")

        access_token, refresh_token = self.jwt_service.encode(
            payload=TokenPayloadSchema(
                username=session_string.username,
                session_id=session_string.session_id,
                role=data.role,
            )
        )

        return session_string, access_token, refresh_token

    # Refresh token methods

    async def _validate_refresh_token(
        self, refresh_token: TokenDataSchema, refresh_token_str: str
    ) -> None:
        session_token = await self.redis_session_service.get_session_token(
            SessionString(refresh_token.username, refresh_token.session_id)
        )
        if session_token.decode("utf-8") != refresh_token_str:
            raise FailedRefreshSession(
                refresh_token.username, refresh_token.session_id
            )

    def _get_refresh_token_data(self, refresh_token: str) -> TokenDataSchema:
        data = self.jwt_service.decode(refresh_token)
        if not data.type == JWTTokenTypeEnum.REFRESH:
            raise NotValidTokenType(data.username, data.session_id)
        return data


class AuthAPI:
    def __init__(
        self, redis_client: redis.Redis, settings: JWTAuthSettings
    ) -> None:
        redis_session_repository = RedisSessionRepository(redis_client)
        jwt_provider = AuthJWTProvider(settings)
        auth_service = AuthService(redis_session_repository, jwt_provider)
        self.settings = settings
        self.auth_service = auth_service

    async def revoke_session(self, username: str, session_id: str) -> None:
        await self.auth_service.close_session(
            SessionString(username, session_id)
        )

    async def refresh_session(
        self, refresh_token: str, response: Response
    ) -> str:
        access_token, refresh_token = await self.auth_service.refresh_session(
            refresh_token
        )
        self._set_refresh_token_cookie(refresh_token, response)
        return access_token

    def decode_access_token(self, access_token: str) -> TokenDataSchema:
        return self.auth_service.decode_access_token(access_token)

    async def authorize_user(
        self,
        username: str,
        password: str,
        response: Response,
        db_session: AsyncDBSession,
    ) -> str:
        user = await self._authorize_user(username, password, db_session)
        access_token, refresh_token = await self.auth_service.create_session(
            user
        )
        self._set_refresh_token_cookie(refresh_token, response)
        return access_token

    def _set_refresh_token_cookie(
        self, refresh_token: str, response: Response
    ) -> None:
        response.set_cookie(
            "Refresh-Token",
            refresh_token,
            max_age=self.settings.refresh_ttl,
            expires=self.settings.refresh_ttl,
            samesite="none",
            secure=True,
            httponly=True,
            path="/refresh-session",
        )

    async def _authorize_user(
        self, username: str, password: str, db_session: AsyncDBSession
    ) -> User:
        user_service = UserService(db_session)
        user = await user_service.get_user(username)

        # await user_service.create_user(UserCreateForm(username=username, password=password, role=UserRoleEnum.CUSTOMER))
        if not user:
            raise "User not found"
        verify_secret(password, user.password_hash)
        return User(
            username=user.username,
            role=resolve_auth_role(user.username, user.role),
        )
