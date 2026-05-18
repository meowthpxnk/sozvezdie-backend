from app.database import Database

from .settings import settings

database = Database(settings.database)
