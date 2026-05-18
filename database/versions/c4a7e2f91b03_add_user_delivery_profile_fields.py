"""add user delivery profile fields

Revision ID: c4a7e2f91b03
Revises: a8f3c2e1b904
Create Date: 2026-05-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a7e2f91b03"
down_revision: Union[str, None] = "b534512e16a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("full_name", sa.String(), nullable=True))
    op.add_column("user", sa.Column("email", sa.String(), nullable=True))
    op.add_column("user", sa.Column("phone", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "phone")
    op.drop_column("user", "email")
    op.drop_column("user", "full_name")
