"""add engagement quiet-hours timezone storage

Revision ID: 20260508_0018
Revises: 20260508_0017
Create Date: 2026-05-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260508_0018"
down_revision: Union[str, None] = "20260508_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "community_engagement_settings",
        sa.Column("quiet_hours_timezone", sa.Text(), nullable=False, server_default="utc"),
    )
    op.add_column(
        "engagement_settings",
        sa.Column("quiet_hours_timezone", sa.Text(), nullable=False, server_default="utc"),
    )


def downgrade() -> None:
    op.drop_column("engagement_settings", "quiet_hours_timezone")
    op.drop_column("community_engagement_settings", "quiet_hours_timezone")
