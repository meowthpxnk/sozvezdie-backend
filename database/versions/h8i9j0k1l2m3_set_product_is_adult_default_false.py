"""set existing product is_adult to false

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-08-14 21:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
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
    op.execute(
        sa.text(
            """
            ALTER TABLE product
            ALTER COLUMN is_adult SET DEFAULT FALSE
            """
        )
    )
    op.execute(sa.text("UPDATE product SET is_adult = FALSE"))


def downgrade() -> None:
    pass
