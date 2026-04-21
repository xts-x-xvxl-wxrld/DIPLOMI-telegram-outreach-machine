"""add engagement embedding cache tables

Revision ID: 20260421_0010
Revises: 20260420_0009
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260421_0010"
down_revision: Union[str, None] = "20260420_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagement_topic_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_topics.id"),
            nullable=False,
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("profile_text_hash", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("topic_id", "model", "dimensions", "profile_text_hash"),
    )
    op.create_index(
        "ix_engagement_topic_embeddings_topic_id",
        "engagement_topic_embeddings",
        ["topic_id"],
    )

    op.create_table(
        "engagement_message_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "community_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("communities.id"),
            nullable=False,
        ),
        sa.Column("tg_message_id", sa.BigInteger()),
        sa.Column("source_text_hash", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "community_id",
            "tg_message_id",
            "source_text_hash",
            "model",
            "dimensions",
        ),
    )
    op.create_index(
        "ix_engagement_message_embeddings_lookup",
        "engagement_message_embeddings",
        ["community_id", "source_text_hash", "model", "dimensions"],
    )
    op.create_index(
        "ix_engagement_message_embeddings_expires_at",
        "engagement_message_embeddings",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_engagement_message_embeddings_expires_at",
        table_name="engagement_message_embeddings",
    )
    op.drop_index(
        "ix_engagement_message_embeddings_lookup",
        table_name="engagement_message_embeddings",
    )
    op.drop_table("engagement_message_embeddings")
    op.drop_index(
        "ix_engagement_topic_embeddings_topic_id",
        table_name="engagement_topic_embeddings",
    )
    op.drop_table("engagement_topic_embeddings")
