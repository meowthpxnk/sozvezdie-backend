"""add yookassa idempotence key to checkout_payment

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-06-01 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "checkout_payment",
        sa.Column("yookassa_idempotence_key", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE checkout_payment SET yookassa_idempotence_key = gen_random_uuid()::text "
        "WHERE yookassa_idempotence_key IS NULL"
    )
    op.alter_column(
        "checkout_payment",
        "yookassa_idempotence_key",
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_checkout_payment_yookassa_idempotence_key",
        "checkout_payment",
        ["yookassa_idempotence_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_checkout_payment_yookassa_idempotence_key",
        "checkout_payment",
        type_="unique",
    )
    op.drop_column("checkout_payment", "yookassa_idempotence_key")
