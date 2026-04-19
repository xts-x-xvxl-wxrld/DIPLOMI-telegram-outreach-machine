"""add engagement targets

Revision ID: 20260419_0007
Revises: 20260419_0006
Create Date: 2026-04-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260419_0007"
down_revision: Union[str, None] = "20260419_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagement_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("submitted_ref", sa.Text(), nullable=False),
        sa.Column("submitted_ref_type", sa.Text(), server_default="telegram_username", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("allow_join", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("allow_detect", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("allow_post", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("added_by", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("community_id"),
    )
    op.create_index("ix_engagement_targets_community_id", "engagement_targets", ["community_id"])
    op.create_index("ix_engagement_targets_status", "engagement_targets", ["status"])
    op.create_index("ix_engagement_targets_submitted_ref", "engagement_targets", ["submitted_ref"])


def downgrade() -> None:
    op.drop_table("engagement_targets")
