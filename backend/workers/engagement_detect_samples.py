# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.workers.engagement_detect_types import *


async def load_recent_detection_samples(
    session: AsyncSession,
    *,
    community: Community,
    window_minutes: int,
) -> list[DetectionMessage]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    artifact_messages = await _load_latest_artifact_messages(session, community, cutoff=cutoff)
    if artifact_messages:
        return artifact_messages
    if community.store_messages:
        return await _load_stored_messages(session, community, cutoff=cutoff)
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


async def _load_latest_artifact_messages(
    session: AsyncSession,
    community: Community,
    *,
    cutoff: datetime,
) -> list[DetectionMessage]:
    result = await session.scalars(
        select(CollectionRun)
        .where(
            CollectionRun.community_id == community.id,
            CollectionRun.status == CollectionRunStatus.COMPLETED.value,
            CollectionRun.analysis_input.is_not(None),
        )
        .order_by(CollectionRun.completed_at.desc().nullslast(), CollectionRun.started_at.desc())
        .limit(5)
    )
    for run in result:
        messages = _messages_from_analysis_input(
            run.analysis_input or {},
            cutoff=cutoff,
            community_is_group=bool(community.is_group),
        )
        if messages:
            return messages
    return []


async def _load_stored_messages(
    session: AsyncSession,
    community: Community,
    *,
    cutoff: datetime,
) -> list[DetectionMessage]:
    result = await session.scalars(
        select(Message)
        .where(
            Message.community_id == community.id,
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
            is_replyable=bool(community.is_group and message.tg_message_id is not None),
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
    community_is_group: bool,
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
        tg_message_id = _optional_int(
            raw_message.get("tg_message_id")
            or raw_message.get("message_id")
            or raw_message.get("id")
        )
        message = DetectionMessage(
            tg_message_id=tg_message_id,
            text=_truncate_text(text, MAX_MESSAGE_CHARS),
            message_date=message_date,
            reply_context=_truncate_text(raw_message.get("reply_context"), MAX_MESSAGE_CHARS)
            if isinstance(raw_message.get("reply_context"), str)
            else None,
            is_replyable=_coerce_is_replyable(
                raw_message.get("is_replyable"),
                community_is_group=community_is_group,
                tg_message_id=tg_message_id,
            ),
        )
        messages.append(message)
    return messages[-100:]


def _truncate_text(value: str | None, limit: int) -> str:
    sanitized = sanitize_candidate_excerpt(value) or ""
    return sanitized[:limit]


def _coerce_is_replyable(
    value: object,
    *,
    community_is_group: bool,
    tg_message_id: int | None,
) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(community_is_group and tg_message_id is not None)


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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

__all__ = [
    "load_recent_detection_samples",
    "load_community_context",
]
