"""add vk_id_mapping

Revision ID: k6g7h8i9j0k1
Revises: j5e6f7a8b9c0
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k6g7h8i9j0k1"
down_revision: Union[str, None] = "j5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vk_id_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vk_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vk_id", name="uq_vk_id_mapping_vk_id"),
        sa.UniqueConstraint("user_id", name="uq_vk_id_mapping_user_id"),
    )


def downgrade() -> None:
    op.drop_table("vk_id_mapping")
