"""add cart_fingerprint to checkout_payment

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-06-01 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o0p1q2r3s4t5"
down_revision: Union[str, None] = "n9o0p1q2r3s4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "checkout_payment",
        sa.Column("cart_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_checkout_payment_customer_fingerprint",
        "checkout_payment",
        ["customer_id", "cart_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_checkout_payment_customer_fingerprint",
        table_name="checkout_payment",
    )
    op.drop_column("checkout_payment", "cart_fingerprint")
