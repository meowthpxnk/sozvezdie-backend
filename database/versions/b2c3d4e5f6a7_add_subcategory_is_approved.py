"""add subcategory is_approved flag

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24 11:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS: api and worker both run alembic on startup.
    op.execute(
        sa.text(
            """
            ALTER TABLE subcategory
            ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT false NOT NULL
            """
        )
    )
    # Existing subcategories have already been used — treat as moderated.
    op.execute(sa.text("UPDATE subcategory SET is_approved = true"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE subcategory DROP COLUMN IF EXISTS is_approved"))
