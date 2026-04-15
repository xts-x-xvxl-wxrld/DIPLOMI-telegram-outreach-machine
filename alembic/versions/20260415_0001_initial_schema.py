"""initial schema

Revision ID: 20260415_0001
Revises:
Create Date: 2026-04-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260415_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audience_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text())),
        sa.Column("related_phrases", postgresql.ARRAY(sa.Text())),
        sa.Column("language_hints", postgresql.ARRAY(sa.Text())),
        sa.Column("geography_hints", postgresql.ARRAY(sa.Text())),
        sa.Column("exclusion_terms", postgresql.ARRAY(sa.Text())),
        sa.Column("community_types", postgresql.ARRAY(sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "communities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("member_count", sa.Integer()),
        sa.Column("language", sa.Text()),
        sa.Column("is_group", sa.Boolean()),
        sa.Column("is_broadcast", sa.Boolean()),
        sa.Column("tgstat_id", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("match_reason", sa.Text()),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audience_briefs.id")),
        sa.Column("status", sa.Text(), server_default="candidate", nullable=False),
        sa.Column("store_messages", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_snapshot_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "community_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("member_count", sa.Integer()),
        sa.Column("message_count_7d", sa.Integer()),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "collection_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audience_briefs.id")),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("analysis_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("window_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("messages_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("members_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("activity_events", sa.Integer(), server_default="0", nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("community_snapshots.id")),
        sa.Column("analysis_input", postgresql.JSONB()),
        sa.Column("analysis_input_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tg_message_id", sa.BigInteger(), nullable=False),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("sender_user_id", sa.BigInteger()),
        sa.Column("message_type", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("has_forward", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("forward_from_id", sa.BigInteger()),
        sa.Column("reply_to_message_id", sa.BigInteger()),
        sa.Column("views", sa.Integer()),
        sa.Column("reactions_count", sa.Integer()),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("message_date", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("community_id", "tg_message_id"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.Text()),
        sa.Column("first_name", sa.Text()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "community_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("activity_status", sa.Text(), server_default="inactive", nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("community_id", "user_id"),
    )

    op.create_table(
        "analysis_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audience_briefs.id")),
        sa.Column("summary", sa.Text()),
        sa.Column("dominant_themes", postgresql.ARRAY(sa.Text())),
        sa.Column("activity_level", sa.Text()),
        sa.Column("is_broadcast", sa.Boolean()),
        sa.Column("relevance_score", sa.Numeric(3, 2)),
        sa.Column("relevance_notes", sa.Text()),
        sa.Column("centrality", sa.Text()),
        sa.Column("analysis_window_days", sa.Integer(), server_default="90"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model", sa.Text()),
    )

    op.create_table(
        "telegram_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.Text(), nullable=False, unique=True),
        sa.Column("session_file_path", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="available", nullable=False),
        sa.Column("flood_wait_until", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("notes", sa.Text()),
    )

    op.create_index("ix_communities_status", "communities", ["status"])
    op.create_index("ix_communities_brief_id", "communities", ["brief_id"])
    op.create_index("ix_communities_store_messages", "communities", ["store_messages"])
    op.create_index("ix_collection_runs_community_started", "collection_runs", ["community_id", "started_at"])
    op.create_index("ix_collection_runs_analysis_status", "collection_runs", ["analysis_status"])
    op.create_index("ix_collection_runs_analysis_input_expires", "collection_runs", ["analysis_input_expires_at"])
    op.create_index("ix_messages_community_message_date", "messages", ["community_id", "message_date"])
    op.create_index("ix_users_tg_user_id", "users", ["tg_user_id"])
    op.create_index("ix_community_members_activity", "community_members", ["community_id", "activity_status"])
    op.create_index("ix_community_members_user_id", "community_members", ["user_id"])
    op.create_index("ix_analysis_summaries_community_analyzed", "analysis_summaries", ["community_id", "analyzed_at"])
    op.create_index("ix_telegram_accounts_status", "telegram_accounts", ["status"])
    op.create_index("ix_telegram_accounts_lease_expires", "telegram_accounts", ["lease_expires_at"])


def downgrade() -> None:
    op.drop_table("telegram_accounts")
    op.drop_table("analysis_summaries")
    op.drop_table("community_members")
    op.drop_table("users")
    op.drop_table("messages")
    op.drop_table("collection_runs")
    op.drop_table("community_snapshots")
    op.drop_table("communities")
    op.drop_table("audience_briefs")

