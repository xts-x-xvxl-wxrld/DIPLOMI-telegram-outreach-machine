"""add query-driven search schema

Revision ID: 20260421_0011
Revises: 20260421_0010
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260421_0011"
down_revision: Union[str, None] = "20260421_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text()),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column(
            "enabled_adapters",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{telegram_entity_search}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "language_hints",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "locale_hints",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("per_run_candidate_cap", sa.Integer(), server_default="100", nullable=False),
        sa.Column(
            "per_adapter_caps",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("planner_source", sa.Text()),
        sa.Column(
            "planner_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ranking_version", sa.Text()),
        sa.Column(
            "ranking_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_runs_status_created", "search_runs", ["status", "created_at"])
    op.create_index(
        "ix_search_runs_requested_by_created",
        "search_runs",
        ["requested_by", "created_at"],
    )

    op.create_table(
        "search_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("adapter", sa.Text(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("normalized_query_key", sa.Text(), nullable=False),
        sa.Column("language_hint", sa.Text()),
        sa.Column("locale_hint", sa.Text()),
        sa.Column(
            "include_terms",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "exclusion_terms",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("planner_source", sa.Text(), server_default="deterministic_v1", nullable=False),
        sa.Column(
            "planner_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "search_run_id",
            "adapter",
            "normalized_query_key",
            name="uq_search_queries_run_adapter_key",
        ),
    )
    op.create_index("ix_search_queries_run_status", "search_queries", ["search_run_id", "status"])
    op.create_index("ix_search_queries_adapter_status", "search_queries", ["adapter", "status"])

    op.create_table(
        "search_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("status", sa.Text(), server_default="candidate", nullable=False),
        sa.Column("normalized_username", sa.Text()),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("raw_title", sa.Text()),
        sa.Column("raw_description", sa.Text()),
        sa.Column("raw_member_count", sa.Integer()),
        sa.Column("adapter_first_seen", sa.Text()),
        sa.Column("score", sa.Numeric(8, 3)),
        sa.Column(
            "score_components",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ranking_version", sa.Text()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("last_reviewed_by", sa.Text()),
    )
    op.create_index("ix_search_candidates_run_status", "search_candidates", ["search_run_id", "status"])
    op.create_index("ix_search_candidates_community_id", "search_candidates", ["community_id"])
    op.create_index("ix_search_candidates_score", "search_candidates", ["score"])
    op.create_index(
        "uq_search_candidates_run_community",
        "search_candidates",
        ["search_run_id", "community_id"],
        unique=True,
        postgresql_where=sa.text("community_id IS NOT NULL"),
    )
    op.create_index(
        "uq_search_candidates_run_username",
        "search_candidates",
        ["search_run_id", "normalized_username"],
        unique=True,
        postgresql_where=sa.text("normalized_username IS NOT NULL"),
    )
    op.create_index(
        "uq_search_candidates_run_canonical_url",
        "search_candidates",
        ["search_run_id", "canonical_url"],
        unique=True,
        postgresql_where=sa.text("canonical_url IS NOT NULL"),
    )

    op.create_table(
        "search_candidate_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column(
            "search_query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_queries.id", ondelete="SET NULL"),
        ),
        sa.Column("adapter", sa.Text(), nullable=False),
        sa.Column("query_text", sa.Text()),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("evidence_value", sa.Text()),
        sa.Column(
            "evidence_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("source_seed_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seed_groups.id")),
        sa.Column("source_seed_channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seed_channels.id")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_search_candidate_evidence_candidate_captured",
        "search_candidate_evidence",
        ["search_candidate_id", "captured_at"],
    )
    op.create_index(
        "ix_search_candidate_evidence_run_type",
        "search_candidate_evidence",
        ["search_run_id", "evidence_type"],
    )
    op.create_index(
        "ix_search_candidate_evidence_community_id",
        "search_candidate_evidence",
        ["community_id"],
    )

    op.create_table(
        "search_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("communities.id")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), server_default="run", nullable=False),
        sa.Column("requested_by", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_search_reviews_candidate_created",
        "search_reviews",
        ["search_candidate_id", "created_at"],
    )
    op.create_index("ix_search_reviews_run_action", "search_reviews", ["search_run_id", "action"])


def downgrade() -> None:
    op.drop_index("ix_search_reviews_run_action", table_name="search_reviews")
    op.drop_index("ix_search_reviews_candidate_created", table_name="search_reviews")
    op.drop_table("search_reviews")

    op.drop_index("ix_search_candidate_evidence_community_id", table_name="search_candidate_evidence")
    op.drop_index("ix_search_candidate_evidence_run_type", table_name="search_candidate_evidence")
    op.drop_index(
        "ix_search_candidate_evidence_candidate_captured",
        table_name="search_candidate_evidence",
    )
    op.drop_table("search_candidate_evidence")

    op.drop_index("uq_search_candidates_run_canonical_url", table_name="search_candidates")
    op.drop_index("uq_search_candidates_run_username", table_name="search_candidates")
    op.drop_index("uq_search_candidates_run_community", table_name="search_candidates")
    op.drop_index("ix_search_candidates_score", table_name="search_candidates")
    op.drop_index("ix_search_candidates_community_id", table_name="search_candidates")
    op.drop_index("ix_search_candidates_run_status", table_name="search_candidates")
    op.drop_table("search_candidates")

    op.drop_index("ix_search_queries_adapter_status", table_name="search_queries")
    op.drop_index("ix_search_queries_run_status", table_name="search_queries")
    op.drop_table("search_queries")

    op.drop_index("ix_search_runs_requested_by_created", table_name="search_runs")
    op.drop_index("ix_search_runs_status_created", table_name="search_runs")
    op.drop_table("search_runs")
