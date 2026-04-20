"""add engagement admin control plane tables

Revision ID: 20260420_0008
Revises: 20260419_0007
Create Date: 2026-04-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260420_0008"
down_revision: Union[str, None] = "20260419_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagement_prompt_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Numeric(4, 3), server_default="0.2", nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column(
            "output_schema_name",
            sa.Text(),
            server_default="engagement_detection_v1",
            nullable=False,
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_engagement_prompt_profiles_active",
        "engagement_prompt_profiles",
        ["active"],
    )
    op.create_index(
        "ix_engagement_prompt_profiles_updated",
        "engagement_prompt_profiles",
        ["updated_at"],
    )

    op.create_table(
        "engagement_prompt_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "prompt_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_prompt_profiles.id"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Numeric(4, 3), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("output_schema_name", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prompt_profile_id", "version_number"),
    )
    op.create_index(
        "ix_engagement_prompt_profile_versions_profile",
        "engagement_prompt_profile_versions",
        ["prompt_profile_id"],
    )

    op.create_table(
        "engagement_style_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_type", sa.Text(), server_default="global", nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True)),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_engagement_style_rules_scope",
        "engagement_style_rules",
        ["scope_type", "scope_id", "active", "priority"],
    )
    op.create_index(
        "ix_engagement_style_rules_active",
        "engagement_style_rules",
        ["active"],
    )

    op.add_column(
        "engagement_candidates",
        sa.Column(
            "prompt_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_prompt_profiles.id"),
        ),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column(
            "prompt_profile_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_prompt_profile_versions.id"),
        ),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("prompt_render_summary", postgresql.JSONB()),
    )

    op.create_table(
        "engagement_candidate_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_candidates.id"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=False),
        sa.Column("edited_by", sa.Text(), nullable=False),
        sa.Column("edit_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("candidate_id", "revision_number"),
    )
    op.create_index(
        "ix_engagement_candidate_revisions_candidate",
        "engagement_candidate_revisions",
        ["candidate_id", "revision_number"],
    )


def downgrade() -> None:
    op.drop_table("engagement_candidate_revisions")
    op.drop_column("engagement_candidates", "prompt_render_summary")
    op.drop_column("engagement_candidates", "prompt_profile_version_id")
    op.drop_column("engagement_candidates", "prompt_profile_id")
    op.drop_table("engagement_style_rules")
    op.drop_table("engagement_prompt_profile_versions")
    op.drop_table("engagement_prompt_profiles")
