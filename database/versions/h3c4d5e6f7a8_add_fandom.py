"""add fandom table and product fandom_slug

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-05-18 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h3c4d5e6f7a8"
down_revision: Union[str, None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FANDOM_ROWS = [
    ("naruto", "Наруто"),
    ("one-piece", "Ван Пис"),
    ("demon-slayer", "Истребитель демонов"),
    ("attack-on-titan", "Атака титанов"),
    ("genshin-impact", "Genshin Impact"),
    ("marvel", "Marvel"),
    ("harry-potter", "Гарри Поттер"),
    ("star-wars", "Звёздные войны"),
    ("minecraft", "Minecraft"),
    ("original", "Оригинальный контент"),
]

FANDOM_SLUGS = [row[0] for row in FANDOM_ROWS]


def upgrade() -> None:
    fandom_table = op.create_table(
        "fandom",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("slug"),
    )

    op.bulk_insert(
        fandom_table,
        [{"slug": slug, "title": title} for slug, title in FANDOM_ROWS],
    )

    op.add_column(
        "product",
        sa.Column("fandom_slug", sa.String(length=64), nullable=True),
    )

    op.create_foreign_key(
        "fk_product_fandom_slug",
        "product",
        "fandom",
        ["fandom_slug"],
        ["slug"],
        ondelete="SET NULL",
    )

    connection = op.get_bind()
    products = connection.execute(sa.text("SELECT id FROM product ORDER BY id")).fetchall()

    for index, (product_id,) in enumerate(products):
        fandom_slug = FANDOM_SLUGS[index % len(FANDOM_SLUGS)]
        connection.execute(
            sa.text(
                "UPDATE product SET fandom_slug = :fandom_slug WHERE id = :product_id"
            ),
            {"fandom_slug": fandom_slug, "product_id": product_id},
        )


def downgrade() -> None:
    op.drop_constraint("fk_product_fandom_slug", "product", type_="foreignkey")
    op.drop_column("product", "fandom_slug")
    op.drop_table("fandom")
