"""add task-first engagement tables

Revision ID: 20260428_0013
Revises: 20260422_0012
Create Date: 2026-04-28
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260428_0013"
down_revision: Union[str, None] = "20260422_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagement_targets.id"),
            nullable=False,
        ),
        sa.Column(
            "community_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("communities.id"),
            nullable=False,
        ),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("engagement_topics.id")),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("target_id"),
    )
    op.create_index("ix_engagements_community_id", "engagements", ["community_id"])
    op.create_index("ix_engagements_status_created", "engagements", ["status", "created_at"])

    op.create_table(
        "engagement_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("engagement_id"),
    )
    op.create_index("ix_engagement_settings_engagement_id", "engagement_settings", ["engagement_id"])

    _backfill_engagement_rows()


def downgrade() -> None:
    op.drop_table("engagement_settings")
    op.drop_table("engagements")


def _backfill_engagement_rows() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()

    targets = sa.Table("engagement_targets", metadata, autoload_with=bind)
    candidates = sa.Table("engagement_candidates", metadata, autoload_with=bind)
    legacy_settings = sa.Table("community_engagement_settings", metadata, autoload_with=bind)
    engagements = sa.Table("engagements", metadata, autoload_with=bind)
    engagement_settings = sa.Table("engagement_settings", metadata, autoload_with=bind)

    topic_rows = bind.execute(
        sa.select(
            candidates.c.community_id,
            sa.func.min(candidates.c.topic_id).label("topic_id"),
            sa.func.count(sa.distinct(candidates.c.topic_id)).label("topic_count"),
        )
        .where(candidates.c.topic_id.isnot(None))
        .group_by(candidates.c.community_id)
    ).mappings()
    single_topics = {
        row["community_id"]: row["topic_id"] for row in topic_rows if int(row["topic_count"] or 0) == 1
    }

    legacy_settings_by_community = {
        row["community_id"]: row
        for row in bind.execute(sa.select(legacy_settings)).mappings()
    }

    existing_engagements = {
        row["target_id"]: row
        for row in bind.execute(
            sa.select(engagements.c.id, engagements.c.target_id, engagements.c.community_id)
        ).mappings()
    }

    target_rows = list(
        bind.execute(
            sa.select(targets).where(targets.c.community_id.isnot(None)).order_by(targets.c.created_at.asc())
        ).mappings()
    )
    target_to_engagement_id: dict[uuid.UUID, uuid.UUID] = {}

    for target in target_rows:
        existing = existing_engagements.get(target["id"])
        if existing is not None:
            target_to_engagement_id[target["id"]] = existing["id"]
            continue

        community_id = target["community_id"]
        legacy = legacy_settings_by_community.get(community_id)
        topic_id = single_topics.get(community_id)
        engagement_id = uuid.uuid4()

        bind.execute(
            engagements.insert().values(
                id=engagement_id,
                target_id=target["id"],
                community_id=community_id,
                topic_id=topic_id,
                status=_backfilled_engagement_status(
                    target_status=target["status"],
                    legacy_mode=None if legacy is None else legacy["mode"],
                    topic_id=topic_id,
                ),
                name=None,
                created_by=target["approved_by"] or target["added_by"] or "migration",
                created_at=target["created_at"],
                updated_at=_later_timestamp(
                    target["updated_at"],
                    None if legacy is None else legacy["updated_at"],
                ),
            )
        )
        target_to_engagement_id[target["id"]] = engagement_id

    existing_settings_engagement_ids = {
        row["engagement_id"]
        for row in bind.execute(sa.select(engagement_settings.c.engagement_id)).mappings()
    }

    for target in target_rows:
        legacy = legacy_settings_by_community.get(target["community_id"])
        engagement_id = target_to_engagement_id.get(target["id"])
        if legacy is None or engagement_id is None or engagement_id in existing_settings_engagement_ids:
            continue

        bind.execute(
            engagement_settings.insert().values(
                id=uuid.uuid4(),
                engagement_id=engagement_id,
                mode=legacy["mode"],
                allow_join=legacy["allow_join"],
                allow_post=legacy["allow_post"],
                reply_only=legacy["reply_only"],
                require_approval=legacy["require_approval"],
                max_posts_per_day=legacy["max_posts_per_day"],
                min_minutes_between_posts=legacy["min_minutes_between_posts"],
                quiet_hours_start=legacy["quiet_hours_start"],
                quiet_hours_end=legacy["quiet_hours_end"],
                assigned_account_id=legacy["assigned_account_id"],
                created_at=legacy["created_at"],
                updated_at=legacy["updated_at"],
            )
        )
        existing_settings_engagement_ids.add(engagement_id)


def _backfilled_engagement_status(
    *,
    target_status: str,
    legacy_mode: str | None,
    topic_id: uuid.UUID | None,
) -> str:
    if target_status == "archived":
        return "archived"
    if topic_id is None or legacy_mode is None:
        return "draft"
    if target_status != "approved":
        return "draft"
    if legacy_mode == "disabled":
        return "paused"
    return "active"


def _later_timestamp(left, right):
    if left is None:
        return right
    if right is None:
        return left
    return right if right > left else left
