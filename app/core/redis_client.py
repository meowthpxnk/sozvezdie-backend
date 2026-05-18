from redis.asyncio import Redis
from . import settings

redis_client = Redis.from_url(url=str(settings.redis.uri), password=settings.redis.password)
