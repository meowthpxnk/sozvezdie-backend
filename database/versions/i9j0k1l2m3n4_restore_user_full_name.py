"""restore user.full_name for compatibility with running api

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-08-14 21:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS last_name VARCHAR
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS first_name VARCHAR
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS patronymic VARCHAR
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS full_name VARCHAR
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET full_name = last_name
            WHERE full_name IS NULL
              AND last_name IS NOT NULL
              AND last_name <> ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET last_name = full_name
            WHERE (last_name IS NULL OR last_name = '')
              AND full_name IS NOT NULL
              AND full_name <> ''
            """
        )
    )


def downgrade() -> None:
    pass
