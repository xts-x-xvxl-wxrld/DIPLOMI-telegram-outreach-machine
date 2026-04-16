"""add manual seed groups

Revision ID: 20260415_0002
Revises: 20260415_0001
Create Date: 2026-04-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260415_0002"
down_revision: Union[str, None] = "20260415_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seed_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_index("ix_seed_groups_normalized_name", "seed_groups", ["normalized_name"])

    op.create_table(
        "seed_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seed_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seed_groups.id"), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.Text(), nullable=False),
        sa.Column("username", sa.Text()),
        sa.Column("telegram_url", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("seed_group_id", "normalized_key"),
    )
    op.create_index("ix_seed_channels_seed_group_id", "seed_channels", ["seed_group_id"])
    op.create_index("ix_seed_channels_status", "seed_channels", ["status"])
    op.create_index("ix_seed_channels_community_id", "seed_channels", ["community_id"])


def downgrade() -> None:
    op.drop_index("ix_seed_channels_community_id", table_name="seed_channels")
    op.drop_index("ix_seed_channels_status", table_name="seed_channels")
    op.drop_index("ix_seed_channels_seed_group_id", table_name="seed_channels")
    op.drop_table("seed_channels")
    op.drop_index("ix_seed_groups_normalized_name", table_name="seed_groups")
    op.drop_table("seed_groups")
