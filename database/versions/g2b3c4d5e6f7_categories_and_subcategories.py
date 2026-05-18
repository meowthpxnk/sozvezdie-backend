"""refactor categories and add subcategories

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
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

OLD_TO_NEW_CATEGORY = {
    "gifts": "gifts",
    "jewelry": "jewelry",
    "home": "interior",
    "clothing": "wear",
    "stationery": "stationery",
    "dolls": "dolls",
    "interior": "interior",
    "accessories": "accessories",
    "wear": "wear",
    "cosmetics": "cosmetics",
}


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "category" in tables:
        columns = {column["name"] for column in inspector.get_columns("category")}
        if "id" in columns and "slug" not in columns:
            op.alter_column("category", "id", new_column_name="slug")

    if "product_category" in tables:
        op.add_column(
            "product",
            sa.Column("category_slug", sa.String(length=64), nullable=True),
        )
        op.add_column(
            "product",
            sa.Column("subcategory_id", sa.Integer(), nullable=True),
        )

        products = connection.execute(
            sa.text(
                """
                SELECT pc.product_id, pc.category_id
                FROM product_category pc
                """
            )
        ).fetchall()

        for product_id, category_id in products:
            mapped_slug = OLD_TO_NEW_CATEGORY.get(category_id, category_id)
            connection.execute(
                sa.text(
                    "UPDATE product SET category_slug = :category_slug "
                    "WHERE id = :product_id"
                ),
                {"category_slug": mapped_slug, "product_id": product_id},
            )

        op.drop_table("product_category")
    else:
        op.add_column(
            "product",
            sa.Column("category_slug", sa.String(length=64), nullable=True),
        )
        op.add_column(
            "product",
            sa.Column("subcategory_id", sa.Integer(), nullable=True),
        )

    if "category" in tables:
        connection.execute(sa.text("DELETE FROM category"))
    else:
        op.create_table(
            "category",
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.PrimaryKeyConstraint("slug"),
        )

    op.bulk_insert(
        sa.table(
            "category",
            sa.column("slug", sa.String(length=64)),
            sa.column("title", sa.String(length=255)),
        ),
        [{"slug": slug, "title": title} for slug, title in CATEGORY_ROWS],
    )

    op.create_table(
        "subcategory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category_slug", sa.String(length=64), nullable=False),
        sa.Column("seller_card_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_slug"], ["category.slug"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["seller_card_id"], ["seller_card.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_slug", "slug", name="uq_subcategory_category_slug"
        ),
    )

    op.create_foreign_key(
        "fk_product_category_slug",
        "product",
        "category",
        ["category_slug"],
        ["slug"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_product_subcategory_id",
        "product",
        "subcategory",
        ["subcategory_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_product_subcategory_id", "product", type_="foreignkey")
    op.drop_constraint("fk_product_category_slug", "product", type_="foreignkey")
    op.drop_table("subcategory")
    op.drop_column("product", "subcategory_id")
    op.drop_column("product", "category_slug")

    op.create_table(
        "product_category",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.slug"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "category_id"),
    )

    op.alter_column("category", "slug", new_column_name="id")
