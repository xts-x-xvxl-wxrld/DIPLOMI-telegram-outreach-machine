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


async def summarize_semantic_rollout(
    db: AsyncSession,
    *,
    window_days: int = 14,
    community_id: UUID | None = None,
    topic_id: UUID | None = None,
    now: datetime | None = None,
) -> EngagementSemanticRolloutSummary:
    safe_window_days = max(min(int(window_days), 90), 1)
    cutoff = (now or _utcnow()) - timedelta(days=safe_window_days)
    filters = [EngagementCandidate.created_at >= cutoff]
    if community_id is not None:
        filters.append(EngagementCandidate.community_id == community_id)
    if topic_id is not None:
        filters.append(EngagementCandidate.topic_id == topic_id)

    rows = await db.scalars(
        select(EngagementCandidate)
        .where(*filters)
        .order_by(EngagementCandidate.created_at.desc())
    )
    candidates = [
        candidate
        for candidate in rows
        if _semantic_similarity(candidate) is not None
    ]
    band_stats = [_new_semantic_band_stats(*band) for band in _SEMANTIC_ROLLOUT_BANDS]
    overall = _new_rollout_stats()

    for candidate in candidates:
        similarity = _semantic_similarity(candidate)
        if similarity is None:
            continue
        _record_rollout_candidate(overall, candidate.status, similarity)
        for band in band_stats:
            if _similarity_in_band(similarity, band):
                _record_rollout_candidate(band, candidate.status, similarity)
                break

    return EngagementSemanticRolloutSummary(
        window_days=safe_window_days,
        community_id=community_id,
        topic_id=topic_id,
        total_semantic_candidates=overall["total"],
        reviewed_semantic_candidates=overall["approved"] + overall["rejected"],
        pending=overall["pending"],
        approved=overall["approved"],
        rejected=overall["rejected"],
        expired=overall["expired"],
        approval_rate=_approval_rate(overall),
        bands=[_semantic_band_view(band) for band in band_stats],
    )


def _action_status_values() -> set[str]:
    return {status.value for status in EngagementActionStatus}


def _action_type_values() -> set[str]:
    return {action_type.value for action_type in EngagementActionType}


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


def _approval_rate(stats: dict[str, Any]) -> float | None:
    reviewed = stats["approved"] + stats["rejected"]
    if reviewed <= 0:
        return None
    return round(stats["approved"] / reviewed, 4)


def _new_rollout_stats() -> dict[str, Any]:
    return {
        "total": 0,
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "expired": 0,
        "similarity_total": 0.0,
    }


def _new_semantic_band_stats(
    label: str,
    min_similarity: float,
    max_similarity: float,
) -> dict[str, Any]:
    stats = _new_rollout_stats()
    stats.update(
        {
            "label": label,
            "min_similarity": min_similarity,
            "max_similarity": max_similarity,
        }
    )
    return stats


def _record_rollout_candidate(stats: dict[str, Any], status: str, similarity: float) -> None:
    stats["total"] += 1
    stats["similarity_total"] += similarity
    if status == EngagementCandidateStatus.REJECTED.value:
        stats["rejected"] += 1
    elif status == EngagementCandidateStatus.EXPIRED.value:
        stats["expired"] += 1
    elif status == EngagementCandidateStatus.NEEDS_REVIEW.value:
        stats["pending"] += 1
    elif status in {
        EngagementCandidateStatus.APPROVED.value,
        EngagementCandidateStatus.SENT.value,
        EngagementCandidateStatus.FAILED.value,
    }:
        stats["approved"] += 1
    else:
        stats["pending"] += 1


def _semantic_band_view(band: dict[str, Any]) -> EngagementSemanticRolloutBand:
    return EngagementSemanticRolloutBand(
        label=str(band["label"]),
        min_similarity=float(band["min_similarity"]),
        max_similarity=float(band["max_similarity"]),
        total=int(band["total"]),
        pending=int(band["pending"]),
        approved=int(band["approved"]),
        rejected=int(band["rejected"]),
        expired=int(band["expired"]),
        approval_rate=_approval_rate(band),
        average_similarity=_average_similarity(band),
    )


def _semantic_similarity(candidate: EngagementCandidate) -> float | None:
    for container in (candidate.model_output, candidate.prompt_render_summary):
        if not isinstance(container, dict):
            continue
        semantic = container.get("semantic_match")
        if not isinstance(semantic, dict):
            continue
        value = semantic.get("similarity")
        try:
            similarity = float(value)
        except (TypeError, ValueError):
            continue
        if 0 <= similarity <= 1:
            return similarity
    return None


def _similarity_in_band(similarity: float, band: dict[str, Any]) -> bool:
    lower = float(band["min_similarity"])
    upper = float(band["max_similarity"])
    if upper >= 1.0:
        return lower <= similarity <= upper
    return lower <= similarity < upper


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _average_similarity(stats: dict[str, Any]) -> float | None:
    if stats["total"] <= 0:
        return None
    return round(stats["similarity_total"] / stats["total"], 4)

__all__ = [
    "list_engagement_actions",
    "summarize_semantic_rollout",
]
