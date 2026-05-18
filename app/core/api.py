from app.api import Api
from app.api.routers import router

from .logging import LOGGING_CONFIG
from .settings import settings

api = Api(settings.api, LOGGING_CONFIG)
api._set_router(router)
