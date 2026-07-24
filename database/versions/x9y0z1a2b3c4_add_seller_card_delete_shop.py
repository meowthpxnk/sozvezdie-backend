"""add seller card delete shop moderation

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-07-24 09:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x9y0z1a2b3c4"
down_revision: Union[str, None] = "w8x9y0z1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TYPE sellercardmoderationaction ADD VALUE IF NOT EXISTS 'DELETE_SHOP'"
        )
    )

    op.add_column("seller_card_moderation", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE seller_card_moderation AS moderation
            SET user_id = seller_card.user_id
            FROM seller_card
            WHERE moderation.seller_card_id = seller_card.id
              AND moderation.user_id IS NULL
            """
        )
    )
    op.alter_column("seller_card_moderation", "user_id", nullable=False)
    op.create_foreign_key(
        "seller_card_moderation_user_id_fkey",
        "seller_card_moderation",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "seller_card_moderation_seller_card_id_fkey",
        "seller_card_moderation",
        type_="foreignkey",
    )
    op.alter_column("seller_card_moderation", "seller_card_id", nullable=True)
    op.create_foreign_key(
        "seller_card_moderation_seller_card_id_fkey",
        "seller_card_moderation",
        "seller_card",
        ["seller_card_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "seller_card_moderation_seller_card_id_fkey",
        "seller_card_moderation",
        type_="foreignkey",
    )
    op.execute(
        sa.text(
            """
            DELETE FROM seller_card_moderation
            WHERE seller_card_id IS NULL
               OR action_type = 'DELETE_SHOP'
            """
        )
    )
    op.alter_column("seller_card_moderation", "seller_card_id", nullable=False)
    op.create_foreign_key(
        "seller_card_moderation_seller_card_id_fkey",
        "seller_card_moderation",
        "seller_card",
        ["seller_card_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "seller_card_moderation_user_id_fkey",
        "seller_card_moderation",
        type_="foreignkey",
    )
    op.drop_column("seller_card_moderation", "user_id")
