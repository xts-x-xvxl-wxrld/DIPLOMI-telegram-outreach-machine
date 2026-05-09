# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.db.enums import EngagementActionStatus, EngagementActionType
from backend.db.models import EngagementAction
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
    selected_telegram_account_id: object | None = None,
) -> list[TriggerCandidate]:
    if not messages:
        return []
    continuation_candidates = await _select_direct_continuation_candidates(
        session,
        community_id=community_id,
        topic_id=topic.id,
        messages=messages,
        selected_telegram_account_id=selected_telegram_account_id,
    )
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
            semantic_candidates = [
                TriggerCandidate(
                    message=_coerce_detection_message(match.message),
                    semantic_match=match,
                )
                for match in semantic_matches
            ]
            return _merge_trigger_candidates(continuation_candidates, semantic_candidates)
        if not (topic.trigger_keywords or []):
            return continuation_candidates
        # Rollout fallback: only exact trigger keywords may rescue an empty semantic selection.
        fallback_messages = _prefilter_messages(topic, messages, require_trigger=True)
        fallback_candidates = (
            [TriggerCandidate(message=_select_source_message(fallback_messages))]
            if fallback_messages
            else []
        )
        return _merge_trigger_candidates(continuation_candidates, fallback_candidates)

    if not (topic.trigger_keywords or []):
        return continuation_candidates
    matching_messages = _prefilter_messages(topic, messages, require_trigger=True)
    matching_candidates = (
        [TriggerCandidate(message=_select_source_message(matching_messages))]
        if matching_messages
        else []
    )
    return _merge_trigger_candidates(continuation_candidates, matching_candidates)


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


async def _select_direct_continuation_candidates(
    session: AsyncSession,
    *,
    community_id: object,
    topic_id: object,
    messages: list[DetectionMessage],
    selected_telegram_account_id: object | None,
) -> list[TriggerCandidate]:
    if selected_telegram_account_id is None:
        return []
    reply_targets = {
        message.reply_to_tg_message_id
        for message in messages
        if message.reply_to_tg_message_id is not None
    }
    if not reply_targets:
        return []
    sent_actions = list(
        await session.scalars(
        select(EngagementAction)
        .join(EngagementCandidate, EngagementAction.candidate_id == EngagementCandidate.id)
        .where(
            EngagementAction.community_id == community_id,
            EngagementAction.telegram_account_id == selected_telegram_account_id,
            EngagementAction.action_type == EngagementActionType.REPLY.value,
            EngagementAction.status == EngagementActionStatus.SENT.value,
            EngagementAction.sent_tg_message_id.in_(tuple(reply_targets)),
            EngagementCandidate.topic_id == topic_id,
        )
        .order_by(
            EngagementAction.sent_at.desc().nullslast(),
            EngagementAction.created_at.desc(),
        )
    )
    )
    actions_by_reply_target = {
        int(action.sent_tg_message_id): action
        for action in sent_actions
        if getattr(action, "sent_tg_message_id", None) is not None
    }
    if not actions_by_reply_target:
        return []
    continuation_candidates: list[TriggerCandidate] = []
    for message in _sort_detection_messages(messages):
        reply_target = message.reply_to_tg_message_id
        if reply_target is None or reply_target not in actions_by_reply_target:
            continue
        action = actions_by_reply_target[reply_target]
        continuation_candidates.append(
            TriggerCandidate(
                message=message,
                thread_context=_build_thread_prompt_context(
                    source_message=message,
                    messages=messages,
                    previous_reply_text=str(getattr(action, "outbound_text", "") or ""),
                    managed_reply_tg_message_id=reply_target,
                ),
            )
        )
    return continuation_candidates


def _coerce_detection_message(message: object) -> DetectionMessage:
    if isinstance(message, DetectionMessage):
        return message
    return DetectionMessage(
        tg_message_id=getattr(message, "tg_message_id", None),
        text=str(getattr(message, "text", "") or ""),
        message_date=getattr(message, "message_date", None),
        reply_to_tg_message_id=getattr(message, "reply_to_tg_message_id", None),
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
    return _sort_detection_messages(messages)[0]


def _merge_trigger_candidates(
    primary: list[TriggerCandidate],
    secondary: list[TriggerCandidate],
) -> list[TriggerCandidate]:
    merged: list[TriggerCandidate] = []
    seen: set[tuple[int | None, str, datetime | None]] = set()
    for candidate in [*primary, *secondary]:
        key = _trigger_candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    return merged


def _trigger_candidate_key(candidate: TriggerCandidate) -> tuple[int | None, str, datetime | None]:
    return (
        candidate.message.tg_message_id,
        candidate.message.text,
        candidate.message.message_date,
    )


def _sort_detection_messages(messages: list[DetectionMessage]) -> list[DetectionMessage]:
    return sorted(
        messages,
        key=lambda message: (
            _sortable_datetime(message.message_date),
            message.tg_message_id or -1,
        ),
        reverse=True,
    )


def _build_thread_prompt_context(
    *,
    source_message: DetectionMessage,
    messages: list[DetectionMessage],
    previous_reply_text: str,
    managed_reply_tg_message_id: int,
) -> ThreadPromptContext:
    stage = _infer_thread_stage(source_message.text)
    recent_replies = [
        message.text
        for message in _recent_thread_replies(
            messages,
            source_message=source_message,
            managed_reply_tg_message_id=managed_reply_tg_message_id,
        )
    ]
    return ThreadPromptContext(
        stage=stage,
        objective=_thread_objective(stage),
        unresolved_question=_unresolved_question(source_message.text),
        avoid_repeating=[
            "Do not restate the full previous managed reply.",
            "Do not restart the recommendation from zero.",
        ],
        last_managed_reply=previous_reply_text or None,
        recent_replies=recent_replies,
        summary=_thread_summary(
            source_message=source_message,
            recent_replies=recent_replies,
            previous_reply_text=previous_reply_text,
        ),
    )


def _recent_thread_replies(
    messages: list[DetectionMessage],
    *,
    source_message: DetectionMessage,
    managed_reply_tg_message_id: int,
) -> list[DetectionMessage]:
    related = [
        message
        for message in _sort_detection_messages(messages)
        if (
            message.reply_to_tg_message_id == managed_reply_tg_message_id
            or message.tg_message_id == source_message.tg_message_id
        )
    ]
    return related[:4]


def _infer_thread_stage(text: str) -> str:
    normalized = text.casefold()
    if any(marker in normalized for marker in ("tell me more", "what was the case", "example", "case", "details")):
        return "provide_example"
    if any(marker in normalized for marker in ("vs", "versus", "difference", "compare", "better than")):
        return "compare"
    if any(marker in normalized for marker in ("not sure", "sounds", "seems", "concern", "problem", "issue", "but ")):
        return "answer_objection"
    if "?" in text:
        return "clarify"
    return "narrow_discussion"


def _thread_objective(stage: str) -> str:
    objectives = {
        "clarify": "Answer the latest question clearly and keep the thread moving.",
        "compare": "Add one grounded comparison point without restarting the full pitch.",
        "answer_objection": "Address the concern directly and reduce friction in the public thread.",
        "provide_example": "Give one concrete example or case detail that supports the earlier point.",
        "narrow_discussion": "Add one useful next step that narrows the conversation naturally.",
    }
    return objectives.get(stage, "Move the thread forward by one useful public reply.")


def _unresolved_question(text: str) -> str | None:
    cleaned = " ".join(text.strip().split())
    if "?" not in cleaned:
        return None
    return cleaned[:280]


def _thread_summary(
    *,
    source_message: DetectionMessage,
    recent_replies: list[str],
    previous_reply_text: str,
) -> str:
    if recent_replies:
        return (
            "The managed account already replied in this thread. "
            f"The latest public follow-up is: {source_message.text[:160]} "
            f"There are {len(recent_replies)} recent public follow-up replies in the sampled thread context."
        )
    if previous_reply_text:
        return (
            "The managed account already replied in this thread and the newest public message is a follow-up "
            "to that earlier reply."
        )
    return "This is an ongoing public thread; continue it without restarting the outreach."


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
