import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app")


async def ensure_adult_content_columns(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            ALTER TABLE product
            ADD COLUMN IF NOT EXISTS is_adult BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )
    await session.execute(
        text(
            """
            ALTER TABLE product
            ALTER COLUMN is_adult SET DEFAULT FALSE
            """
        )
    )
    await session.execute(
        text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS last_name VARCHAR
            """
        )
    )
    await session.execute(
        text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS first_name VARCHAR
            """
        )
    )
    await session.execute(
        text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS patronymic VARCHAR
            """
        )
    )
    await session.execute(
        text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS full_name VARCHAR
            """
        )
    )
    await session.execute(
        text(
            """
            UPDATE "user"
            SET full_name = last_name
            WHERE full_name IS NULL
              AND last_name IS NOT NULL
              AND last_name <> ''
            """
        )
    )
    await session.execute(
        text(
            """
            UPDATE "user"
            SET last_name = full_name
            WHERE (last_name IS NULL OR last_name = '')
              AND full_name IS NOT NULL
              AND full_name <> ''
            """
        )
    )
    await session.execute(
        text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS age_confirmed BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )
    await session.commit()
    logger.info("Adult content and user name columns are present")
