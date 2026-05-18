from app.api.auth_routing import AuthAPI
from . import redis_client, settings

auth_api = AuthAPI(redis_client, settings.jwt_auth)
