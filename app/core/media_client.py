from app.media_client import MediaClient
from .settings import settings

media_client = MediaClient(settings.minio.minio_uri)
