"""add one_c_author_id and author_invite

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-13 22:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE "user"
            ADD COLUMN IF NOT EXISTS one_c_author_id VARCHAR
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_one_c_author_id
            ON "user" (one_c_author_id)
            WHERE one_c_author_id IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS author_invite (
                id SERIAL PRIMARY KEY,
                token VARCHAR NOT NULL UNIQUE,
                one_c_author_id VARCHAR NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                used_at TIMESTAMP WITHOUT TIME ZONE,
                used_by_user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_author_invite_one_c_unused
            ON author_invite (one_c_author_id)
            WHERE used_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_author_invite_one_c_unused"))
    op.execute(sa.text("DROP TABLE IF EXISTS author_invite"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_user_one_c_author_id"))
    op.execute(
        sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS one_c_author_id')
    )
