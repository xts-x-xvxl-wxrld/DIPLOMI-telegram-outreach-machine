"""add engagement opportunity cadence fields

Revision ID: 20260430_0016
Revises: 20260428_0015
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0016"
down_revision: Union[str, None] = "20260428_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "engagement_candidates",
        sa.Column("source_reply_to_tg_message_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("opportunity_kind", sa.Text(), server_default="root", nullable=False),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("root_candidate_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "engagement_candidates",
        sa.Column("conversation_key", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_engagement_candidates_root_candidate_id",
        "engagement_candidates",
        "engagement_candidates",
        ["root_candidate_id"],
        ["id"],
    )
    op.create_index(
        "ix_engagement_candidates_root_kind",
        "engagement_candidates",
        ["root_candidate_id", "opportunity_kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_engagement_candidates_root_kind", table_name="engagement_candidates")
    op.drop_constraint(
        "fk_engagement_candidates_root_candidate_id",
        "engagement_candidates",
        type_="foreignkey",
    )
    op.drop_column("engagement_candidates", "conversation_key")
    op.drop_column("engagement_candidates", "root_candidate_id")
    op.drop_column("engagement_candidates", "opportunity_kind")
    op.drop_column("engagement_candidates", "source_reply_to_tg_message_id")
