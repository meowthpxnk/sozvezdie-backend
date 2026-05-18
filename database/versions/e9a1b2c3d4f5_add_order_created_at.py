"""add order created_at

Revision ID: e9a1b2c3d4f5
Revises: d8f1a2b3c4e5
Create Date: 2026-05-17 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9a1b2c3d4f5"
down_revision: Union[str, None] = "d8f1a2b3c4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.alter_column("order", "created_at", server_default=None)


def downgrade() -> None:
    op.drop_column("order", "created_at")
