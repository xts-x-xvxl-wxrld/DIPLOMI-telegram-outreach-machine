"""add telegram account pools

Revision ID: 20260420_0009
Revises: 20260420_0008
Create Date: 2026-04-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260420_0009"
down_revision: Union[str, None] = "20260420_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telegram_accounts",
        sa.Column("account_pool", sa.Text(), server_default="search", nullable=False),
    )
    op.create_index(
        "ix_telegram_accounts_pool_status_last_used",
        "telegram_accounts",
        ["account_pool", "status", "last_used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_accounts_pool_status_last_used", table_name="telegram_accounts")
    op.drop_column("telegram_accounts", "account_pool")
