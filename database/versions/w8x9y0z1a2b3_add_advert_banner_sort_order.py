"""add advert banner sort_order

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-06-22 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "advert_banner",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        UPDATE advert_banner AS banner
        SET sort_order = ranked.position
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id DESC) - 1 AS position
            FROM advert_banner
        ) AS ranked
        WHERE banner.id = ranked.id
        """
    )
    op.alter_column("advert_banner", "sort_order", server_default=None)


def downgrade() -> None:
    op.drop_column("advert_banner", "sort_order")
