"""add yookassa payment id to order

Revision ID: m8n9o0p1q2r3
Revises: l7h8i9j0k1l2
Create Date: 2026-06-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m8n9o0p1q2r3"
down_revision: Union[str, None] = "l7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order",
        sa.Column("yookassa_payment_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order", "yookassa_payment_id")
