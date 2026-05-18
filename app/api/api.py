from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

from app.core import database
from app.schemas.api.config import CorsConfig
from app.services.super_moderator_bootstrap import ensure_super_moderator_user
from app.settings import ApiSettings
from app.utils.files import read_yaml_model

from .exceptions import default_exception_handler


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    async with database.session() as session:
        await ensure_super_moderator_user(session)
    yield


class Api:
    def __init__(self, settings: ApiSettings, log_config: dict):
        self.settings = settings
        self.api = FastAPI(docs_url=None, lifespan=app_lifespan)

        config = Config(
            self.api, settings.host, settings.port, log_config=log_config,
        )
        self.server = Server(config)

        self._set_cors()
        self._set_exception_handler()

    def _set_cors(self) -> None:
        cors_config = read_yaml_model(self.settings.cors_path, CorsConfig)
        self.api.add_middleware(CORSMiddleware, **cors_config.model_dump())

    def _set_router(self, router: APIRouter) -> None:
        self.api.include_router(router)

    def _set_exception_handler(self):
        self.api.add_exception_handler(Exception, default_exception_handler)
