"""add product deletion request fields

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-06-01 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t5u6v7w8x9y0"
down_revision: Union[str, None] = "s4t5u6v7w8x9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

moderation_status_enum = sa.Enum(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="moderationstatus",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "product",
        sa.Column("deletion_request_status", moderation_status_enum, nullable=True),
    )
    op.add_column(
        "product",
        sa.Column("deletion_request_reason", sa.String(), nullable=True),
    )
    op.add_column(
        "product",
        sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product", "deletion_requested_at")
    op.drop_column("product", "deletion_request_reason")
    op.drop_column("product", "deletion_request_status")
