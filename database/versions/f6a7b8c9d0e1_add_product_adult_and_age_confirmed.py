"""add product is_adult and user age_confirmed

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-14 20:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE product
            ADD COLUMN IF NOT EXISTS is_adult BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )
    op.execute(sa.text("UPDATE product SET is_adult = FALSE"))
    op.execute(
        sa.text(
            """
            ALTER TABLE product
            ALTER COLUMN is_adult SET DEFAULT FALSE
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS age_confirmed BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE product DROP COLUMN IF EXISTS is_adult"))
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS age_confirmed'))
