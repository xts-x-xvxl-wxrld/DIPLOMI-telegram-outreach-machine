"""remove tgstat-specific community metadata

Revision ID: 20260415_0004
Revises: 20260415_0003
Create Date: 2026-04-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260415_0004"
down_revision: Union[str, None] = "20260415_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("communities", "tgstat_id")


def downgrade() -> None:
    op.add_column("communities", sa.Column("tgstat_id", sa.Text()))
