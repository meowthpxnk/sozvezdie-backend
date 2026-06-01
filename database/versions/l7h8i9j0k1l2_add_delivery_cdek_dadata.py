"""add delivery cdek dadata support

Revision ID: l7h8i9j0k1l2
Revises: k6g7h8i9j0k1
Create Date: 2026-05-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l7h8i9j0k1l2"
down_revision: Union[str, None] = "k6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE deliverymethod ADD VALUE IF NOT EXISTS 'SELF_PICKUP'")

    op.create_table(
        "user_address",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("formatted_address", sa.Text(), nullable=False),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("street", sa.String(), nullable=True),
        sa.Column("house", sa.String(), nullable=True),
        sa.Column("flat", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("cdek_city_code", sa.Integer(), nullable=True),
        sa.Column("dadata_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("order", sa.Column("delivery_date", sa.Date(), nullable=True))
    op.add_column("order", sa.Column("delivery_address_text", sa.Text(), nullable=True))
    op.add_column("order", sa.Column("delivery_lat", sa.Float(), nullable=True))
    op.add_column("order", sa.Column("delivery_lon", sa.Float(), nullable=True))
    op.add_column("order", sa.Column("delivery_flat", sa.String(), nullable=True))
    op.add_column("order", sa.Column("cdek_pvz_code", sa.String(), nullable=True))
    op.add_column("order", sa.Column("cdek_pvz_address", sa.Text(), nullable=True))
    op.add_column("order", sa.Column("cdek_order_uuid", sa.String(), nullable=True))
    op.add_column("order", sa.Column("cdek_tariff_code", sa.Integer(), nullable=True))
    op.add_column("order", sa.Column("cdek_error", sa.Text(), nullable=True))
    op.add_column("order", sa.Column("user_address_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_order_user_address_id",
        "order",
        "user_address",
        ["user_address_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_order_user_address_id", "order", type_="foreignkey")
    op.drop_column("order", "user_address_id")
    op.drop_column("order", "cdek_error")
    op.drop_column("order", "cdek_tariff_code")
    op.drop_column("order", "cdek_order_uuid")
    op.drop_column("order", "cdek_pvz_address")
    op.drop_column("order", "cdek_pvz_code")
    op.drop_column("order", "delivery_flat")
    op.drop_column("order", "delivery_lon")
    op.drop_column("order", "delivery_lat")
    op.drop_column("order", "delivery_address_text")
    op.drop_column("order", "delivery_date")
    op.drop_table("user_address")
