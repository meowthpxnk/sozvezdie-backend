"""add category and product_category tables

Revision ID: f1a2b3c4d5e6
Revises: e9a1b2c3d4f5
Create Date: 2026-05-17 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e9a1b2c3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_ROWS = [
    ("gifts", "Подарки"),
    ("jewelry", "Украшения"),
    ("dolls", "Куклы"),
    ("stationery", "Канцелярия"),
    ("interior", "Интерьер"),
    ("accessories", "Аксессуары"),
    ("wear", "Одежда"),
    ("cosmetics", "Косметика"),
]

CATEGORY_SLUGS = [row[0] for row in CATEGORY_ROWS]


def upgrade() -> None:
    category_table = op.create_table(
        "category",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("slug"),
    )

    op.create_table(
        "product_category",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.slug"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "category_id"),
    )

    op.bulk_insert(
        category_table,
        [{"slug": slug, "title": title} for slug, title in CATEGORY_ROWS],
    )

    connection = op.get_bind()
    products = connection.execute(sa.text("SELECT id FROM product ORDER BY id")).fetchall()

    product_category_rows = []
    for index, (product_id,) in enumerate(products):
        category_id = CATEGORY_SLUGS[index % len(CATEGORY_SLUGS)]
        product_category_rows.append(
            {"product_id": product_id, "category_id": category_id}
        )

    for row in product_category_rows:
        connection.execute(
            sa.text(
                "INSERT INTO product_category (product_id, category_id) "
                "VALUES (:product_id, :category_id)"
            ),
            row,
        )


def downgrade() -> None:
    op.drop_table("product_category")
    op.drop_table("category")
