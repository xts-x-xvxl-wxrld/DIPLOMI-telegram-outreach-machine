"""add community discovery edges

Revision ID: 20260415_0003
Revises: 20260415_0002
Create Date: 2026-04-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260415_0003"
down_revision: Union[str, None] = "20260415_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "community_discovery_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seed_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seed_groups.id")),
        sa.Column("seed_channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seed_channels.id")),
        sa.Column(
            "source_community_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("communities.id"),
        ),
        sa.Column(
            "target_community_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("communities.id"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("evidence_value", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "seed_group_id",
            "seed_channel_id",
            "source_community_id",
            "target_community_id",
            "evidence_type",
            "evidence_value",
            name="uq_community_discovery_edges_identity",
        ),
    )
    op.create_index(
        "ix_community_discovery_edges_seed_group_id",
        "community_discovery_edges",
        ["seed_group_id"],
    )
    op.create_index(
        "ix_community_discovery_edges_seed_channel_id",
        "community_discovery_edges",
        ["seed_channel_id"],
    )
    op.create_index(
        "ix_community_discovery_edges_source_community_id",
        "community_discovery_edges",
        ["source_community_id"],
    )
    op.create_index(
        "ix_community_discovery_edges_target_community_id",
        "community_discovery_edges",
        ["target_community_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_community_discovery_edges_target_community_id", table_name="community_discovery_edges")
    op.drop_index("ix_community_discovery_edges_source_community_id", table_name="community_discovery_edges")
    op.drop_index("ix_community_discovery_edges_seed_channel_id", table_name="community_discovery_edges")
    op.drop_index("ix_community_discovery_edges_seed_group_id", table_name="community_discovery_edges")
    op.drop_table("community_discovery_edges")
