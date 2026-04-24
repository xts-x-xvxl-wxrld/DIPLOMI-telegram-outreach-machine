# ruff: noqa: F401,F403,F405
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
from backend.services.community_engagement_views import *

_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_SEMANTIC_ROLLOUT_BANDS = (
    ("0.90-1.00", 0.90, 1.0),
    ("0.80-0.89", 0.80, 0.90),
    ("0.70-0.79", 0.70, 0.80),
    ("0.62-0.69", 0.62, 0.70),
    ("0.00-0.61", 0.00, 0.62),
)
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
    "source_post.text",
    "source_post.tg_message_id",
    "source_post.message_date",
    "reply_context",
    "messages",
    "community_context.latest_summary",
    "community_context.dominant_themes",
}

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


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _required_text(value: str | None, *, field: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        raise EngagementValidationError(f"{field}_required", f"{field} is required")
    return cleaned


def _target_view(target: EngagementTarget) -> EngagementTargetView:
    community = target.__dict__.get("community")
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _target_status_values() -> set[str]:
    return {status.value for status in EngagementTargetStatus}


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _field_was_set(payload: Any, field: str) -> bool:
    fields_set = getattr(payload, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(payload, "__fields_set__", set())
    return field in fields_set


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

__all__ = [
    "create_engagement_target",
    "list_engagement_targets",
    "get_engagement_target",
    "update_engagement_target",
    "has_engagement_target_permission",
    "resolve_engagement_target",
]
