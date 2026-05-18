import asyncio
import logging
import logging.config

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from app import models
from app.database import Base
from app.settings import Settings
from app.utils.files import read_yaml

load_dotenv()
settings = Settings()

logging.config.dictConfig(read_yaml(settings.logging.config_path))
config = context.config

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=str(settings.database.uri),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using asyncpg."""
    connectable = create_async_engine(
        str(settings.database.uri), pool_pre_ping=True
    )

    async with connectable.begin() as connection:

        def do_migrations(sync_connection):
            context.configure(
                connection=sync_connection,
                target_metadata=target_metadata,
                compare_type=True,  # Optional: compare column types
            )
            with context.begin_transaction():
                context.run_migrations()

        await connection.run_sync(do_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
