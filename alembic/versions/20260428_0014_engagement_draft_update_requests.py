"""add engagement draft update requests

Revision ID: 20260428_0014
Revises: 20260428_0013
Create Date: 2026-04-28
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260428_0014"
down_revision: Union[str, None] = "20260428_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagement_draft_update_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id"),
            nullable=False,
        ),
        sa.Column(
            "source_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_candidates.id"),
            nullable=False,
        ),
        sa.Column(
            "replacement_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_candidates.id"),
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("edit_request", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("source_queue_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_candidate_id"),
        sa.UniqueConstraint("replacement_candidate_id"),
    )
    op.create_index(
        "ix_engagement_draft_update_requests_engagement_status",
        "engagement_draft_update_requests",
        ["engagement_id", "status"],
    )
    op.create_index(
        "ix_engagement_draft_update_requests_queue_created",
        "engagement_draft_update_requests",
        ["source_queue_created_at"],
    )


def downgrade() -> None:
    op.drop_table("engagement_draft_update_requests")
