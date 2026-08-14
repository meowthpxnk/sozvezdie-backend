"""split user full_name into last_name, first_name, patronymic

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-14 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
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
            UPDATE "user"
            SET last_name = full_name
            WHERE full_name IS NOT NULL
              AND (last_name IS NULL OR last_name = '')
            """
        )
    )
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS full_name'))


def downgrade() -> None:
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
            SET full_name = NULLIF(
                TRIM(CONCAT_WS(' ', last_name, first_name, patronymic)),
                ''
            )
            """
        )
    )
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS last_name'))
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS first_name'))
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS patronymic'))
