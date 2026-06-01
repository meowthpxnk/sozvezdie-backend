"""add checkout_payment for pay-before-order flow

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-06-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "n9o0p1q2r3s4"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

checkout_payment_status = sa.Enum(
    "PENDING",
    "FULFILLED",
    "CANCELED",
    name="checkoutpaymentstatus",
)


def upgrade() -> None:
    checkout_payment_status.create(op.get_bind(), checkfirst=True)
    status_type = postgresql.ENUM(
        "PENDING",
        "FULFILLED",
        "CANCELED",
        name="checkoutpaymentstatus",
        create_type=False,
    )
    op.create_table(
        "checkout_payment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("yookassa_payment_id", sa.String(), nullable=False),
        sa.Column("total_kopecks", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            status_type,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("yookassa_payment_id"),
    )
    op.create_index(
        "ix_checkout_payment_customer_id",
        "checkout_payment",
        ["customer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_checkout_payment_customer_id", table_name="checkout_payment")
    op.drop_table("checkout_payment")
    checkout_payment_status.drop(op.get_bind(), checkfirst=True)
