"""add created_at to product and favourites

Revision ID: i4d5e6f7a8b9
Revises: h3c4d5e6f7a8
Create Date: 2026-05-17 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i4d5e6f7a8b9"
down_revision: Union[str, None] = "h3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table_name in ("product", "favourite_product", "favourite_author"):
        op.add_column(
            table_name,
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )
        op.alter_column(table_name, "created_at", server_default=None)


def downgrade() -> None:
    op.drop_column("favourite_author", "created_at")
    op.drop_column("favourite_product", "created_at")
    op.drop_column("product", "created_at")
