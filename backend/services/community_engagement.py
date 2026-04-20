from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    AccountPool,
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunitySource,
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStyleRuleScope,
    EngagementTargetRefType,
    EngagementTargetStatus,
    TelegramEntityIntakeStatus,
    TelegramEntityType,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementCandidateRevision,
    EngagementPromptProfile,
    EngagementPromptProfileVersion,
    EngagementStyleRule,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)
from backend.services.seed_import import normalize_telegram_seed
from backend.services.seed_resolution import TransientResolveError
from backend.services.telegram_entity_intake import (
    TelegramEntityInfo,
    TelegramEntityResolveOutcome,
    TelegramEntityResolverAdapter,
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
class EngagementTargetView:
    id: UUID
    community_id: UUID | None
    community_title: str | None
    submitted_ref: str
    submitted_ref_type: str
    status: str
    allow_join: bool
    allow_detect: bool
    allow_post: bool
    notes: str | None
    added_by: str
    approved_by: str | None
    approved_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EngagementTargetListResult:
    items: list[EngagementTargetView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementTargetResolveSummary:
    target_id: UUID
    status: str
    community_id: UUID | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "job_type": "engagement_target.resolve",
            "target_id": str(self.target_id),
            "community_id": str(self.community_id) if self.community_id else None,
            "error_message": self.error_message,
        }


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
    prompt_profile_id: UUID | None
    prompt_profile_version_id: UUID | None
    prompt_render_summary: dict[str, Any] | None
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


@dataclass(frozen=True)
class EngagementPromptProfileView:
    id: UUID
    name: str
    description: str | None
    active: bool
    model: str
    temperature: Decimal
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    current_version_number: int | None
    current_version_id: UUID | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EngagementPromptProfileListResult:
    items: list[EngagementPromptProfileView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class EngagementPromptProfileVersionView:
    id: UUID
    prompt_profile_id: UUID
    version_number: int
    model: str
    temperature: Decimal
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class EngagementPromptPreview:
    profile_id: UUID | None
    profile_name: str
    version_id: UUID | None
    version_number: int | None
    model: str
    temperature: Decimal
    max_output_tokens: int
    system_prompt: str
    user_prompt_template: str
    rendered_user_prompt: str
    variables: dict[str, Any]


@dataclass(frozen=True)
class EngagementStyleRuleView:
    id: UUID
    scope_type: str
    scope_id: UUID | None
    name: str
    rule_text: str
    active: bool
    priority: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EngagementStyleRuleListResult:
    items: list[EngagementStyleRuleView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class PromptProfileSelection:
    profile: EngagementPromptProfile | None
    version: EngagementPromptProfileVersion | None
    fallback: EngagementPromptPreview | None = None


@dataclass(frozen=True)
class StyleRuleBundle:
    global_rules: list[str]
    account_rules: list[str]
    community_rules: list[str]
    topic_rules: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "global": self.global_rules,
            "account": self.account_rules,
            "community": self.community_rules,
            "topic": self.topic_rules,
        }


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


async def create_engagement_target(
    db: AsyncSession,
    *,
    target_ref: str,
    added_by: str,
    notes: str | None = None,
) -> EngagementTargetView:
    ref = _normalize_engagement_target_ref(target_ref)
    community: Community | None = None
    if ref["community_id"] is not None:
        community = await db.get(Community, ref["community_id"])
        if community is None:
            raise EngagementNotFound("community_not_found", "Community not found")

        existing = await db.scalar(
            select(EngagementTarget).where(EngagementTarget.community_id == community.id)
        )
        if existing is not None:
            if notes is not None:
                existing.notes = _optional_text(notes)
                existing.updated_at = _utcnow()
                await db.flush()
            return _target_view(existing)

    existing_by_ref = await db.scalar(
        select(EngagementTarget).where(EngagementTarget.submitted_ref == ref["submitted_ref"])
    )
    if existing_by_ref is not None:
        if notes is not None:
            existing_by_ref.notes = _optional_text(notes)
            existing_by_ref.updated_at = _utcnow()
            await db.flush()
        return _target_view(existing_by_ref)

    now = _utcnow()
    target = EngagementTarget(
        id=uuid.uuid4(),
        community_id=ref["community_id"],
        submitted_ref=ref["submitted_ref"],
        submitted_ref_type=ref["submitted_ref_type"],
        status=EngagementTargetStatus.RESOLVED.value
        if ref["community_id"] is not None
        else EngagementTargetStatus.PENDING.value,
        allow_join=False,
        allow_detect=False,
        allow_post=False,
        notes=_optional_text(notes),
        added_by=_required_text(added_by, field="added_by"),
        created_at=now,
        updated_at=now,
    )
    if community is not None:
        target.community = community
    db.add(target)
    await db.flush()
    return _target_view(target)


async def list_engagement_targets(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EngagementTargetListResult:
    if status is not None and status not in _target_status_values():
        raise EngagementValidationError("invalid_target_status", "Unknown engagement target status")

    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    filters = []
    if status is not None:
        filters.append(EngagementTarget.status == status)

    total_query = select(func.count(EngagementTarget.id))
    target_query = (
        select(EngagementTarget)
        .options(joinedload(EngagementTarget.community))
        .order_by(EngagementTarget.created_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    if filters:
        total_query = total_query.where(*filters)
        target_query = target_query.where(*filters)

    total = int(await db.scalar(total_query) or 0)
    rows = await db.scalars(target_query)
    return EngagementTargetListResult(
        items=[_target_view(target) for target in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def get_engagement_target(db: AsyncSession, target_id: UUID) -> EngagementTargetView:
    target = await db.scalar(
        select(EngagementTarget)
        .options(joinedload(EngagementTarget.community))
        .where(EngagementTarget.id == target_id)
        .limit(1)
    )
    if target is None:
        raise EngagementNotFound("target_not_found", "Engagement target not found")
    return _target_view(target)


async def update_engagement_target(
    db: AsyncSession,
    *,
    target_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementTargetView:
    target = await db.scalar(
        select(EngagementTarget)
        .options(joinedload(EngagementTarget.community))
        .where(EngagementTarget.id == target_id)
        .limit(1)
    )
    if target is None:
        raise EngagementNotFound("target_not_found", "Engagement target not found")

    next_status = target.status
    if _field_was_set(payload, "status") and payload.status is not None:
        next_status = _enum_value(payload.status)
    if next_status not in _target_status_values():
        raise EngagementValidationError("invalid_target_status", "Unknown engagement target status")

    if next_status == EngagementTargetStatus.APPROVED.value and target.community_id is None:
        raise EngagementConflict(
            "target_not_resolved",
            "Engagement target must resolve to a community before approval",
        )

    if _field_was_set(payload, "allow_join") and payload.allow_join is not None:
        target.allow_join = bool(payload.allow_join)
    if _field_was_set(payload, "allow_detect") and payload.allow_detect is not None:
        target.allow_detect = bool(payload.allow_detect)
    if _field_was_set(payload, "allow_post") and payload.allow_post is not None:
        target.allow_post = bool(payload.allow_post)
    if _field_was_set(payload, "notes"):
        target.notes = _optional_text(payload.notes)

    target.status = next_status
    if next_status == EngagementTargetStatus.APPROVED.value:
        target.approved_by = _required_text(updated_by, field="approved_by")
        target.approved_at = _utcnow()
        target.last_error = None
    elif next_status in {
        EngagementTargetStatus.REJECTED.value,
        EngagementTargetStatus.ARCHIVED.value,
    }:
        target.allow_join = False
        target.allow_detect = False
        target.allow_post = False
    target.updated_at = _utcnow()
    await db.flush()
    return _target_view(target)


async def has_engagement_target_permission(
    db: AsyncSession,
    *,
    community_id: UUID,
    permission: str,
) -> bool:
    if permission not in {"join", "detect", "post"}:
        raise EngagementValidationError("invalid_target_permission", "Unknown engagement target permission")

    target = await db.scalar(
        select(EngagementTarget)
        .where(
            EngagementTarget.community_id == community_id,
            EngagementTarget.status == EngagementTargetStatus.APPROVED.value,
        )
        .limit(1)
    )
    if target is None:
        return False
    if permission == "join":
        return bool(target.allow_join)
    if permission == "detect":
        return bool(target.allow_detect)
    return bool(target.allow_post)


async def resolve_engagement_target(
    db: AsyncSession,
    *,
    target_id: UUID,
    resolver: TelegramEntityResolverAdapter,
) -> EngagementTargetResolveSummary:
    target = await db.get(EngagementTarget, target_id)
    if target is None:
        raise EngagementNotFound("target_not_found", "Engagement target not found")
    if target.status in {
        EngagementTargetStatus.APPROVED.value,
        EngagementTargetStatus.REJECTED.value,
        EngagementTargetStatus.ARCHIVED.value,
    }:
        return EngagementTargetResolveSummary(
            target_id=target.id,
            status=target.status,
            community_id=target.community_id,
            error_message=target.last_error,
        )
    if target.community_id is not None:
        target.status = EngagementTargetStatus.RESOLVED.value
        target.last_error = None
        target.updated_at = _utcnow()
        await db.flush()
        return EngagementTargetResolveSummary(
            target_id=target.id,
            status=target.status,
            community_id=target.community_id,
        )

    username = _username_from_submitted_ref(target.submitted_ref)
    if username is None:
        return await _mark_target_failed(db, target, "Engagement target reference is not resolvable")

    try:
        outcome = await resolver.resolve_entity(username)
    except TransientResolveError as exc:
        outcome = TelegramEntityResolveOutcome.failed(str(exc))

    if outcome.status != TelegramEntityIntakeStatus.RESOLVED.value or outcome.entity is None:
        return await _mark_target_failed(
            db,
            target,
            outcome.error_message or "Engagement target could not be resolved",
        )
    if outcome.entity.entity_type not in {TelegramEntityType.CHANNEL, TelegramEntityType.GROUP}:
        return await _mark_target_failed(db, target, "Resolved target is not a community")

    community = await _upsert_engagement_target_community(db, target, outcome.entity)
    target.community_id = community.id
    target.status = EngagementTargetStatus.RESOLVED.value
    target.last_error = None
    target.updated_at = _utcnow()
    await db.flush()
    return EngagementTargetResolveSummary(
        target_id=target.id,
        status=target.status,
        community_id=community.id,
    )


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


async def add_topic_example(
    db: AsyncSession,
    *,
    topic_id: UUID,
    example_type: str,
    example: str,
) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")
    cleaned = _required_text(example, field="example")
    if example_type == "good":
        topic.example_good_replies = [*(topic.example_good_replies or []), cleaned]
    elif example_type == "bad":
        topic.example_bad_replies = [*(topic.example_bad_replies or []), cleaned]
    else:
        raise EngagementValidationError("invalid_example_type", "Example type must be good or bad")
    topic.updated_at = _utcnow()
    await db.flush()
    return topic


async def remove_topic_example(
    db: AsyncSession,
    *,
    topic_id: UUID,
    example_type: str,
    index: int,
) -> EngagementTopic:
    topic = await db.get(EngagementTopic, topic_id)
    if topic is None:
        raise EngagementNotFound("not_found", "Engagement topic not found")
    if example_type == "good":
        values = list(topic.example_good_replies or [])
    elif example_type == "bad":
        values = list(topic.example_bad_replies or [])
    else:
        raise EngagementValidationError("invalid_example_type", "Example type must be good or bad")
    if index < 0 or index >= len(values):
        raise EngagementNotFound("example_not_found", "Topic example not found")
    values.pop(index)
    if example_type == "good":
        topic.example_good_replies = values
    else:
        topic.example_bad_replies = values
    topic.updated_at = _utcnow()
    await db.flush()
    return topic


async def create_prompt_profile(
    db: AsyncSession,
    *,
    payload: Any,
    created_by: str,
) -> EngagementPromptProfileView:
    values = _prompt_profile_values(payload)
    now = _utcnow()
    profile = EngagementPromptProfile(
        id=uuid.uuid4(),
        name=values["name"],
        description=values["description"],
        active=False,
        model=values["model"],
        temperature=values["temperature"],
        max_output_tokens=values["max_output_tokens"],
        system_prompt=values["system_prompt"],
        user_prompt_template=values["user_prompt_template"],
        output_schema_name=values["output_schema_name"],
        created_by=_required_text(created_by, field="created_by"),
        updated_by=_required_text(created_by, field="updated_by"),
        created_at=now,
        updated_at=now,
    )
    db.add(profile)
    version = _new_prompt_version(profile, version_number=1, created_by=created_by, now=now)
    db.add(version)
    if bool(getattr(payload, "active", False)):
        await _deactivate_other_prompt_profiles(db, profile.id)
        profile.active = True
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def list_prompt_profiles(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
) -> EngagementPromptProfileListResult:
    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    total = int(await db.scalar(select(func.count(EngagementPromptProfile.id))) or 0)
    rows = await db.scalars(
        select(EngagementPromptProfile)
        .order_by(EngagementPromptProfile.active.desc(), EngagementPromptProfile.updated_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    return EngagementPromptProfileListResult(
        items=[await _prompt_profile_view(db, profile) for profile in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def get_prompt_profile(db: AsyncSession, profile_id: UUID) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    return await _prompt_profile_view(db, profile)


async def update_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    values = _prompt_profile_values(payload, current=profile)
    _validate_prompt_template(values["user_prompt_template"])

    profile.name = values["name"]
    profile.description = values["description"]
    profile.model = values["model"]
    profile.temperature = values["temperature"]
    profile.max_output_tokens = values["max_output_tokens"]
    profile.system_prompt = values["system_prompt"]
    profile.user_prompt_template = values["user_prompt_template"]
    profile.output_schema_name = values["output_schema_name"]
    profile.updated_by = _required_text(updated_by, field="updated_by")
    profile.updated_at = _utcnow()
    version = _new_prompt_version(
        profile,
        version_number=await _next_prompt_version_number(db, profile.id),
        created_by=updated_by,
        now=profile.updated_at,
    )
    db.add(version)
    if _field_was_set(payload, "active") and bool(payload.active):
        await _deactivate_other_prompt_profiles(db, profile.id)
        profile.active = True
    elif _field_was_set(payload, "active"):
        profile.active = bool(payload.active)
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def activate_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    updated_by: str,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    await _deactivate_other_prompt_profiles(db, profile_id)
    profile.active = True
    profile.updated_by = _required_text(updated_by, field="updated_by")
    profile.updated_at = _utcnow()
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def duplicate_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    created_by: str,
    name: str | None = None,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    now = _utcnow()
    copy = EngagementPromptProfile(
        id=uuid.uuid4(),
        name=_required_text(name, field="name") if name else f"{profile.name} copy",
        description=profile.description,
        active=False,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        output_schema_name=profile.output_schema_name,
        created_by=_required_text(created_by, field="created_by"),
        updated_by=_required_text(created_by, field="updated_by"),
        created_at=now,
        updated_at=now,
    )
    db.add(copy)
    db.add(_new_prompt_version(copy, version_number=1, created_by=created_by, now=now))
    await db.flush()
    return await _prompt_profile_view(db, copy)


async def rollback_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID,
    version_id: UUID,
    updated_by: str,
) -> EngagementPromptProfileView:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    version = await db.scalar(
        select(EngagementPromptProfileVersion).where(
            EngagementPromptProfileVersion.id == version_id,
            EngagementPromptProfileVersion.prompt_profile_id == profile_id,
        )
    )
    if version is None:
        raise EngagementNotFound("prompt_profile_version_not_found", "Prompt profile version not found")
    profile.model = version.model
    profile.temperature = version.temperature
    profile.max_output_tokens = version.max_output_tokens
    profile.system_prompt = version.system_prompt
    profile.user_prompt_template = version.user_prompt_template
    profile.output_schema_name = version.output_schema_name
    profile.updated_by = _required_text(updated_by, field="updated_by")
    profile.updated_at = _utcnow()
    db.add(
        _new_prompt_version(
            profile,
            version_number=await _next_prompt_version_number(db, profile.id),
            created_by=updated_by,
            now=profile.updated_at,
        )
    )
    await db.flush()
    return await _prompt_profile_view(db, profile)


async def list_prompt_profile_versions(
    db: AsyncSession,
    *,
    profile_id: UUID,
) -> list[EngagementPromptProfileVersionView]:
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    rows = await db.scalars(
        select(EngagementPromptProfileVersion)
        .where(EngagementPromptProfileVersion.prompt_profile_id == profile_id)
        .order_by(EngagementPromptProfileVersion.version_number.desc())
    )
    return [_prompt_version_view(row) for row in rows]


async def select_active_prompt_profile(db: AsyncSession) -> PromptProfileSelection:
    profile = await db.scalar(
        select(EngagementPromptProfile)
        .where(EngagementPromptProfile.active.is_(True))
        .order_by(EngagementPromptProfile.updated_at.desc(), EngagementPromptProfile.id.desc())
        .limit(1)
    )
    if profile is None:
        return PromptProfileSelection(
            profile=None,
            version=None,
            fallback=_default_prompt_preview(),
        )
    version = await _latest_prompt_version(db, profile.id)
    return PromptProfileSelection(profile=profile, version=version)


async def preview_prompt_profile(
    db: AsyncSession,
    *,
    profile_id: UUID | None,
    variables: dict[str, Any] | None = None,
) -> EngagementPromptPreview:
    if profile_id is None:
        default = _default_prompt_preview()
        return _render_prompt_preview(default, variables or _synthetic_prompt_variables())
    profile = await db.get(EngagementPromptProfile, profile_id)
    if profile is None:
        raise EngagementNotFound("prompt_profile_not_found", "Engagement prompt profile not found")
    latest = await _latest_prompt_version(db, profile.id)
    preview = EngagementPromptPreview(
        profile_id=profile.id,
        profile_name=profile.name,
        version_id=latest.id if latest is not None else None,
        version_number=latest.version_number if latest is not None else None,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        rendered_user_prompt="",
        variables={},
    )
    return _render_prompt_preview(preview, variables or _synthetic_prompt_variables())


async def list_style_rules(
    db: AsyncSession,
    *,
    scope_type: str | None = None,
    scope_id: UUID | None = None,
    active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EngagementStyleRuleListResult:
    safe_limit = max(min(limit, 100), 1)
    safe_offset = max(offset, 0)
    filters = []
    if scope_type is not None:
        _validate_style_scope(scope_type, scope_id, allow_missing_scope_id=True)
        filters.append(EngagementStyleRule.scope_type == scope_type)
    if scope_id is not None:
        filters.append(EngagementStyleRule.scope_id == scope_id)
    if active is not None:
        filters.append(EngagementStyleRule.active.is_(active))
    total_query = select(func.count(EngagementStyleRule.id))
    query = (
        select(EngagementStyleRule)
        .order_by(EngagementStyleRule.scope_type, EngagementStyleRule.priority, EngagementStyleRule.created_at)
        .limit(safe_limit)
        .offset(safe_offset)
    )
    if filters:
        total_query = total_query.where(*filters)
        query = query.where(*filters)
    total = int(await db.scalar(total_query) or 0)
    rows = await db.scalars(query)
    return EngagementStyleRuleListResult(
        items=[_style_rule_view(rule) for rule in rows],
        limit=safe_limit,
        offset=safe_offset,
        total=total,
    )


async def create_style_rule(
    db: AsyncSession,
    *,
    payload: Any,
    created_by: str,
) -> EngagementStyleRuleView:
    scope_type = str(payload.scope_type)
    _validate_style_scope(scope_type, payload.scope_id)
    rule_text = _required_text(payload.rule_text, field="rule_text")
    _validate_safe_admin_text(rule_text, code_prefix="style_rule")
    now = _utcnow()
    rule = EngagementStyleRule(
        id=uuid.uuid4(),
        scope_type=scope_type,
        scope_id=payload.scope_id,
        name=_required_text(payload.name, field="name"),
        rule_text=rule_text,
        active=bool(payload.active),
        priority=int(payload.priority),
        created_by=_required_text(created_by, field="created_by"),
        updated_by=_required_text(created_by, field="updated_by"),
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    await db.flush()
    return _style_rule_view(rule)


async def update_style_rule(
    db: AsyncSession,
    *,
    rule_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementStyleRuleView:
    rule = await db.get(EngagementStyleRule, rule_id)
    if rule is None:
        raise EngagementNotFound("style_rule_not_found", "Engagement style rule not found")
    scope_type = rule.scope_type
    scope_id = rule.scope_id
    if _field_was_set(payload, "scope_type") and payload.scope_type is not None:
        scope_type = str(payload.scope_type)
    if _field_was_set(payload, "scope_id"):
        scope_id = payload.scope_id
    _validate_style_scope(scope_type, scope_id)
    if _field_was_set(payload, "name") and payload.name is not None:
        rule.name = _required_text(payload.name, field="name")
    if _field_was_set(payload, "rule_text") and payload.rule_text is not None:
        rule_text = _required_text(payload.rule_text, field="rule_text")
        _validate_safe_admin_text(rule_text, code_prefix="style_rule")
        rule.rule_text = rule_text
    if _field_was_set(payload, "active") and payload.active is not None:
        rule.active = bool(payload.active)
    if _field_was_set(payload, "priority") and payload.priority is not None:
        rule.priority = int(payload.priority)
    rule.scope_type = scope_type
    rule.scope_id = scope_id
    rule.updated_by = _required_text(updated_by, field="updated_by")
    rule.updated_at = _utcnow()
    await db.flush()
    return _style_rule_view(rule)


async def list_active_style_rules_for_prompt(
    db: AsyncSession,
    *,
    account_id: UUID | None,
    community_id: UUID,
    topic_id: UUID,
) -> StyleRuleBundle:
    scope_filters = [
        (EngagementStyleRule.scope_type == EngagementStyleRuleScope.GLOBAL.value)
        & EngagementStyleRule.scope_id.is_(None),
        (EngagementStyleRule.scope_type == EngagementStyleRuleScope.COMMUNITY.value)
        & (EngagementStyleRule.scope_id == community_id),
        (EngagementStyleRule.scope_type == EngagementStyleRuleScope.TOPIC.value)
        & (EngagementStyleRule.scope_id == topic_id),
    ]
    if account_id is not None:
        scope_filters.append(
            (EngagementStyleRule.scope_type == EngagementStyleRuleScope.ACCOUNT.value)
            & (EngagementStyleRule.scope_id == account_id)
        )
    rows = await db.scalars(
        select(EngagementStyleRule)
        .where(EngagementStyleRule.active.is_(True), *scope_filters[:1])
        .order_by(EngagementStyleRule.priority, EngagementStyleRule.created_at)
    )
    global_rules = [rule.rule_text for rule in rows]

    async def _scope_rules(scope_type: str, scope_id_value: UUID | None) -> list[str]:
        if scope_id_value is None:
            return []
        scoped = await db.scalars(
            select(EngagementStyleRule)
            .where(
                EngagementStyleRule.active.is_(True),
                EngagementStyleRule.scope_type == scope_type,
                EngagementStyleRule.scope_id == scope_id_value,
            )
            .order_by(EngagementStyleRule.priority, EngagementStyleRule.created_at)
        )
        return [rule.rule_text for rule in scoped]

    return StyleRuleBundle(
        global_rules=global_rules,
        account_rules=await _scope_rules(EngagementStyleRuleScope.ACCOUNT.value, account_id),
        community_rules=await _scope_rules(EngagementStyleRuleScope.COMMUNITY.value, community_id),
        topic_rules=await _scope_rules(EngagementStyleRuleScope.TOPIC.value, topic_id),
    )


async def edit_candidate_reply(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    final_reply: str,
    edited_by: str,
    edit_reason: str | None = None,
) -> EngagementCandidateView:
    candidate = await _get_candidate_for_review(db, candidate_id)
    if candidate.status in {
        EngagementCandidateStatus.SENT.value,
        EngagementCandidateStatus.REJECTED.value,
        EngagementCandidateStatus.EXPIRED.value,
    }:
        raise EngagementConflict(
            "candidate_not_editable",
            "Sent, rejected, and expired candidates cannot be edited",
        )
    reply = validate_suggested_reply(final_reply)
    if reply is None:
        raise EngagementValidationError("final_reply_required", "Final reply is required")
    revision_number = await _next_candidate_revision_number(db, candidate_id)
    now = _utcnow()
    revision = EngagementCandidateRevision(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        revision_number=revision_number,
        reply_text=reply,
        edited_by=_required_text(edited_by, field="edited_by"),
        edit_reason=_optional_text(edit_reason),
        created_at=now,
    )
    db.add(revision)
    candidate.final_reply = reply
    candidate.updated_at = now
    await db.flush()
    return _candidate_view(candidate)


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

    reply_source = final_reply if final_reply is not None else candidate.final_reply or candidate.suggested_reply
    reply = validate_suggested_reply(reply_source)
    if reply is None:
        raise EngagementValidationError(
            "final_reply_required",
            "A candidate needs suggested_reply or final_reply before approval",
        )

    now = _utcnow()
    candidate.status = EngagementCandidateStatus.APPROVED.value
    if final_reply is not None:
        revision = EngagementCandidateRevision(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            revision_number=await _next_candidate_revision_number(db, candidate.id),
            reply_text=reply,
            edited_by=_required_text(approved_by, field="edited_by"),
            edit_reason="approval override",
            created_at=now,
        )
        db.add(revision)
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
        .join(TelegramAccount, CommunityAccountMembership.telegram_account_id == TelegramAccount.id)
        .where(
            CommunityAccountMembership.community_id == community_id,
            CommunityAccountMembership.status == CommunityAccountMembershipStatus.JOINED.value,
            TelegramAccount.account_pool == AccountPool.ENGAGEMENT.value,
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
    prompt_profile_id: UUID | None = None,
    prompt_profile_version_id: UUID | None = None,
    prompt_render_summary: dict[str, Any] | None = None,
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
        prompt_profile_id=prompt_profile_id,
        prompt_profile_version_id=prompt_profile_version_id,
        prompt_render_summary=_compact_prompt_render_summary(prompt_render_summary),
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


def _normalize_engagement_target_ref(raw_value: str) -> dict[str, Any]:
    cleaned = _required_text(raw_value, field="target_ref")
    try:
        community_id = UUID(cleaned)
    except ValueError:
        community_id = None
    if community_id is not None:
        return {
            "community_id": community_id,
            "submitted_ref": str(community_id),
            "submitted_ref_type": EngagementTargetRefType.COMMUNITY_ID.value,
        }

    lowered = cleaned.casefold()
    if "t.me/+" in lowered or "telegram.me/+" in lowered or "/joinchat/" in lowered:
        return {
            "community_id": None,
            "submitted_ref": cleaned,
            "submitted_ref_type": EngagementTargetRefType.INVITE_LINK.value,
        }

    try:
        normalized = normalize_telegram_seed(cleaned)
    except ValueError as exc:
        raise EngagementValidationError("invalid_target_ref", str(exc)) from exc

    is_link = "t.me/" in lowered or "telegram.me/" in lowered or lowered.startswith(("http://", "https://"))
    return {
        "community_id": None,
        "submitted_ref": normalized.normalized_key,
        "submitted_ref_type": EngagementTargetRefType.TELEGRAM_LINK.value
        if is_link
        else EngagementTargetRefType.TELEGRAM_USERNAME.value,
    }


def _target_view(target: EngagementTarget) -> EngagementTargetView:
    community = target.community
    community_title = None
    if community is not None:
        community_title = community.title or community.username
    return EngagementTargetView(
        id=target.id,
        community_id=target.community_id,
        community_title=community_title,
        submitted_ref=target.submitted_ref,
        submitted_ref_type=target.submitted_ref_type,
        status=target.status,
        allow_join=target.allow_join,
        allow_detect=target.allow_detect,
        allow_post=target.allow_post,
        notes=target.notes,
        added_by=target.added_by,
        approved_by=target.approved_by,
        approved_at=target.approved_at,
        last_error=target.last_error,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


async def _mark_target_failed(
    db: AsyncSession,
    target: EngagementTarget,
    error_message: str,
) -> EngagementTargetResolveSummary:
    target.status = EngagementTargetStatus.FAILED.value
    target.last_error = error_message
    target.updated_at = _utcnow()
    await db.flush()
    return EngagementTargetResolveSummary(
        target_id=target.id,
        status=target.status,
        community_id=target.community_id,
        error_message=target.last_error,
    )


async def _upsert_engagement_target_community(
    db: AsyncSession,
    target: EngagementTarget,
    resolved: TelegramEntityInfo,
) -> Community:
    community = await db.scalar(select(Community).where(Community.tg_id == resolved.tg_id))
    if community is None:
        community = Community(
            id=uuid.uuid4(),
            tg_id=resolved.tg_id,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
        db.add(community)

    community.username = resolved.username or _username_from_submitted_ref(target.submitted_ref) or community.username
    community.title = resolved.title or community.title
    if resolved.description is not None:
        community.description = resolved.description
    if resolved.member_count is not None:
        community.member_count = resolved.member_count
    community.is_group = bool(resolved.is_group)
    community.is_broadcast = bool(resolved.is_broadcast)
    community.source = CommunitySource.MANUAL.value
    community.match_reason = f"Engagement target intake: {target.submitted_ref}"
    if not community.status:
        community.status = CommunityStatus.CANDIDATE.value
    return community


def _username_from_submitted_ref(value: str) -> str | None:
    if value.startswith("username:"):
        return value.split(":", 1)[1]
    try:
        return normalize_telegram_seed(value).username
    except ValueError:
        return None


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
        if account.account_pool != AccountPool.ENGAGEMENT.value:
            raise EngagementValidationError(
                "assigned_account_wrong_pool",
                "assigned_account_id must reference an engagement Telegram account",
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
        prompt_profile_id=candidate.prompt_profile_id,
        prompt_profile_version_id=candidate.prompt_profile_version_id,
        prompt_render_summary=candidate.prompt_render_summary,
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


async def _prompt_profile_view(
    db: AsyncSession,
    profile: EngagementPromptProfile,
) -> EngagementPromptProfileView:
    latest = await _latest_prompt_version(db, profile.id)
    return EngagementPromptProfileView(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        active=profile.active,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        output_schema_name=profile.output_schema_name,
        current_version_number=latest.version_number if latest is not None else None,
        current_version_id=latest.id if latest is not None else None,
        created_by=profile.created_by,
        updated_by=profile.updated_by,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _prompt_version_view(version: EngagementPromptProfileVersion) -> EngagementPromptProfileVersionView:
    return EngagementPromptProfileVersionView(
        id=version.id,
        prompt_profile_id=version.prompt_profile_id,
        version_number=version.version_number,
        model=version.model,
        temperature=version.temperature,
        max_output_tokens=version.max_output_tokens,
        system_prompt=version.system_prompt,
        user_prompt_template=version.user_prompt_template,
        output_schema_name=version.output_schema_name,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _style_rule_view(rule: EngagementStyleRule) -> EngagementStyleRuleView:
    return EngagementStyleRuleView(
        id=rule.id,
        scope_type=rule.scope_type,
        scope_id=rule.scope_id,
        name=rule.name,
        rule_text=rule.rule_text,
        active=rule.active,
        priority=rule.priority,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


async def _latest_prompt_version(
    db: AsyncSession,
    profile_id: UUID,
) -> EngagementPromptProfileVersion | None:
    return await db.scalar(
        select(EngagementPromptProfileVersion)
        .where(EngagementPromptProfileVersion.prompt_profile_id == profile_id)
        .order_by(EngagementPromptProfileVersion.version_number.desc())
        .limit(1)
    )


async def _next_prompt_version_number(db: AsyncSession, profile_id: UUID) -> int:
    value = await db.scalar(
        select(func.max(EngagementPromptProfileVersion.version_number)).where(
            EngagementPromptProfileVersion.prompt_profile_id == profile_id
        )
    )
    try:
        return int(value or 0) + 1
    except (TypeError, ValueError):
        return 1


def _new_prompt_version(
    profile: EngagementPromptProfile,
    *,
    version_number: int,
    created_by: str,
    now: datetime,
) -> EngagementPromptProfileVersion:
    return EngagementPromptProfileVersion(
        id=uuid.uuid4(),
        prompt_profile_id=profile.id,
        version_number=version_number,
        model=profile.model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        system_prompt=profile.system_prompt,
        user_prompt_template=profile.user_prompt_template,
        output_schema_name=profile.output_schema_name,
        created_by=_required_text(created_by, field="created_by"),
        created_at=now,
    )


async def _deactivate_other_prompt_profiles(db: AsyncSession, active_profile_id: UUID) -> None:
    rows = await db.scalars(
        select(EngagementPromptProfile).where(
            EngagementPromptProfile.id != active_profile_id,
            EngagementPromptProfile.active.is_(True),
        )
    )
    now = _utcnow()
    for profile in rows:
        profile.active = False
        profile.updated_at = now


def _prompt_profile_values(payload: Any, current: EngagementPromptProfile | None = None) -> dict[str, Any]:
    name = current.name if current is not None else None
    description = current.description if current is not None else None
    model = current.model if current is not None else None
    temperature = current.temperature if current is not None else Decimal("0.2")
    max_output_tokens = current.max_output_tokens if current is not None else 1000
    system_prompt = current.system_prompt if current is not None else None
    user_prompt_template = current.user_prompt_template if current is not None else None
    output_schema_name = current.output_schema_name if current is not None else "engagement_detection_v1"

    if current is None or _field_was_set(payload, "name"):
        name = _required_text(payload.name, field="name")
    if current is None or _field_was_set(payload, "description"):
        description = _optional_text(payload.description)
    if (current is None or _field_was_set(payload, "model")) and payload.model is not None:
        model = _required_text(payload.model, field="model")
    if (current is None or _field_was_set(payload, "temperature")) and payload.temperature is not None:
        temperature = Decimal(str(payload.temperature))
    if (
        current is None or _field_was_set(payload, "max_output_tokens")
    ) and payload.max_output_tokens is not None:
        max_output_tokens = int(payload.max_output_tokens)
    if (current is None or _field_was_set(payload, "system_prompt")) and payload.system_prompt is not None:
        system_prompt = _required_text(payload.system_prompt, field="system_prompt")
    if (
        current is None or _field_was_set(payload, "user_prompt_template")
    ) and payload.user_prompt_template is not None:
        user_prompt_template = _required_multiline_text(
            payload.user_prompt_template,
            field="user_prompt_template",
        )
    if (
        current is None or _field_was_set(payload, "output_schema_name")
    ) and payload.output_schema_name is not None:
        output_schema_name = _required_text(payload.output_schema_name, field="output_schema_name")

    assert name is not None
    assert model is not None
    assert system_prompt is not None
    assert user_prompt_template is not None
    assert output_schema_name is not None
    if temperature < Decimal("0") or temperature > Decimal("2"):
        raise EngagementValidationError("invalid_temperature", "Prompt profile temperature must be 0-2")
    if max_output_tokens < 128 or max_output_tokens > 4000:
        raise EngagementValidationError(
            "invalid_max_output_tokens",
            "Prompt profile max output tokens must be between 128 and 4000",
        )
    _validate_safe_admin_text(system_prompt, code_prefix="prompt")
    _validate_prompt_template(user_prompt_template)
    return {
        "name": name,
        "description": description,
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "system_prompt": system_prompt,
        "user_prompt_template": user_prompt_template,
        "output_schema_name": output_schema_name,
    }


def _validate_style_scope(
    scope_type: str,
    scope_id: UUID | None,
    *,
    allow_missing_scope_id: bool = False,
) -> None:
    allowed = {item.value for item in EngagementStyleRuleScope}
    if scope_type not in allowed:
        raise EngagementValidationError("invalid_style_scope", "Unknown engagement style rule scope")
    if scope_type == EngagementStyleRuleScope.GLOBAL.value:
        if scope_id is not None:
            raise EngagementValidationError("invalid_style_scope_id", "Global style rules cannot have scope_id")
        return
    if scope_id is None and not allow_missing_scope_id:
        raise EngagementValidationError("style_scope_id_required", "Non-global style rules require scope_id")


async def _next_candidate_revision_number(db: AsyncSession, candidate_id: UUID) -> int:
    value = await db.scalar(
        select(func.max(EngagementCandidateRevision.revision_number)).where(
            EngagementCandidateRevision.candidate_id == candidate_id
        )
    )
    try:
        return int(value or 0) + 1
    except (TypeError, ValueError):
        return 1


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


def _target_status_values() -> set[str]:
    return {status.value for status in EngagementTargetStatus}


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


def _compact_prompt_render_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    allowed_keys = {
        "profile_name",
        "version_number",
        "style_rule_counts",
        "message_count",
        "serialized_input_bytes",
    }
    return {key: value[key] for key in allowed_keys if key in value}


def _default_prompt_preview() -> EngagementPromptPreview:
    return EngagementPromptPreview(
        profile_id=None,
        profile_name="Default engagement prompt",
        version_id=None,
        version_number=None,
        model="default",
        temperature=Decimal("0.2"),
        max_output_tokens=1000,
        system_prompt=(
            "You draft transparent, helpful public replies for an approved operator account. "
            "Prefer no reply over a weak reply."
        ),
        user_prompt_template=(
            "Community: {{community.title}} (@{{community.username}})\n"
            "Topic: {{topic.name}}\n"
            "Guidance: {{topic.stance_guidance}}\n"
            "Good examples: {{topic.example_good_replies}}\n"
            "Bad examples to avoid: {{topic.example_bad_replies}}\n"
            "Global style: {{style.global}}\n"
            "Account style: {{style.account}}\n"
            "Community style: {{style.community}}\n"
            "Messages: {{messages}}\n"
            "Community context: {{community_context.latest_summary}}\n"
            "Themes: {{community_context.dominant_themes}}"
        ),
        rendered_user_prompt="",
        variables={},
    )


def _render_prompt_preview(
    preview: EngagementPromptPreview,
    variables: dict[str, Any],
) -> EngagementPromptPreview:
    _validate_prompt_template(preview.user_prompt_template)
    rendered = _render_template(preview.user_prompt_template, variables)
    return EngagementPromptPreview(
        profile_id=preview.profile_id,
        profile_name=preview.profile_name,
        version_id=preview.version_id,
        version_number=preview.version_number,
        model=preview.model,
        temperature=preview.temperature,
        max_output_tokens=preview.max_output_tokens,
        system_prompt=preview.system_prompt,
        user_prompt_template=preview.user_prompt_template,
        rendered_user_prompt=rendered,
        variables=variables,
    )


def render_prompt_template(template: str, variables: dict[str, Any]) -> str:
    _validate_prompt_template(template)
    return _render_template(template, variables)


def _render_template(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = _lookup_template_variable(variables, key)
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        if isinstance(value, dict):
            return str(value)
        return "" if value is None else str(value)

    return _TEMPLATE_RE.sub(replace, template)


def _lookup_template_variable(variables: dict[str, Any], key: str) -> Any:
    current: Any = variables
    for part in key.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _validate_prompt_template(template: str) -> None:
    for match in _TEMPLATE_RE.finditer(template):
        key = match.group(1).strip()
        if key not in _ALLOWED_PROMPT_VARIABLES:
            raise EngagementValidationError(
                "invalid_prompt_variable",
                f"Prompt template variable is not allowed: {key}",
            )


def _synthetic_prompt_variables() -> dict[str, Any]:
    return {
        "community": {
            "title": "Example Operators",
            "username": "example_operators",
            "description": "A public group discussing SaaS operations.",
        },
        "topic": {
            "name": "Open-source CRM",
            "description": "CRM tooling discussions",
            "stance_guidance": "Be factual, brief, and non-salesy.",
            "trigger_keywords": ["crm", "open source"],
            "negative_keywords": [],
            "example_good_replies": ["Compare data ownership, integrations, and exit paths first."],
            "example_bad_replies": ["Buy our tool now."],
        },
        "style": {
            "global": ["Keep replies public and useful."],
            "account": [],
            "community": ["Keep replies under 3 sentences."],
            "topic": ["Discuss practical evaluation criteria."],
        },
        "messages": [
            {
                "tg_message_id": 123,
                "text": "Has anyone compared open-source CRM options?",
                "message_date": "2026-04-20T10:00:00+00:00",
            }
        ],
        "community_context": {
            "latest_summary": "Members compare sales and support tooling.",
            "dominant_themes": ["crm", "automation"],
        },
    }


def _validate_safe_admin_text(value: str, *, code_prefix: str) -> None:
    lowered = value.casefold()
    disallowed_markers = (
        "ask for dm",
        "ask users to dm",
        "move to dm",
        "send them a direct message",
        "pretend to be",
        "act like a normal member",
        "create fake consensus",
        "make fake consensus",
        "hidden sponsorship",
        "evade moderation",
        "harass",
        "target individual",
        "target individuals",
    )
    for marker in disallowed_markers:
        if marker in lowered and f"do not {marker}" not in lowered and f"don't {marker}" not in lowered:
            raise EngagementValidationError(
                f"unsafe_{code_prefix}",
                "Admin-controlled engagement text cannot permit DMs, impersonation, "
                "hidden sponsorship, harassment, fake consensus, or moderation evasion",
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


def _required_multiline_text(value: str | None, *, field: str) -> str:
    cleaned = (value or "").strip()
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
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_ALLOWED_PROMPT_VARIABLES = {
    "community.title",
    "community.username",
    "community.description",
    "topic.name",
    "topic.description",
    "topic.stance_guidance",
    "topic.trigger_keywords",
    "topic.negative_keywords",
    "topic.example_good_replies",
    "topic.example_bad_replies",
    "style.global",
    "style.account",
    "style.community",
    "style.topic",
    "messages",
    "community_context.latest_summary",
    "community_context.dominant_themes",
}
