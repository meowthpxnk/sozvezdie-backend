"""add seller_card is_disabled

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-13 22:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE seller_card
            ADD COLUMN IF NOT EXISTS is_disabled BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE seller_card
            SET is_disabled = TRUE
            FROM "user"
            WHERE seller_card.user_id = "user".id
              AND "user".role::text <> 'SELLER'
              AND seller_card.is_disabled = FALSE
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE seller_card DROP COLUMN IF EXISTS is_disabled"))
