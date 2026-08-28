"""add user email_verified

Revision ID: a2b3c4d5e6f7
Revises: i9j0k1l2m3n4
Create Date: 2026-08-25 02:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS email_verified')
    )
