"""unlimit slug length

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-14 20:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "category",
        "slug",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "subcategory",
        "slug",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "subcategory",
        "category_slug",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "fandom",
        "slug",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "product",
        "category_slug",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "product",
        "fandom_slug",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "product",
        "fandom_slug",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    op.alter_column(
        "product",
        "category_slug",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    op.alter_column(
        "fandom",
        "slug",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "subcategory",
        "category_slug",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "subcategory",
        "slug",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "category",
        "slug",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
