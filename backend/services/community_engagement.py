from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
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


@dataclass(frozen=True)
class EngagementCandidateCreationResult:
    candidate: EngagementCandidate
    created: bool
    reason: str


@dataclass(frozen=True)
class EngagementCandidateView:
    id: UUID
    community_id: UUID
    community_title: str | None
    topic_id: UUID
    topic_name: str
    source_tg_message_id: int | None
    source_excerpt: str | None
    detected_reason: str
    suggested_reply: str | None
    final_reply: str | None
    risk_notes: list[str]
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class EngagementCandidateListResult:
    items: list[EngagementCandidateView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementActionView:
    id: UUID
    candidate_id: UUID | None
    community_id: UUID
    telegram_account_id: UUID
    action_type: str
    status: str
    outbound_text: str | None
    reply_to_tg_message_id: int | None
    sent_tg_message_id: int | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True)
class EngagementActionListResult:
    items: list[EngagementActionView]
    limit: int
    offset: int
    total: int


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


async def list_engagement_candidates(
    db: AsyncSession,
    *,
    status: str | None = EngagementCandidateStatus.NEEDS_REVIEW.value,
    community_id: UUID | None = None,
    topic_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EngagementCandidateListResult:
    if status is not None and status not in _candidate_status_values():
        raise EngagementValidationError("invalid_candidate_status", "Unknown engagement candidate status")

    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    filters = []
    if status is not None:
        filters.append(EngagementCandidate.status == status)
    if community_id is not None:
        filters.append(EngagementCandidate.community_id == community_id)
    if topic_id is not None:
        filters.append(EngagementCandidate.topic_id == topic_id)

    total_query = select(func.count(EngagementCandidate.id))
    candidate_query = (
        select(EngagementCandidate)
        .options(
            joinedload(EngagementCandidate.community),
            joinedload(EngagementCandidate.topic),
        )
        .order_by(EngagementCandidate.created_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    if filters:
        total_query = total_query.where(*filters)
        candidate_query = candidate_query.where(*filters)

    total = int(await db.scalar(total_query) or 0)
    rows = await db.scalars(candidate_query)
    return EngagementCandidateListResult(
        items=[_candidate_view(candidate) for candidate in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def list_engagement_actions(
    db: AsyncSession,
    *,
    community_id: UUID | None = None,
    candidate_id: UUID | None = None,
    status: str | None = None,
    action_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EngagementActionListResult:
    if status is not None and status not in _action_status_values():
        raise EngagementValidationError(
            "invalid_engagement_action_status",
            "Unknown engagement action status",
        )
    if action_type is not None and action_type not in _action_type_values():
        raise EngagementValidationError(
            "invalid_engagement_action_type",
            "Unknown engagement action type",
        )

    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    filters = []
    if community_id is not None:
        filters.append(EngagementAction.community_id == community_id)
    if candidate_id is not None:
        filters.append(EngagementAction.candidate_id == candidate_id)
    if status is not None:
        filters.append(EngagementAction.status == status)
    if action_type is not None:
        filters.append(EngagementAction.action_type == action_type)

    total_query = select(func.count(EngagementAction.id))
    action_query = (
        select(EngagementAction)
        .order_by(EngagementAction.created_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    if filters:
        total_query = total_query.where(*filters)
        action_query = action_query.where(*filters)

    total = int(await db.scalar(total_query) or 0)
    rows = await db.scalars(action_query)
    return EngagementActionListResult(
        items=[_action_view(action) for action in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def approve_candidate(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    approved_by: str,
    final_reply: str | None = None,
) -> EngagementCandidateView:
    candidate = await _get_candidate_for_review(db, candidate_id)
    if candidate.status not in {
        EngagementCandidateStatus.NEEDS_REVIEW.value,
        EngagementCandidateStatus.FAILED.value,
    }:
        raise EngagementConflict(
            "candidate_not_approvable",
            "Only candidates needing review or failed candidates can be approved",
        )
    if _candidate_is_expired(candidate, _utcnow()):
        raise EngagementConflict("candidate_expired", "Expired candidates cannot be approved")

    reply_source = final_reply if final_reply is not None else candidate.suggested_reply
    reply = validate_suggested_reply(reply_source)
    if reply is None:
        raise EngagementValidationError(
            "final_reply_required",
            "A candidate needs suggested_reply or final_reply before approval",
        )

    now = _utcnow()
    candidate.status = EngagementCandidateStatus.APPROVED.value
    candidate.final_reply = reply
    candidate.reviewed_by = _required_text(approved_by, field="approved_by")
    candidate.reviewed_at = now
    candidate.updated_at = now
    await db.flush()
    return _candidate_view(candidate)


async def reject_candidate(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    rejected_by: str,
    reason: str | None = None,
) -> EngagementCandidateView:
    del reason
    candidate = await _get_candidate_for_review(db, candidate_id)
    if candidate.status != EngagementCandidateStatus.NEEDS_REVIEW.value:
        raise EngagementConflict(
            "candidate_not_rejectable",
            "Only candidates needing review can be rejected",
        )

    now = _utcnow()
    candidate.status = EngagementCandidateStatus.REJECTED.value
    candidate.reviewed_by = _required_text(rejected_by, field="rejected_by")
    candidate.reviewed_at = now
    candidate.updated_at = now
    await db.flush()
    return _candidate_view(candidate)


async def expire_stale_candidates(db: AsyncSession, *, now: datetime) -> int:
    rows = await db.scalars(
        select(EngagementCandidate).where(
            EngagementCandidate.status.in_(
                (
                    EngagementCandidateStatus.NEEDS_REVIEW.value,
                    EngagementCandidateStatus.APPROVED.value,
                )
            ),
            EngagementCandidate.expires_at <= now,
        )
    )
    count = 0
    for candidate in rows:
        candidate.status = EngagementCandidateStatus.EXPIRED.value
        candidate.updated_at = now
        count += 1
    if count:
        await db.flush()
    return count


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


async def create_engagement_candidate(
    db: AsyncSession,
    *,
    community_id: UUID,
    topic_id: UUID,
    source_tg_message_id: int | None,
    source_excerpt: str | None,
    detected_reason: str,
    suggested_reply: str | None,
    model: str | None,
    model_output: dict[str, Any] | None,
    risk_notes: list[str] | None,
    now: datetime | None = None,
) -> EngagementCandidateCreationResult:
    current_time = now or _utcnow()
    excerpt = sanitize_candidate_excerpt(source_excerpt)
    reason = _required_text(detected_reason, field="detected_reason")[:500]
    reply = validate_suggested_reply(suggested_reply)
    notes = normalize_text_list(risk_notes)[:8]

    existing = await _find_active_candidate_duplicate(
        db,
        community_id=community_id,
        topic_id=topic_id,
        source_tg_message_id=source_tg_message_id,
        source_excerpt=excerpt,
    )
    if existing is not None:
        return EngagementCandidateCreationResult(
            candidate=existing,
            created=False,
            reason="duplicate_active_candidate",
        )

    candidate = EngagementCandidate(
        id=uuid.uuid4(),
        community_id=community_id,
        topic_id=topic_id,
        source_tg_message_id=source_tg_message_id,
        source_excerpt=excerpt,
        detected_reason=reason,
        suggested_reply=reply,
        model=model,
        model_output=_compact_model_output(model_output),
        risk_notes=notes,
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        expires_at=current_time + timedelta(hours=24),
        created_at=current_time,
        updated_at=current_time,
    )
    db.add(candidate)
    await db.flush()
    return EngagementCandidateCreationResult(
        candidate=candidate,
        created=True,
        reason="created",
    )


def sanitize_candidate_excerpt(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    cleaned = _PHONE_RE.sub("[phone redacted]", cleaned)
    return cleaned[:500]


def validate_suggested_reply(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise EngagementValidationError("suggested_reply_required", "Suggested reply is required")
    if len(cleaned) > 800:
        raise EngagementValidationError(
            "suggested_reply_too_long",
            "Suggested reply must be 800 characters or fewer",
        )

    lowered = cleaned.casefold()
    disallowed_markers = (
        "dm me",
        "direct message me",
        "send me a dm",
        "pm me",
        "private message me",
        "as a customer",
        "as the founder",
        "as founder",
        "as a moderator",
        "everyone agrees",
        "guaranteed",
        "limited time",
    )
    for marker in disallowed_markers:
        if marker in lowered:
            raise EngagementValidationError(
                "unsafe_suggested_reply",
                "Suggested reply must not ask for DMs, impersonate a role, "
                "claim fake consensus, or use manipulative urgency",
            )
    if "http://" in lowered or "https://" in lowered:
        raise EngagementValidationError(
            "links_not_allowed",
            "Suggested reply links are not enabled in the MVP",
        )
    return cleaned


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


async def _find_active_candidate_duplicate(
    db: AsyncSession,
    *,
    community_id: UUID,
    topic_id: UUID,
    source_tg_message_id: int | None,
    source_excerpt: str | None,
) -> EngagementCandidate | None:
    active_statuses = (
        EngagementCandidateStatus.NEEDS_REVIEW.value,
        EngagementCandidateStatus.APPROVED.value,
    )
    query = select(EngagementCandidate).where(
        EngagementCandidate.community_id == community_id,
        EngagementCandidate.topic_id == topic_id,
        EngagementCandidate.status.in_(active_statuses),
    )
    if source_tg_message_id is not None:
        query = query.where(EngagementCandidate.source_tg_message_id == source_tg_message_id)
    else:
        query = query.where(
            EngagementCandidate.source_tg_message_id.is_(None),
            EngagementCandidate.source_excerpt == source_excerpt,
        )
    return await db.scalar(query.limit(1))


async def _get_candidate_for_review(
    db: AsyncSession,
    candidate_id: UUID,
) -> EngagementCandidate:
    candidate = await db.scalar(
        select(EngagementCandidate)
        .options(
            joinedload(EngagementCandidate.community),
            joinedload(EngagementCandidate.topic),
        )
        .where(EngagementCandidate.id == candidate_id)
        .limit(1)
    )
    if candidate is None:
        raise EngagementNotFound("not_found", "Engagement candidate not found")
    return candidate


def _candidate_view(candidate: EngagementCandidate) -> EngagementCandidateView:
    community = candidate.community
    topic = candidate.topic
    community_title = None
    if community is not None:
        community_title = community.title or community.username
    return EngagementCandidateView(
        id=candidate.id,
        community_id=candidate.community_id,
        community_title=community_title,
        topic_id=candidate.topic_id,
        topic_name=topic.name if topic is not None else "Unknown topic",
        source_tg_message_id=candidate.source_tg_message_id,
        source_excerpt=candidate.source_excerpt,
        detected_reason=candidate.detected_reason,
        suggested_reply=candidate.suggested_reply,
        final_reply=candidate.final_reply,
        risk_notes=list(candidate.risk_notes or []),
        status=candidate.status,
        reviewed_by=candidate.reviewed_by,
        reviewed_at=candidate.reviewed_at,
        expires_at=candidate.expires_at,
        created_at=candidate.created_at,
    )


def _action_view(action: EngagementAction) -> EngagementActionView:
    return EngagementActionView(
        id=action.id,
        candidate_id=action.candidate_id,
        community_id=action.community_id,
        telegram_account_id=action.telegram_account_id,
        action_type=action.action_type,
        status=action.status,
        outbound_text=action.outbound_text,
        reply_to_tg_message_id=action.reply_to_tg_message_id,
        sent_tg_message_id=action.sent_tg_message_id,
        scheduled_at=action.scheduled_at,
        sent_at=action.sent_at,
        error_message=action.error_message,
        created_at=action.created_at,
    )


def _candidate_is_expired(candidate: EngagementCandidate, now: datetime) -> bool:
    return _ensure_aware_utc(candidate.expires_at) <= _ensure_aware_utc(now)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _candidate_status_values() -> set[str]:
    return {status.value for status in EngagementCandidateStatus}


def _action_status_values() -> set[str]:
    return {status.value for status in EngagementActionStatus}


def _action_type_values() -> set[str]:
    return {action_type.value for action_type in EngagementActionType}


def _compact_model_output(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    allowed_keys = {
        "should_engage",
        "topic_match",
        "source_tg_message_id",
        "reason",
        "suggested_reply",
        "risk_notes",
    }
    return {key: value[key] for key in allowed_keys if key in value}


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


_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
