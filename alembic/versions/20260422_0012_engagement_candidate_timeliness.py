"""add engagement candidate timeliness fields

Revision ID: 20260422_0012
Revises: 20260421_0011
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260422_0012"
down_revision: Union[str, None] = "20260421_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "engagement_candidates",
        sa.Column("source_message_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("moment_strength", sa.Text(), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("timeliness", sa.Text(), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("reply_value", sa.Text(), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("review_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("reply_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("operator_notified_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE engagement_candidates
            SET
                source_message_date = created_at,
                detected_at = COALESCE(created_at, now()),
                moment_strength = 'good',
                timeliness = 'fresh',
                reply_value = CASE
                    WHEN suggested_reply IS NOT NULL THEN 'other'
                    ELSE 'none'
                END,
                review_deadline_at = COALESCE(created_at, now()) + interval '60 minutes',
                reply_deadline_at = COALESCE(created_at, now()) + interval '90 minutes'
            WHERE detected_at IS NULL
               OR moment_strength IS NULL
               OR timeliness IS NULL
               OR reply_value IS NULL
               OR reply_deadline_at IS NULL
            """
        )
    )

    op.alter_column("engagement_candidates", "detected_at", nullable=False)
    op.alter_column("engagement_candidates", "moment_strength", nullable=False)
    op.alter_column("engagement_candidates", "timeliness", nullable=False)
    op.alter_column("engagement_candidates", "reply_value", nullable=False)
    op.alter_column("engagement_candidates", "reply_deadline_at", nullable=False)


def downgrade() -> None:
    op.drop_column("engagement_candidates", "operator_notified_at")
    op.drop_column("engagement_candidates", "reply_deadline_at")
    op.drop_column("engagement_candidates", "review_deadline_at")
    op.drop_column("engagement_candidates", "reply_value")
    op.drop_column("engagement_candidates", "timeliness")
    op.drop_column("engagement_candidates", "moment_strength")
    op.drop_column("engagement_candidates", "detected_at")
    op.drop_column("engagement_candidates", "source_message_date")
