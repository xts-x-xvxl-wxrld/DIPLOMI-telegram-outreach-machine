from __future__ import annotations

from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.db.enums import (
    AccountPool,
    CommunityAccountMembershipStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMomentStrength,
    EngagementMode,
    EngagementReplyValue,
    EngagementStyleRuleScope,
    EngagementTimeliness,
    EngagementTargetRefType,
    EngagementTargetStatus,
)
from backend.db.models import (
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementCandidateRevision,
    EngagementMessageEmbedding,
    EngagementPromptProfile,
    EngagementPromptProfileVersion,
    EngagementStyleRule,
    EngagementTarget,
    EngagementTopicEmbedding,
    EngagementTopic,
    TelegramAccount,
)


def test_engagement_status_enums_match_contract() -> None:
    assert [item.value for item in AccountPool] == ["search", "engagement", "disabled"]
    assert [item.value for item in EngagementMode] == [
        "disabled",
        "observe",
        "suggest",
        "require_approval",
        "auto_limited",
    ]
    assert [item.value for item in EngagementTargetRefType] == [
        "community_id",
        "telegram_username",
        "telegram_link",
        "invite_link",
    ]
    assert [item.value for item in EngagementTargetStatus] == [
        "pending",
        "resolved",
        "approved",
        "rejected",
        "failed",
        "archived",
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
    assert [item.value for item in EngagementMomentStrength] == ["weak", "good", "strong"]
    assert [item.value for item in EngagementTimeliness] == ["fresh", "aging", "stale"]
    assert [item.value for item in EngagementReplyValue] == [
        "clarifying_question",
        "practical_tip",
        "correction",
        "resource",
        "other",
        "none",
    ]
    assert [item.value for item in EngagementActionType] == ["join", "reply", "post", "skip"]
    assert [item.value for item in EngagementActionStatus] == ["queued", "sent", "failed", "skipped"]
    assert [item.value for item in EngagementStyleRuleScope] == ["global", "account", "community", "topic"]


def test_engagement_model_defaults_are_contract_defaults() -> None:
    account_columns = TelegramAccount.__table__.c
    assert account_columns.account_pool.default.arg == AccountPool.SEARCH.value
    assert account_columns.account_pool.server_default.arg == AccountPool.SEARCH.value

    settings_columns = CommunityEngagementSettings.__table__.c
    assert settings_columns.mode.default.arg == EngagementMode.SUGGEST.value
    assert settings_columns.allow_join.default.arg is False
    assert settings_columns.allow_post.default.arg is False
    assert settings_columns.reply_only.default.arg is True
    assert settings_columns.require_approval.default.arg is True
    assert settings_columns.max_posts_per_day.default.arg == 1
    assert settings_columns.min_minutes_between_posts.default.arg == 240

    assert EngagementTarget.__table__.c.submitted_ref_type.default.arg == (
        EngagementTargetRefType.TELEGRAM_USERNAME.value
    )
    assert EngagementTarget.__table__.c.status.default.arg == EngagementTargetStatus.PENDING.value
    assert EngagementTarget.__table__.c.allow_join.default.arg is False
    assert EngagementTarget.__table__.c.allow_detect.default.arg is False
    assert EngagementTarget.__table__.c.allow_post.default.arg is False
    assert CommunityAccountMembership.__table__.c.status.default.arg == (
        CommunityAccountMembershipStatus.NOT_JOINED.value
    )
    assert EngagementTopic.__table__.c.active.default.arg is True
    assert EngagementCandidate.__table__.c.status.default.arg == EngagementCandidateStatus.NEEDS_REVIEW.value
    assert EngagementAction.__table__.c.action_type.default.arg == EngagementActionType.REPLY.value
    assert EngagementAction.__table__.c.status.default.arg == EngagementActionStatus.QUEUED.value
    assert EngagementPromptProfile.__table__.c.active.default.arg is False
    assert EngagementPromptProfile.__table__.c.temperature.default.arg == Decimal("0.2")
    assert EngagementPromptProfile.__table__.c.max_output_tokens.default.arg == 1000
    assert EngagementStyleRule.__table__.c.scope_type.default.arg == EngagementStyleRuleScope.GLOBAL.value
    assert EngagementStyleRule.__table__.c.active.default.arg is True
    assert EngagementStyleRule.__table__.c.priority.default.arg == 100


def test_engagement_uniqueness_constraints_are_declared() -> None:
    assert _has_unique_constraint(CommunityEngagementSettings, ["community_id"])
    assert _has_unique_constraint(EngagementTarget, ["community_id"])
    assert _has_unique_constraint(CommunityAccountMembership, ["community_id", "telegram_account_id"])
    assert _has_unique_constraint(EngagementTopicEmbedding, ["topic_id", "model", "dimensions", "profile_text_hash"])
    assert _has_unique_constraint(
        EngagementMessageEmbedding,
        ["community_id", "tg_message_id", "source_text_hash", "model", "dimensions"],
    )
    assert _has_unique_constraint(EngagementAction, ["idempotency_key"])
    assert _has_unique_constraint(EngagementPromptProfileVersion, ["prompt_profile_id", "version_number"])
    assert _has_unique_constraint(EngagementCandidateRevision, ["candidate_id", "revision_number"])


def test_engagement_indexes_are_declared() -> None:
    assert _has_index(TelegramAccount, ["account_pool", "status", "last_used_at"])
    assert _has_index(CommunityEngagementSettings, ["community_id"])
    assert _has_index(EngagementTarget, ["community_id"])
    assert _has_index(EngagementTarget, ["status"])
    assert _has_index(EngagementTarget, ["submitted_ref"])
    assert _has_index(CommunityAccountMembership, ["community_id", "telegram_account_id"])
    assert _has_index(EngagementTopic, ["active"])
    assert _has_index(EngagementTopicEmbedding, ["topic_id"])
    assert _has_index(
        EngagementMessageEmbedding,
        ["community_id", "source_text_hash", "model", "dimensions"],
    )
    assert _has_index(EngagementMessageEmbedding, ["expires_at"])
    assert _has_index(EngagementCandidate, ["status", "created_at"])
    assert _has_index(EngagementCandidate, ["community_id", "topic_id", "status"])
    assert _has_index(EngagementAction, ["community_id", "created_at"])
    assert _has_index(EngagementAction, ["telegram_account_id", "created_at"])
    assert _has_index(EngagementPromptProfile, ["active"])
    assert _has_index(EngagementPromptProfileVersion, ["prompt_profile_id"])
    assert _has_index(EngagementStyleRule, ["scope_type", "scope_id", "active", "priority"])
    assert _has_index(EngagementCandidateRevision, ["candidate_id", "revision_number"])


def test_engagement_candidate_columns_include_timeliness_contract_fields() -> None:
    candidate_columns = EngagementCandidate.__table__.c

    assert "source_message_date" in candidate_columns
    assert "detected_at" in candidate_columns
    assert "moment_strength" in candidate_columns
    assert "timeliness" in candidate_columns
    assert "reply_value" in candidate_columns
    assert "review_deadline_at" in candidate_columns
    assert "reply_deadline_at" in candidate_columns
    assert "operator_notified_at" in candidate_columns


def test_engagement_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()

    for model in (
        CommunityEngagementSettings,
        EngagementTarget,
        CommunityAccountMembership,
        EngagementTopic,
        EngagementTopicEmbedding,
        EngagementMessageEmbedding,
        EngagementPromptProfile,
        EngagementPromptProfileVersion,
        EngagementStyleRule,
        EngagementCandidate,
        EngagementCandidateRevision,
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
