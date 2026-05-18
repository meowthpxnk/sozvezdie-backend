"""add seller card moderation

Revision ID: j5e6f7a8b9c0
Revises: i4d5e6f7a8b9
Create Date: 2026-05-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "j5e6f7a8b9c0"
down_revision: Union[str, None] = "i4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

moderation_status_enum = postgresql.ENUM(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="moderationstatus",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE sellercardmoderationaction AS ENUM (
                    'CREATE_SHOP', 'UPDATE_BRAND'
                );
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    seller_card_columns = {column["name"] for column in inspector.get_columns("seller_card")}

    if "status" not in seller_card_columns:
        op.add_column(
            "seller_card",
            sa.Column(
                "status",
                moderation_status_enum,
                nullable=False,
                server_default="APPROVED",
            ),
        )
        op.alter_column("seller_card", "status", server_default=None)

    if "created_at" not in seller_card_columns:
        op.add_column(
            "seller_card",
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )
        op.alter_column("seller_card", "created_at", server_default=None)

    if "seller_card_moderation" not in inspector.get_table_names():
        op.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS seller_card_moderation (
                    id SERIAL NOT NULL,
                    seller_card_id INTEGER NOT NULL,
                    moderator_id INTEGER,
                    action_type sellercardmoderationaction NOT NULL,
                    status moderationstatus NOT NULL,
                    comment VARCHAR,
                    proposed_name VARCHAR NOT NULL,
                    proposed_desc VARCHAR NOT NULL,
                    proposed_banner_image VARCHAR,
                    proposed_avatar_image VARCHAR,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    CONSTRAINT seller_card_moderation_pkey PRIMARY KEY (id),
                    CONSTRAINT seller_card_moderation_moderator_id_fkey
                        FOREIGN KEY (moderator_id)
                        REFERENCES "user" (id) ON DELETE SET NULL,
                    CONSTRAINT seller_card_moderation_seller_card_id_fkey
                        FOREIGN KEY (seller_card_id)
                        REFERENCES seller_card (id) ON DELETE CASCADE
                )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "seller_card_moderation" in inspector.get_table_names():
        op.drop_table("seller_card_moderation")

    seller_card_columns = {column["name"] for column in inspector.get_columns("seller_card")}
    if "created_at" in seller_card_columns:
        op.drop_column("seller_card", "created_at")
    if "status" in seller_card_columns:
        op.drop_column("seller_card", "status")

    op.execute(sa.text("DROP TYPE IF EXISTS sellercardmoderationaction"))
