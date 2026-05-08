"""raise engagement settings cadence defaults

Revision ID: 20260508_0017
Revises: 20260430_0016
Create Date: 2026-05-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260508_0017"
down_revision: Union[str, None] = "20260430_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "community_engagement_settings",
        "max_posts_per_day",
        existing_type=sa.Integer(),
        server_default="300",
    )
    op.alter_column(
        "community_engagement_settings",
        "min_minutes_between_posts",
        existing_type=sa.Integer(),
        server_default="1",
    )
    op.alter_column(
        "engagement_settings",
        "max_posts_per_day",
        existing_type=sa.Integer(),
        server_default="300",
    )
    op.alter_column(
        "engagement_settings",
        "min_minutes_between_posts",
        existing_type=sa.Integer(),
        server_default="1",
    )

    op.execute(
        sa.text(
            """
            UPDATE community_engagement_settings
            SET max_posts_per_day = 300,
                min_minutes_between_posts = 1
            WHERE max_posts_per_day = 1
              AND min_minutes_between_posts = 240
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE engagement_settings
            SET max_posts_per_day = 300,
                min_minutes_between_posts = 1
            WHERE max_posts_per_day = 1
              AND min_minutes_between_posts = 240
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE engagement_settings
            SET max_posts_per_day = 1,
                min_minutes_between_posts = 240
            WHERE max_posts_per_day = 300
              AND min_minutes_between_posts = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE community_engagement_settings
            SET max_posts_per_day = 1,
                min_minutes_between_posts = 240
            WHERE max_posts_per_day = 300
              AND min_minutes_between_posts = 1
            """
        )
    )

    op.alter_column(
        "engagement_settings",
        "min_minutes_between_posts",
        existing_type=sa.Integer(),
        server_default="240",
    )
    op.alter_column(
        "engagement_settings",
        "max_posts_per_day",
        existing_type=sa.Integer(),
        server_default="1",
    )
    op.alter_column(
        "community_engagement_settings",
        "min_minutes_between_posts",
        existing_type=sa.Integer(),
        server_default="240",
    )
    op.alter_column(
        "community_engagement_settings",
        "max_posts_per_day",
        existing_type=sa.Integer(),
        server_default="1",
    )
