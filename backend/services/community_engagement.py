from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementMode,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementTopic,
    TelegramAccount,
)


class EngagementServiceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EngagementNotFound(EngagementServiceError):
    pass


class EngagementConflict(EngagementServiceError):
    pass


class EngagementValidationError(EngagementServiceError):
    pass


@dataclass(frozen=True)
class EngagementSettingsView:
    community_id: UUID
    mode: str
    allow_join: bool
    allow_post: bool
    reply_only: bool
    require_approval: bool
    max_posts_per_day: int
    min_minutes_between_posts: int
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    assigned_account_id: UUID | None
    created_at: datetime | None
    updated_at: datetime | None


async def get_engagement_settings(
    db: AsyncSession,
    community_id: UUID,
) -> EngagementSettingsView:
    community = await db.get(Community, community_id)
    if community is None:
        raise EngagementNotFound("not_found", "Community not found")

    settings = await db.scalar(
        select(CommunityEngagementSettings).where(
            CommunityEngagementSettings.community_id == community_id
        )
    )
    if settings is None:
        return _disabled_settings_view(community_id)
    return _settings_view(settings)


async def upsert_engagement_settings(
    db: AsyncSession,
    *,
    community_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementSettingsView:
    del updated_by
    community = await db.get(Community, community_id)
    if community is None:
        raise EngagementNotFound("not_found", "Community not found")

    values = _settings_values(payload)
    await _validate_settings_values(db, community, values)

    settings = await db.scalar(
        select(CommunityEngagementSettings).where(
            CommunityEngagementSettings.community_id == community_id
        )
    )
    now = _utcnow()
    if settings is None:
        settings = CommunityEngagementSettings(
            id=uuid.uuid4(),
            community_id=community_id,
            created_at=now,
        )
        db.add(settings)

    settings.mode = values["mode"]
    settings.allow_join = values["allow_join"]
    settings.allow_post = values["allow_post"]
    settings.reply_only = values["reply_only"]
    settings.require_approval = values["require_approval"]
    settings.max_posts_per_day = values["max_posts_per_day"]
    settings.min_minutes_between_posts = values["min_minutes_between_posts"]
    settings.quiet_hours_start = values["quiet_hours_start"]
    settings.quiet_hours_end = values["quiet_hours_end"]
    settings.assigned_account_id = values["assigned_account_id"]
    settings.updated_at = now
    await db.flush()
    return _settings_view(settings)


async def create_topic(db: AsyncSession, *, payload: Any) -> EngagementTopic:
    name = _required_text(payload.name, field="name")
    stance_guidance = _required_text(payload.stance_guidance, field="stance_guidance")
    trigger_keywords = normalize_keywords(payload.trigger_keywords)
    negative_keywords = normalize_keywords(payload.negative_keywords)
    example_good_replies = normalize_text_list(payload.example_good_replies)
    example_bad_replies = normalize_text_list(payload.example_bad_replies)

    validate_topic_policy(
        name=name,
        stance_guidance=stance_guidance,
        trigger_keywords=trigger_keywords,
        active=payload.active,
    )
    await _ensure_unique_topic_name(db, name)

    now = _utcnow()
    topic = EngagementTopic(
        id=uuid.uuid4(),
        name=name,
        description=_optional_text(payload.description),
        stance_guidance=stance_guidance,
        trigger_keywords=trigger_keywords,
        negative_keywords=negative_keywords,
        example_good_replies=example_good_replies,
        example_bad_replies=example_bad_replies,
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(topic)
    await db.flush()
    return topic


async def update_topic(db: AsyncSession, *, topic_id: UUID, payload: Any) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")

    next_name = topic.name
    next_description = topic.description
    next_guidance = topic.stance_guidance
    next_trigger_keywords = list(topic.trigger_keywords or [])
    next_negative_keywords = list(topic.negative_keywords or [])
    next_good_replies = list(topic.example_good_replies or [])
    next_bad_replies = list(topic.example_bad_replies or [])
    next_active = topic.active

    if _field_was_set(payload, "name"):
        next_name = _required_text(payload.name, field="name")
    if _field_was_set(payload, "description"):
        next_description = _optional_text(payload.description)
    if _field_was_set(payload, "stance_guidance"):
        next_guidance = _required_text(payload.stance_guidance, field="stance_guidance")
    if _field_was_set(payload, "trigger_keywords"):
        next_trigger_keywords = normalize_keywords(payload.trigger_keywords)
    if _field_was_set(payload, "negative_keywords"):
        next_negative_keywords = normalize_keywords(payload.negative_keywords)
    if _field_was_set(payload, "example_good_replies"):
        next_good_replies = normalize_text_list(payload.example_good_replies)
    if _field_was_set(payload, "example_bad_replies"):
        next_bad_replies = normalize_text_list(payload.example_bad_replies)
    if _field_was_set(payload, "active"):
        next_active = payload.active

    validate_topic_policy(
        name=next_name,
        stance_guidance=next_guidance,
        trigger_keywords=next_trigger_keywords,
        active=next_active,
    )
    if next_name.casefold() != topic.name.casefold():
        await _ensure_unique_topic_name(db, next_name, excluding_topic_id=topic_id)

    topic.name = next_name
    topic.description = next_description
    topic.stance_guidance = next_guidance
    topic.trigger_keywords = next_trigger_keywords
    topic.negative_keywords = next_negative_keywords
    topic.example_good_replies = next_good_replies
    topic.example_bad_replies = next_bad_replies
    topic.active = next_active
    topic.updated_at = _utcnow()
    await db.flush()
    return topic


async def list_active_topics(db: AsyncSession) -> list[EngagementTopic]:
    rows = await db.scalars(
        select(EngagementTopic).where(EngagementTopic.active.is_(True)).order_by(EngagementTopic.name)
    )
    return list(rows)


async def list_topics(db: AsyncSession) -> list[EngagementTopic]:
    rows = await db.scalars(select(EngagementTopic).order_by(EngagementTopic.name))
    return list(rows)


async def mark_join_requested(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership:
    now = _utcnow()
    membership = await _get_membership(
        db,
        community_id=community_id,
        telegram_account_id=telegram_account_id,
    )
    if membership is None:
        membership = CommunityAccountMembership(
            id=uuid.uuid4(),
            community_id=community_id,
            telegram_account_id=telegram_account_id,
            created_at=now,
        )
        db.add(membership)
    elif membership.status == CommunityAccountMembershipStatus.BANNED.value:
        raise EngagementValidationError(
            "membership_banned",
            "This account is banned from the community until an operator resets it",
        )

    membership.status = CommunityAccountMembershipStatus.JOIN_REQUESTED.value
    membership.last_checked_at = now
    membership.last_error = None
    membership.updated_at = now
    await db.flush()
    return membership


async def mark_join_result(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
    status: str,
    joined_at: datetime | None,
    error_message: str | None,
) -> CommunityAccountMembership:
    allowed_statuses = {
        CommunityAccountMembershipStatus.JOINED.value,
        CommunityAccountMembershipStatus.FAILED.value,
        CommunityAccountMembershipStatus.BANNED.value,
    }
    if status not in allowed_statuses:
        raise EngagementValidationError(
            "invalid_membership_status",
            "Join result status must be joined, failed, or banned",
        )

    now = _utcnow()
    membership = await _get_membership(
        db,
        community_id=community_id,
        telegram_account_id=telegram_account_id,
    )
    if membership is None:
        membership = CommunityAccountMembership(
            id=uuid.uuid4(),
            community_id=community_id,
            telegram_account_id=telegram_account_id,
            created_at=now,
        )
        db.add(membership)

    membership.status = status
    membership.joined_at = joined_at if status == CommunityAccountMembershipStatus.JOINED.value else None
    if status == CommunityAccountMembershipStatus.JOINED.value and membership.joined_at is None:
        membership.joined_at = now
    membership.last_checked_at = now
    membership.last_error = error_message
    membership.updated_at = now
    await db.flush()
    return membership


async def get_joined_membership_for_send(
    db: AsyncSession,
    *,
    community_id: UUID,
) -> CommunityAccountMembership | None:
    return await db.scalar(
        select(CommunityAccountMembership)
        .where(
            CommunityAccountMembership.community_id == community_id,
            CommunityAccountMembership.status == CommunityAccountMembershipStatus.JOINED.value,
        )
        .order_by(CommunityAccountMembership.joined_at.asc().nullslast())
        .limit(1)
    )


def normalize_keywords(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = " ".join(value.strip().casefold().split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized


def normalize_text_list(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        cleaned = " ".join(value.strip().split())
        if cleaned:
            normalized.append(cleaned)
    return normalized


def validate_topic_policy(
    *,
    name: str,
    stance_guidance: str,
    trigger_keywords: list[str],
    active: bool,
) -> None:
    _required_text(name, field="name")
    guidance = _required_text(stance_guidance, field="stance_guidance")
    if active and not trigger_keywords:
        raise EngagementValidationError(
            "topic_requires_trigger_keyword",
            "Active engagement topics require at least one trigger keyword",
        )

    lowered = guidance.casefold()
    disallowed_markers = (
        "deceive",
        "impersonate",
        "harass",
        "fake consensus",
        "evade moderation",
        "target individual",
        "target individuals",
    )
    for marker in disallowed_markers:
        if marker in lowered:
            raise EngagementValidationError(
                "unsafe_topic_guidance",
                "Topic guidance must not instruct deception, impersonation, harassment, "
                "individual targeting, fake consensus, or moderation evasion",
            )


def _settings_values(payload: Any) -> dict[str, Any]:
    mode = _enum_value(payload.mode)
    allow_join = bool(payload.allow_join)
    allow_post = bool(payload.allow_post)
    if mode == EngagementMode.DISABLED.value:
        allow_join = False
        allow_post = False

    return {
        "mode": mode,
        "allow_join": allow_join,
        "allow_post": allow_post,
        "reply_only": bool(payload.reply_only),
        "require_approval": bool(payload.require_approval),
        "max_posts_per_day": int(payload.max_posts_per_day),
        "min_minutes_between_posts": int(payload.min_minutes_between_posts),
        "quiet_hours_start": payload.quiet_hours_start,
        "quiet_hours_end": payload.quiet_hours_end,
        "assigned_account_id": payload.assigned_account_id,
    }


async def _validate_settings_values(
    db: AsyncSession,
    community: Community,
    values: dict[str, Any],
) -> None:
    if values["mode"] == EngagementMode.AUTO_LIMITED.value:
        raise EngagementValidationError(
            "auto_limited_not_enabled",
            "auto_limited engagement mode is not enabled in the MVP",
        )
    if values["require_approval"] is False:
        raise EngagementValidationError(
            "approval_required",
            "require_approval must remain true in the MVP",
        )
    if values["reply_only"] is False:
        raise EngagementValidationError(
            "reply_only_required",
            "reply_only must remain true in the MVP",
        )
    if not 0 <= values["max_posts_per_day"] <= 3:
        raise EngagementValidationError(
            "invalid_max_posts_per_day",
            "max_posts_per_day must be between 0 and 3 in the MVP",
        )
    if values["min_minutes_between_posts"] < 60:
        raise EngagementValidationError(
            "invalid_min_minutes_between_posts",
            "min_minutes_between_posts must be at least 60 in the MVP",
        )
    quiet_start = values["quiet_hours_start"]
    quiet_end = values["quiet_hours_end"]
    if (quiet_start is None) != (quiet_end is None):
        raise EngagementValidationError(
            "invalid_quiet_hours",
            "quiet_hours_start and quiet_hours_end must be provided together",
        )
    if values["allow_join"] or values["allow_post"]:
        if community.status not in {
            CommunityStatus.APPROVED.value,
            CommunityStatus.MONITORING.value,
        }:
            raise EngagementValidationError(
                "community_not_engagement_approved",
                "Only approved or monitoring communities may enable engagement joins or posts",
            )
    if values["assigned_account_id"] is not None:
        account = await db.get(TelegramAccount, values["assigned_account_id"])
        if account is None:
            raise EngagementValidationError(
                "assigned_account_not_found",
                "assigned_account_id must reference an existing Telegram account",
            )
        if account.status == AccountStatus.BANNED.value:
            raise EngagementValidationError(
                "assigned_account_banned",
                "assigned_account_id must not reference a banned Telegram account",
            )


async def _ensure_unique_topic_name(
    db: AsyncSession,
    name: str,
    *,
    excluding_topic_id: UUID | None = None,
) -> None:
    query = select(EngagementTopic).where(func.lower(EngagementTopic.name) == name.casefold())
    if excluding_topic_id is not None:
        query = query.where(EngagementTopic.id != excluding_topic_id)
    existing = await db.scalar(query.limit(1))
    if existing is not None:
        raise EngagementConflict(
            "topic_name_exists",
            "An engagement topic with this name already exists",
        )


def _settings_view(settings: CommunityEngagementSettings) -> EngagementSettingsView:
    return EngagementSettingsView(
        community_id=settings.community_id,
        mode=settings.mode,
        allow_join=settings.allow_join,
        allow_post=settings.allow_post,
        reply_only=settings.reply_only,
        require_approval=settings.require_approval,
        max_posts_per_day=settings.max_posts_per_day,
        min_minutes_between_posts=settings.min_minutes_between_posts,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        assigned_account_id=settings.assigned_account_id,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


async def _get_membership(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership | None:
    return await db.scalar(
        select(CommunityAccountMembership)
        .where(
            CommunityAccountMembership.community_id == community_id,
            CommunityAccountMembership.telegram_account_id == telegram_account_id,
        )
        .limit(1)
    )


def _disabled_settings_view(community_id: UUID) -> EngagementSettingsView:
    return EngagementSettingsView(
        community_id=community_id,
        mode=EngagementMode.DISABLED.value,
        allow_join=False,
        allow_post=False,
        reply_only=True,
        require_approval=True,
        max_posts_per_day=1,
        min_minutes_between_posts=240,
        quiet_hours_start=None,
        quiet_hours_end=None,
        assigned_account_id=None,
        created_at=None,
        updated_at=None,
    )


def _required_text(value: str | None, *, field: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        raise EngagementValidationError(f"{field}_required", f"{field} is required")
    return cleaned


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _field_was_set(payload: Any, field: str) -> bool:
    fields_set = getattr(payload, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(payload, "__fields_set__", set())
    return field in fields_set


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
