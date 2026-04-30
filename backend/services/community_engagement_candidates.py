# ruff: noqa: F401,F403,F405
from __future__ import annotations

import uuid
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
from backend.services.engagement_opportunity_cadence import classify_candidate_opportunity, conversation_key
from backend.services.engagement_candidate_timing import (
    DEFAULT_REPLY_DEADLINE_MINUTES,
    calculate_reply_deadline_at,
    calculate_review_deadline_at,
    ensure_aware_utc,
    infer_candidate_timeliness,
    normalize_moment_strength,
    normalize_reply_value,
)

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
    "source_post.reply_to_tg_message_id",
    "source_post.message_date",
    "reply_context",
    "messages",
    "community_context.latest_summary",
    "community_context.dominant_themes",
}
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


async def get_engagement_candidate(
    db: AsyncSession,
    *,
    candidate_id: UUID,
) -> EngagementCandidateView:
    candidate = await _get_candidate_for_review(db, candidate_id)
    return _candidate_view(candidate)


async def list_candidate_revisions(
    db: AsyncSession,
    *,
    candidate_id: UUID,
) -> list[EngagementCandidateRevisionView]:
    await _get_candidate_for_review(db, candidate_id)
    rows = await db.scalars(
        select(EngagementCandidateRevision)
        .where(EngagementCandidateRevision.candidate_id == candidate_id)
        .order_by(EngagementCandidateRevision.revision_number.desc())
    )
    return [_candidate_revision_view(revision) for revision in rows]


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
    if _candidate_is_stale(candidate, _utcnow()):
        raise EngagementConflict("candidate_stale", "Stale reply opportunities cannot be approved")

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


async def expire_candidate(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    expired_by: str,
) -> EngagementCandidateView:
    del expired_by
    candidate = await _get_candidate_for_review(db, candidate_id)
    if candidate.status in {
        EngagementCandidateStatus.SENT.value,
        EngagementCandidateStatus.REJECTED.value,
        EngagementCandidateStatus.EXPIRED.value,
    }:
        raise EngagementConflict(
            "candidate_not_expirable",
            "Sent, rejected, and already expired candidates cannot be expired",
        )

    now = _utcnow()
    candidate.status = EngagementCandidateStatus.EXPIRED.value
    candidate.updated_at = now
    await db.flush()
    return _candidate_view(candidate)


async def retry_candidate(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    retried_by: str,
) -> EngagementCandidateView:
    del retried_by
    candidate = await _get_candidate_for_review(db, candidate_id)
    if candidate.status != EngagementCandidateStatus.FAILED.value:
        raise EngagementConflict(
            "candidate_not_retryable",
            "Only failed candidates can be retried",
        )
    if _candidate_is_expired(candidate, _utcnow()):
        raise EngagementConflict("candidate_expired", "Expired candidates cannot be retried")

    now = _utcnow()
    candidate.status = EngagementCandidateStatus.NEEDS_REVIEW.value
    candidate.reviewed_by = None
    candidate.reviewed_at = None
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


async def create_engagement_candidate(
    db: AsyncSession,
    *,
    community_id: UUID,
    topic_id: UUID,
    source_tg_message_id: int | None,
    source_excerpt: str | None,
    source_message_date: datetime | None,
    detected_reason: str,
    suggested_reply: str | None,
    moment_strength: str | None,
    reply_value: str | None,
    model: str | None,
    model_output: dict[str, Any] | None,
    risk_notes: list[str] | None,
    source_reply_to_tg_message_id: int | None = None,
    prompt_profile_id: UUID | None = None,
    prompt_profile_version_id: UUID | None = None,
    prompt_render_summary: dict[str, Any] | None = None,
    detected_at: datetime | None = None,
    operator_notified_at: datetime | None = None,
    reply_deadline_minutes: int = DEFAULT_REPLY_DEADLINE_MINUTES,
    selected_telegram_account_id: UUID | None = None,
    now: datetime | None = None,
) -> EngagementCandidateCreationResult:
    current_time = now or detected_at or _utcnow()
    excerpt = sanitize_candidate_excerpt(source_excerpt)
    reason = _required_text(detected_reason, field="detected_reason")[:500]
    reply = validate_suggested_reply(suggested_reply)
    notes = normalize_text_list(risk_notes)[:8]
    normalized_detected_at = ensure_aware_utc(detected_at or current_time)
    normalized_source_message_date = (
        ensure_aware_utc(source_message_date)
        if source_message_date is not None
        else None
    )
    reply_deadline_at = calculate_reply_deadline_at(
        source_message_date=normalized_source_message_date,
        detected_at=normalized_detected_at,
        reply_deadline_minutes=reply_deadline_minutes,
    )
    review_deadline_at = calculate_review_deadline_at(
        source_message_date=normalized_source_message_date,
        reply_deadline_at=reply_deadline_at,
    )
    timeliness = infer_candidate_timeliness(
        detected_at=normalized_detected_at,
        review_deadline_at=review_deadline_at,
        reply_deadline_at=reply_deadline_at,
    )
    normalized_moment_strength = normalize_moment_strength(moment_strength)
    normalized_reply_value = normalize_reply_value(reply_value, has_reply=reply is not None)

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

    opportunity = await classify_candidate_opportunity(
        db,
        community_id=community_id,
        selected_telegram_account_id=selected_telegram_account_id,
        source_reply_to_tg_message_id=source_reply_to_tg_message_id,
    )
    candidate = EngagementCandidate(
        id=uuid.uuid4(),
        community_id=community_id,
        topic_id=topic_id,
        source_tg_message_id=source_tg_message_id,
        source_reply_to_tg_message_id=source_reply_to_tg_message_id,
        source_excerpt=excerpt,
        source_message_date=normalized_source_message_date,
        opportunity_kind=opportunity.kind,
        root_candidate_id=opportunity.root_candidate_id,
        conversation_key=conversation_key(
            community_id=community_id,
            root_candidate_id=opportunity.root_candidate_id,
            source_tg_message_id=source_tg_message_id,
            source_excerpt=excerpt,
        ),
        detected_at=normalized_detected_at,
        detected_reason=reason,
        moment_strength=normalized_moment_strength,
        timeliness=timeliness,
        reply_value=normalized_reply_value,
        suggested_reply=reply,
        model=model,
        model_output=_compact_model_output(model_output),
        prompt_profile_id=prompt_profile_id,
        prompt_profile_version_id=prompt_profile_version_id,
        prompt_render_summary=_compact_prompt_render_summary(prompt_render_summary),
        risk_notes=notes,
        status=EngagementCandidateStatus.NEEDS_REVIEW.value,
        review_deadline_at=review_deadline_at,
        reply_deadline_at=reply_deadline_at,
        operator_notified_at=(
            ensure_aware_utc(operator_notified_at)
            if operator_notified_at is not None
            else None
        ),
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
        source_reply_to_tg_message_id=candidate.source_reply_to_tg_message_id,
        source_excerpt=candidate.source_excerpt,
        source_message_date=candidate.source_message_date,
        opportunity_kind=candidate.opportunity_kind,
        root_candidate_id=candidate.root_candidate_id,
        conversation_key=candidate.conversation_key,
        detected_at=candidate.detected_at,
        detected_reason=candidate.detected_reason,
        moment_strength=candidate.moment_strength,
        timeliness=candidate.timeliness,
        reply_value=candidate.reply_value,
        suggested_reply=candidate.suggested_reply,
        final_reply=candidate.final_reply,
        prompt_profile_id=candidate.prompt_profile_id,
        prompt_profile_version_id=candidate.prompt_profile_version_id,
        prompt_render_summary=candidate.prompt_render_summary,
        risk_notes=list(candidate.risk_notes or []),
        status=candidate.status,
        reviewed_by=candidate.reviewed_by,
        reviewed_at=candidate.reviewed_at,
        review_deadline_at=candidate.review_deadline_at,
        reply_deadline_at=candidate.reply_deadline_at,
        operator_notified_at=candidate.operator_notified_at,
        expires_at=candidate.expires_at,
        created_at=candidate.created_at,
    )


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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _candidate_revision_view(
    revision: EngagementCandidateRevision,
) -> EngagementCandidateRevisionView:
    return EngagementCandidateRevisionView(
        id=revision.id,
        candidate_id=revision.candidate_id,
        revision_number=revision.revision_number,
        reply_text=revision.reply_text,
        edited_by=revision.edited_by,
        edit_reason=revision.edit_reason,
        created_at=revision.created_at,
    )


def _candidate_status_values() -> set[str]:
    return {status.value for status in EngagementCandidateStatus}


def _candidate_is_expired(candidate: EngagementCandidate, now: datetime) -> bool:
    return ensure_aware_utc(candidate.expires_at) <= ensure_aware_utc(now)


def _candidate_is_stale(candidate: EngagementCandidate, now: datetime) -> bool:
    deadline = getattr(candidate, "reply_deadline_at", None)
    if deadline is None:
        return False
    return ensure_aware_utc(deadline) <= ensure_aware_utc(now)


def _compact_model_output(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    allowed_keys = {
        "should_engage",
        "topic_match",
        "source_tg_message_id",
        "reason",
        "moment_strength",
        "timeliness",
        "reply_value",
        "suggested_reply",
        "risk_notes",
        "semantic_match",
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
        "source_post_present",
        "serialized_input_bytes",
        "semantic_match",
    }
    return {key: value[key] for key in allowed_keys if key in value}


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


def normalize_text_list(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        cleaned = " ".join(value.strip().split())
        if cleaned:
            normalized.append(cleaned)
    return normalized


__all__ = [
    "edit_candidate_reply",
    "get_engagement_candidate",
    "list_candidate_revisions",
    "list_engagement_candidates",
    "approve_candidate",
    "reject_candidate",
    "expire_candidate",
    "retry_candidate",
    "expire_stale_candidates",
    "create_engagement_candidate",
    "sanitize_candidate_excerpt",
    "validate_suggested_reply",
]
