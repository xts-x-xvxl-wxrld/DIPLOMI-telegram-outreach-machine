"""add engagement schema

Revision ID: 20260419_0006
Revises: 20260416_0005
Create Date: 2026-04-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260419_0006"
down_revision: Union[str, None] = "20260416_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "community_engagement_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id"), nullable=False),
        sa.Column("mode", sa.Text(), server_default="suggest", nullable=False),
        sa.Column("allow_join", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("allow_post", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reply_only", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("require_approval", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("max_posts_per_day", sa.Integer(), server_default="1", nullable=False),
        sa.Column("min_minutes_between_posts", sa.Integer(), server_default="240", nullable=False),
        sa.Column("quiet_hours_start", sa.Time(timezone=False)),
        sa.Column("quiet_hours_end", sa.Time(timezone=False)),
        sa.Column(
            "assigned_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telegram_accounts.id"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("community_id"),
    )
    op.create_index(
        "ix_community_engagement_settings_community_id",
        "community_engagement_settings",
        ["community_id"],
    )

    op.create_table(
        "community_account_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id"), nullable=False),
        sa.Column(
            "telegram_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telegram_accounts.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="not_joined", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("community_id", "telegram_account_id"),
    )
    op.create_index(
        "ix_community_account_memberships_community_account",
        "community_account_memberships",
        ["community_id", "telegram_account_id"],
    )

    op.create_table(
        "engagement_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("stance_guidance", sa.Text(), nullable=False),
        sa.Column(
            "trigger_keywords",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "negative_keywords",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "example_good_replies",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "example_bad_replies",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_engagement_topics_active", "engagement_topics", ["active"])

    op.create_table(
        "engagement_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id"), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("engagement_topics.id"), nullable=False),
        sa.Column("source_tg_message_id", sa.BigInteger()),
        sa.Column("source_excerpt", sa.Text()),
        sa.Column("detected_reason", sa.Text(), nullable=False),
        sa.Column("suggested_reply", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("model_output", postgresql.JSONB()),
        sa.Column("risk_notes", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("status", sa.Text(), server_default="needs_review", nullable=False),
        sa.Column("final_reply", sa.Text()),
        sa.Column("reviewed_by", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_engagement_candidates_status_created",
        "engagement_candidates",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_engagement_candidates_community_topic_status",
        "engagement_candidates",
        ["community_id", "topic_id", "status"],
    )

    op.create_table(
        "engagement_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("engagement_candidates.id")),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id"), nullable=False),
        sa.Column(
            "telegram_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telegram_accounts.id"),
            nullable=False,
        ),
        sa.Column("action_type", sa.Text(), server_default="reply", nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("outbound_text", sa.Text()),
        sa.Column("reply_to_tg_message_id", sa.BigInteger()),
        sa.Column("sent_tg_message_id", sa.BigInteger()),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_engagement_actions_community_created",
        "engagement_actions",
        ["community_id", "created_at"],
    )
    op.create_index(
        "ix_engagement_actions_account_created",
        "engagement_actions",
        ["telegram_account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("engagement_actions")
    op.drop_table("engagement_candidates")
    op.drop_table("engagement_topics")
    op.drop_table("community_account_memberships")
    op.drop_table("community_engagement_settings")
