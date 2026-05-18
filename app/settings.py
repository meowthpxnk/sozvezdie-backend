from pydantic import Field, PostgresDsn, RedisDsn, ValidationError
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings

from app.utils.exceptions import prepare_settings_errors_message


class LoggingSettings(BaseSettings):
    config_path: str = Field(
        "config/logging.yaml",
        alias="LOGGING_CONFIG_PATH",
    )


class ApiSettings(BaseSettings):
    host: str = Field(
        "localhost",
        alias="API_HOST",
    )
    port: int = Field(
        2000,
        alias="API_PORT",
    )
    cors_path: str = Field(
        "config/cors.yaml",
        alias="API_CORS_PATH",
    )


class DatabaseSettings(BaseSettings):
    uri: PostgresDsn = Field(
        alias="DATABASE_URI",
    )


class JWTAuthSettings(BaseSettings):
    access_ttl: int = Field(
        15,
        alias="ACCESS_TOKEN_TTL",
    )
    refresh_ttl: int = Field(
        1209600,
        alias="REFRESH_TOKEN_TTL",
    )
    max_user_sessions: int = Field(
        5,
        alias="MAX_USER_SESSIONS",
    )

    keys_path: str = Field(
        "jwt_keys",
        alias="JWT_KEYS_PATH",
    )
    algorithm: str = "RS256"


class RedisSettings(BaseSettings):
    uri: RedisDsn = Field(
        alias="REDIS_URI",
    )
    password: str | None = Field(
        None,
        alias="REDIS_PASSWORD",
    )


class MinioSettings(BaseSettings):
    minio_uri: str = Field(
        alias="MINIO_URI",
    )


class Settings:
    api: ApiSettings
    database: DatabaseSettings
    redis: RedisSettings
    jwt_auth: JWTAuthSettings
    logging: LoggingSettings
    minio: MinioSettings

    def __init__(self):
        errors: list[ErrorDetails] = []

        for name, cls in self.__annotations__.items():
            try:
                setattr(self, name, cls())
            except ValidationError as err:
                [errors.append(e) for e in err.errors()]

        if errors:
            raise RuntimeError(prepare_settings_errors_message(errors))
