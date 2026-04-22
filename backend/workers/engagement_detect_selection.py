# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.workers.engagement_detect_types import *


async def _select_trigger_candidates(
    session: AsyncSession,
    *,
    community_id: object,
    topic: EngagementTopic,
    messages: list[DetectionMessage],
    runtime_settings: Settings,
    semantic_selector: SemanticSelector,
    semantic_observability: SemanticSelectionStats | None = None,
) -> list[TriggerCandidate]:
    if not messages:
        return []
    if runtime_settings.engagement_semantic_matching_enabled:
        semantic_matches = await semantic_selector(
            session,
            community_id=community_id,
            topic=topic,
            messages=messages,
            settings=runtime_settings,
            observability=semantic_observability,
        )
        if semantic_matches and semantic_observability is not None:
            semantic_observability.semantic_matches_selected = max(
                semantic_observability.semantic_matches_selected,
                len(semantic_matches),
            )
        if semantic_matches:
            return [
                TriggerCandidate(
                    message=_coerce_detection_message(match.message),
                    semantic_match=match,
                )
                for match in semantic_matches
            ]
        if not (topic.trigger_keywords or []):
            return []
        # Rollout fallback: only exact trigger keywords may rescue an empty semantic selection.
        fallback_messages = _prefilter_messages(topic, messages, require_trigger=True)
        return [TriggerCandidate(message=_select_source_message(fallback_messages))] if fallback_messages else []

    if not (topic.trigger_keywords or []):
        return []
    matching_messages = _prefilter_messages(topic, messages, require_trigger=True)
    return [TriggerCandidate(message=_select_source_message(matching_messages))] if matching_messages else []


async def _filter_existing_candidate_messages(
    session: AsyncSession,
    *,
    community_id: object,
    topic_id: object,
    messages: list[DetectionMessage],
) -> list[DetectionMessage]:
    filtered: list[DetectionMessage] = []
    for message in messages:
        if await _has_active_candidate_duplicate(
            session,
            community_id=community_id,
            topic_id=topic_id,
            source_tg_message_id=message.tg_message_id,
            source_excerpt=message.text,
        ):
            continue
        filtered.append(message)
    return filtered


async def _has_active_candidate_duplicate(
    session: AsyncSession,
    *,
    community_id: object,
    topic_id: object,
    source_tg_message_id: int | None,
    source_excerpt: str | None,
) -> bool:
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
            EngagementCandidate.source_excerpt == sanitize_candidate_excerpt(source_excerpt),
        )
    return await session.scalar(query.limit(1)) is not None


def _prefilter_messages(
    topic: EngagementTopic,
    messages: list[DetectionMessage],
    *,
    require_trigger: bool = False,
) -> list[DetectionMessage]:
    triggers = [keyword.casefold() for keyword in topic.trigger_keywords or [] if keyword]
    negatives = [keyword.casefold() for keyword in topic.negative_keywords or [] if keyword]
    if require_trigger and not triggers:
        return []
    matches: list[DetectionMessage] = []
    for message in messages:
        text = message.text.casefold()
        if (triggers or require_trigger) and not any(keyword in text for keyword in triggers):
            continue
        if negatives and any(keyword in text for keyword in negatives):
            continue
        matches.append(message)
    return matches


def _coerce_detection_message(message: object) -> DetectionMessage:
    if isinstance(message, DetectionMessage):
        return message
    return DetectionMessage(
        tg_message_id=getattr(message, "tg_message_id", None),
        text=str(getattr(message, "text", "") or ""),
        message_date=getattr(message, "message_date", None),
        reply_context=getattr(message, "reply_context", None),
        is_replyable=bool(getattr(message, "is_replyable", True)),
    )


def _select_source_message(
    messages: list[DetectionMessage],
    source_tg_message_id: int | None = None,
) -> DetectionMessage:
    if source_tg_message_id is not None:
        for message in messages:
            if message.tg_message_id == source_tg_message_id:
                return message
    return max(
        messages,
        key=lambda message: (
            _sortable_datetime(message.message_date),
            message.tg_message_id or -1,
        ),
    )


def _sortable_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _ensure_aware_utc(value)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

__all__ = [
    "_select_trigger_candidates",
    "_filter_existing_candidate_messages",
    "_has_active_candidate_duplicate",
    "_prefilter_messages",
]
