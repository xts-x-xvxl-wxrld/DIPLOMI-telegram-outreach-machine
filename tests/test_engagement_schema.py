from __future__ import annotations

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.db.enums import (
    CommunityAccountMembershipStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
)
from backend.db.models import (
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementTopic,
)


def test_engagement_status_enums_match_contract() -> None:
    assert [item.value for item in EngagementMode] == [
        "disabled",
        "observe",
        "suggest",
        "require_approval",
        "auto_limited",
    ]
    assert [item.value for item in CommunityAccountMembershipStatus] == [
        "not_joined",
        "join_requested",
        "joined",
        "failed",
        "left",
        "banned",
    ]
    assert [item.value for item in EngagementCandidateStatus] == [
        "needs_review",
        "approved",
        "rejected",
        "sent",
        "expired",
        "failed",
    ]
    assert [item.value for item in EngagementActionType] == ["join", "reply", "post", "skip"]
    assert [item.value for item in EngagementActionStatus] == ["queued", "sent", "failed", "skipped"]


def test_engagement_model_defaults_are_contract_defaults() -> None:
    settings_columns = CommunityEngagementSettings.__table__.c
    assert settings_columns.mode.default.arg == EngagementMode.SUGGEST.value
    assert settings_columns.allow_join.default.arg is False
    assert settings_columns.allow_post.default.arg is False
    assert settings_columns.reply_only.default.arg is True
    assert settings_columns.require_approval.default.arg is True
    assert settings_columns.max_posts_per_day.default.arg == 1
    assert settings_columns.min_minutes_between_posts.default.arg == 240

    assert CommunityAccountMembership.__table__.c.status.default.arg == (
        CommunityAccountMembershipStatus.NOT_JOINED.value
    )
    assert EngagementTopic.__table__.c.active.default.arg is True
    assert EngagementCandidate.__table__.c.status.default.arg == EngagementCandidateStatus.NEEDS_REVIEW.value
    assert EngagementAction.__table__.c.action_type.default.arg == EngagementActionType.REPLY.value
    assert EngagementAction.__table__.c.status.default.arg == EngagementActionStatus.QUEUED.value


def test_engagement_uniqueness_constraints_are_declared() -> None:
    assert _has_unique_constraint(CommunityEngagementSettings, ["community_id"])
    assert _has_unique_constraint(CommunityAccountMembership, ["community_id", "telegram_account_id"])
    assert _has_unique_constraint(EngagementAction, ["idempotency_key"])


def test_engagement_indexes_are_declared() -> None:
    assert _has_index(CommunityEngagementSettings, ["community_id"])
    assert _has_index(CommunityAccountMembership, ["community_id", "telegram_account_id"])
    assert _has_index(EngagementTopic, ["active"])
    assert _has_index(EngagementCandidate, ["status", "created_at"])
    assert _has_index(EngagementCandidate, ["community_id", "topic_id", "status"])
    assert _has_index(EngagementAction, ["community_id", "created_at"])
    assert _has_index(EngagementAction, ["telegram_account_id", "created_at"])


def test_engagement_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()

    for model in (
        CommunityEngagementSettings,
        CommunityAccountMembership,
        EngagementTopic,
        EngagementCandidate,
        EngagementAction,
    ):
        ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert model.__tablename__ in ddl


def _has_unique_constraint(model: type[object], column_names: list[str]) -> bool:
    expected = set(column_names)
    return any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def _has_index(model: type[object], column_names: list[str]) -> bool:
    return any([column.name for column in index.columns] == column_names for index in model.__table__.indexes)
