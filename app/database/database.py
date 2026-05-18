from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.settings import DatabaseSettings


class Database:
    def __init__(self, settings: DatabaseSettings):
        self.engine = create_async_engine(str(settings.uri), future=True)
        self.session = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session() as session:
            yield session
