"""add vk url to seller card

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-01 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, None] = "r3s4t5u6v7w8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("seller_card", sa.Column("vk_url", sa.String(), nullable=True))
    op.add_column(
        "seller_card_moderation",
        sa.Column("proposed_vk_url", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seller_card_moderation", "proposed_vk_url")
    op.drop_column("seller_card", "vk_url")
