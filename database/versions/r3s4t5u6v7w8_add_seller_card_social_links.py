"""add seller card social links

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-06-01 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r3s4t5u6v7w8"
down_revision: Union[str, None] = "q2r3s4t5u6v7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seller_card",
        sa.Column("tiktok_url", sa.String(), nullable=True),
    )
    op.add_column(
        "seller_card",
        sa.Column("telegram_channel_url", sa.String(), nullable=True),
    )
    op.add_column(
        "seller_card_moderation",
        sa.Column("proposed_tiktok_url", sa.String(), nullable=True),
    )
    op.add_column(
        "seller_card_moderation",
        sa.Column("proposed_telegram_channel_url", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seller_card_moderation", "proposed_telegram_channel_url")
    op.drop_column("seller_card_moderation", "proposed_tiktok_url")
    op.drop_column("seller_card", "telegram_channel_url")
    op.drop_column("seller_card", "tiktok_url")
