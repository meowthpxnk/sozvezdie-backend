"""add order payment and delivery fields

Revision ID: d8f1a2b3c4e5
Revises: c4a7e2f91b03
Create Date: 2026-05-17 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8f1a2b3c4e5"
down_revision: Union[str, None] = "c4a7e2f91b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

payment_method_enum = sa.Enum(
    "CARD_ONLINE",
    "ON_RECEIPT",
    name="paymentmethod",
)
delivery_method_enum = sa.Enum(
    "COURIER",
    "PICKUP_POINT",
    "POST",
    name="deliverymethod",
)


def upgrade() -> None:
    payment_method_enum.create(op.get_bind(), checkfirst=True)
    delivery_method_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "order",
        sa.Column(
            "payment_method",
            payment_method_enum,
            nullable=False,
            server_default="CARD_ONLINE",
        ),
    )
    op.add_column(
        "order",
        sa.Column(
            "delivery_method",
            delivery_method_enum,
            nullable=False,
            server_default="COURIER",
        ),
    )
    op.add_column(
        "order",
        sa.Column(
            "delivery_cost",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.alter_column("order", "payment_method", server_default=None)
    op.alter_column("order", "delivery_method", server_default=None)
    op.alter_column("order", "delivery_cost", server_default=None)


def downgrade() -> None:
    op.drop_column("order", "delivery_cost")
    op.drop_column("order", "delivery_method")
    op.drop_column("order", "payment_method")
    delivery_method_enum.drop(op.get_bind(), checkfirst=True)
    payment_method_enum.drop(op.get_bind(), checkfirst=True)
