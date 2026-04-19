from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.enums import CollectionRunStatus, EngagementMode
from backend.db.models import AnalysisSummary, CollectionRun, Community, EngagementTopic, Message
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import EngagementDetectPayload
from backend.services.community_engagement import (
    EngagementCandidateCreationResult,
    EngagementServiceError,
    EngagementValidationError,
    create_engagement_candidate,
    get_engagement_settings,
    has_engagement_target_permission,
    list_active_topics,
    sanitize_candidate_excerpt,
)


MAX_MESSAGES_PER_MODEL_CALL = 20
MAX_MESSAGE_CHARS = 500
MAX_MODEL_INPUT_BYTES = 64 * 1024


DETECTION_INSTRUCTIONS = """You draft transparent, helpful public replies for an approved operator account.
Do not impersonate a normal community member.
Do not create urgency, deception, fake consensus, or claims of personal experience.
Do not target, profile, rank, or evaluate individual people.
Do not suggest direct messages.
Do not mention private/internal analysis.
Only produce a reply when it is genuinely useful and relevant.
Prefer no reply over a weak reply."""


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


@dataclass(frozen=True)
class DetectionMessage:
    tg_message_id: int | None
    text: str
    message_date: datetime | None
    reply_context: str | None = None


@dataclass(frozen=True)
class CommunityContext:
    latest_summary: str | None
    dominant_themes: list[str]


class EngagementDetectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_engage: bool
    topic_match: str | None = None
    source_tg_message_id: int | None = None
    reason: str = ""
    suggested_reply: str | None = None
    risk_notes: list[str] = Field(default_factory=list)


Detector = Callable[[dict[str, Any]], Awaitable[EngagementDetectionDecision]]
TopicLoader = Callable[[AsyncSession], Awaitable[list[EngagementTopic]]]
SampleLoader = Callable[..., Awaitable[list[DetectionMessage]]]
ContextLoader = Callable[..., Awaitable[CommunityContext]]
CandidateCreator = Callable[..., Awaitable[EngagementCandidateCreationResult]]


async def detect_with_openai(model_input: dict[str, Any]) -> EngagementDetectionDecision:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai must be installed before engagement.detect can run") from exc

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for engagement.detect")

    model = settings.openai_engagement_model
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.parse(
        model=model,
        instructions=DETECTION_INSTRUCTIONS,
        input=[
            {
                "role": "user",
                "content": (
                    "Review this compact Telegram community context and decide whether a "
                    "short public reply would be genuinely useful. Return structured output only.\n\n"
                    f"{json.dumps(model_input, ensure_ascii=True, default=str)}"
                ),
            }
        ],
        text_format=EngagementDetectionDecision,
        temperature=0.2,
        max_output_tokens=1000,
    )
    decision = response.output_parsed
    if decision is None:
        raise RuntimeError("OpenAI returned no parsed engagement detection decision")
    return decision


async def process_engagement_detect(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    detector: Detector = detect_with_openai,
    active_topics_fn: TopicLoader = list_active_topics,
    sample_loader: SampleLoader = None,  # type: ignore[assignment]
    context_loader: ContextLoader = None,  # type: ignore[assignment]
    candidate_creator: CandidateCreator = create_engagement_candidate,
    settings: Settings | None = None,
) -> dict[str, object]:
    validated_payload = EngagementDetectPayload.model_validate(payload)
    runtime_settings = settings or get_settings()
    sample_loader = sample_loader or load_recent_detection_samples
    context_loader = context_loader or load_community_context

    async with session_factory() as session:
        try:
            community = await session.get(Community, validated_payload.community_id)
            if community is None:
                return _skipped("community_not_found", validated_payload.community_id)

            engagement_settings = await get_engagement_settings(
                session,
                validated_payload.community_id,
            )
            if engagement_settings.mode == EngagementMode.DISABLED.value:
                return _skipped("engagement_disabled", validated_payload.community_id)
            if engagement_settings.mode == EngagementMode.OBSERVE.value:
                return _skipped("observe_mode", validated_payload.community_id)
            if not await has_engagement_target_permission(
                session,
                community_id=validated_payload.community_id,
                permission="detect",
            ):
                return _skipped("engagement_target_detect_not_approved", validated_payload.community_id)

            topics = await active_topics_fn(session)
            if not topics:
                return _skipped("no_active_topics", validated_payload.community_id)

            messages = await sample_loader(
                session,
                community=community,
                window_minutes=validated_payload.window_minutes,
            )
            if not messages:
                return _skipped("no_recent_samples", validated_payload.community_id)

            community_context = await context_loader(session, community=community)
            summary = DetectionSummary(community_id=validated_payload.community_id)
            for topic in topics:
                summary.topics_checked += 1
                matching_messages = _prefilter_messages(topic, messages)
                if not matching_messages:
                    summary.skipped_no_signal += 1
                    continue

                model_input = _build_model_input(
                    community=community,
                    topic=topic,
                    messages=matching_messages[:MAX_MESSAGES_PER_MODEL_CALL],
                    community_context=community_context,
                )
                model_input = _fit_model_input(model_input)
                decision = await detector(model_input)
                decision = EngagementDetectionDecision.model_validate(decision)
                summary.detector_calls += 1
                if not decision.should_engage:
                    summary.skipped_no_signal += 1
                    continue
                if not decision.suggested_reply:
                    summary.skipped_validation += 1
                    continue

                source_message = _select_source_message(matching_messages, decision.source_tg_message_id)
                try:
                    creation = await candidate_creator(
                        session,
                        community_id=validated_payload.community_id,
                        topic_id=topic.id,
                        source_tg_message_id=decision.source_tg_message_id
                        if decision.source_tg_message_id is not None
                        else source_message.tg_message_id,
                        source_excerpt=source_message.text,
                        detected_reason=decision.reason,
                        suggested_reply=decision.suggested_reply,
                        model=runtime_settings.openai_engagement_model,
                        model_output=decision.model_dump(mode="json", exclude_none=True),
                        risk_notes=decision.risk_notes,
                    )
                except EngagementValidationError:
                    summary.skipped_validation += 1
                    continue

                if creation.created:
                    summary.candidates_created += 1
                else:
                    summary.skipped_dedupe += 1

            await session.commit()
            return summary.to_dict()
        except EngagementServiceError:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise


async def load_recent_detection_samples(
    session: AsyncSession,
    *,
    community: Community,
    window_minutes: int,
) -> list[DetectionMessage]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    artifact_messages = await _load_latest_artifact_messages(session, community.id, cutoff=cutoff)
    if artifact_messages:
        return artifact_messages
    if community.store_messages:
        return await _load_stored_messages(session, community.id, cutoff=cutoff)
    return []


async def load_community_context(
    session: AsyncSession,
    *,
    community: Community,
) -> CommunityContext:
    row = await session.scalar(
        select(AnalysisSummary)
        .where(AnalysisSummary.community_id == community.id)
        .order_by(AnalysisSummary.analyzed_at.desc())
        .limit(1)
    )
    if row is None:
        return CommunityContext(latest_summary=None, dominant_themes=[])
    return CommunityContext(
        latest_summary=row.summary,
        dominant_themes=list(row.dominant_themes or []),
    )


def run_engagement_detect_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_engagement_detect(payload))


@dataclass
class DetectionSummary:
    community_id: object
    candidates_created: int = 0
    topics_checked: int = 0
    detector_calls: int = 0
    skipped_no_signal: int = 0
    skipped_dedupe: int = 0
    skipped_validation: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": "engagement.detect",
            "community_id": str(self.community_id),
            "candidates_created": self.candidates_created,
            "topics_checked": self.topics_checked,
            "detector_calls": self.detector_calls,
            "skipped_no_signal": self.skipped_no_signal,
            "skipped_dedupe": self.skipped_dedupe,
            "skipped_validation": self.skipped_validation,
        }


def _prefilter_messages(topic: EngagementTopic, messages: list[DetectionMessage]) -> list[DetectionMessage]:
    triggers = [keyword.casefold() for keyword in topic.trigger_keywords or [] if keyword]
    negatives = [keyword.casefold() for keyword in topic.negative_keywords or [] if keyword]
    matches: list[DetectionMessage] = []
    for message in messages:
        text = message.text.casefold()
        if triggers and not any(keyword in text for keyword in triggers):
            continue
        if negatives and any(keyword in text for keyword in negatives):
            continue
        matches.append(message)
    return matches


def _build_model_input(
    *,
    community: Community,
    topic: EngagementTopic,
    messages: list[DetectionMessage],
    community_context: CommunityContext,
) -> dict[str, Any]:
    return {
        "community": {
            "id": str(community.id),
            "title": community.title,
            "username": community.username,
            "description": community.description,
            "is_group": bool(community.is_group),
        },
        "topic": {
            "id": str(topic.id),
            "name": topic.name,
            "description": topic.description,
            "stance_guidance": topic.stance_guidance,
            "trigger_keywords": list(topic.trigger_keywords or []),
            "negative_keywords": list(topic.negative_keywords or []),
            "example_good_replies": list(topic.example_good_replies or []),
            "example_bad_replies": list(topic.example_bad_replies or []),
        },
        "messages": [
            {
                "tg_message_id": message.tg_message_id,
                "text": _truncate_text(message.text, MAX_MESSAGE_CHARS),
                "message_date": message.message_date.isoformat() if message.message_date else None,
                "reply_context": _truncate_text(message.reply_context, MAX_MESSAGE_CHARS)
                if message.reply_context
                else None,
            }
            for message in messages[:MAX_MESSAGES_PER_MODEL_CALL]
        ],
        "community_context": {
            "latest_summary": _truncate_text(community_context.latest_summary, 2000)
            if community_context.latest_summary
            else None,
            "dominant_themes": community_context.dominant_themes[:20],
        },
    }


def _fit_model_input(model_input: dict[str, Any]) -> dict[str, Any]:
    while _serialized_size(model_input) > MAX_MODEL_INPUT_BYTES and model_input["messages"]:
        model_input["messages"].pop()
    return model_input


def _select_source_message(
    messages: list[DetectionMessage],
    source_tg_message_id: int | None,
) -> DetectionMessage:
    if source_tg_message_id is not None:
        for message in messages:
            if message.tg_message_id == source_tg_message_id:
                return message
    return messages[0]


async def _load_latest_artifact_messages(
    session: AsyncSession,
    community_id: object,
    *,
    cutoff: datetime,
) -> list[DetectionMessage]:
    result = await session.scalars(
        select(CollectionRun)
        .where(
            CollectionRun.community_id == community_id,
            CollectionRun.status == CollectionRunStatus.COMPLETED.value,
            CollectionRun.analysis_input.is_not(None),
        )
        .order_by(CollectionRun.completed_at.desc().nullslast(), CollectionRun.started_at.desc())
        .limit(5)
    )
    for run in result:
        messages = _messages_from_analysis_input(run.analysis_input or {}, cutoff=cutoff)
        if messages:
            return messages
    return []


async def _load_stored_messages(
    session: AsyncSession,
    community_id: object,
    *,
    cutoff: datetime,
) -> list[DetectionMessage]:
    result = await session.scalars(
        select(Message)
        .where(
            Message.community_id == community_id,
            Message.message_date >= cutoff,
            Message.text.is_not(None),
        )
        .order_by(Message.message_date.desc())
        .limit(100)
    )
    messages = [
        DetectionMessage(
            tg_message_id=message.tg_message_id,
            text=_truncate_text(message.text or "", MAX_MESSAGE_CHARS),
            message_date=message.message_date,
            reply_context=None,
        )
        for message in result
        if message.text
    ]
    messages.sort(key=lambda message: message.message_date or datetime.min.replace(tzinfo=timezone.utc))
    return messages


def _messages_from_analysis_input(
    analysis_input: dict[str, Any],
    *,
    cutoff: datetime,
) -> list[DetectionMessage]:
    messages: list[DetectionMessage] = []
    for raw_message in analysis_input.get("sample_messages") or []:
        if not isinstance(raw_message, dict):
            continue
        text = raw_message.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        message_date = _parse_datetime(raw_message.get("message_date"))
        if message_date is not None and message_date < cutoff:
            continue
        message = DetectionMessage(
            tg_message_id=_optional_int(
                raw_message.get("tg_message_id")
                or raw_message.get("message_id")
                or raw_message.get("id")
            ),
            text=_truncate_text(text, MAX_MESSAGE_CHARS),
            message_date=message_date,
            reply_context=_truncate_text(raw_message.get("reply_context"), MAX_MESSAGE_CHARS)
            if isinstance(raw_message.get("reply_context"), str)
            else None,
        )
        messages.append(message)
    return messages[-100:]


def _truncate_text(value: str | None, limit: int) -> str:
    sanitized = sanitize_candidate_excerpt(value) or ""
    return sanitized[:limit]


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=True, default=str).encode("utf-8"))


def _skipped(reason: str, community_id: object) -> dict[str, object]:
    return {
        "status": "skipped",
        "job_type": "engagement.detect",
        "community_id": str(community_id),
        "reason": reason,
    }
