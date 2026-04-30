from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.db.enums import EngagementMomentStrength, EngagementReplyValue, EngagementTimeliness
from backend.services.community_engagement_views import EngagementValidationError

DEFAULT_REPLY_DEADLINE_MINUTES = 90
REVIEW_WINDOW_MINUTES = 30


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def calculate_reply_deadline_at(
    *,
    source_message_date: datetime | None,
    detected_at: datetime,
    reply_deadline_minutes: int = DEFAULT_REPLY_DEADLINE_MINUTES,
) -> datetime:
    base_time = ensure_aware_utc(source_message_date or detected_at)
    return base_time + timedelta(minutes=max(reply_deadline_minutes, 1))


def calculate_review_deadline_at(
    *,
    source_message_date: datetime | None,
    reply_deadline_at: datetime,
) -> datetime | None:
    if source_message_date is None:
        return None
    review_deadline = ensure_aware_utc(reply_deadline_at) - timedelta(minutes=REVIEW_WINDOW_MINUTES)
    source_time = ensure_aware_utc(source_message_date)
    return max(review_deadline, source_time)


def infer_candidate_timeliness(
    *,
    detected_at: datetime,
    review_deadline_at: datetime | None,
    reply_deadline_at: datetime,
) -> str:
    detected_time = ensure_aware_utc(detected_at)
    if detected_time >= ensure_aware_utc(reply_deadline_at):
        return EngagementTimeliness.STALE.value
    if review_deadline_at is not None and detected_time >= ensure_aware_utc(review_deadline_at):
        return EngagementTimeliness.AGING.value
    return EngagementTimeliness.FRESH.value


def normalize_moment_strength(value: str | None) -> str:
    cleaned = _optional_text(value)
    if cleaned is None:
        return EngagementMomentStrength.GOOD.value
    normalized = cleaned.casefold()
    allowed = {item.value for item in EngagementMomentStrength}
    if normalized not in allowed:
        raise EngagementValidationError(
            "invalid_moment_strength",
            "moment_strength must be weak, good, or strong",
        )
    return normalized


def normalize_reply_value(value: str | None, *, has_reply: bool) -> str:
    cleaned = _optional_text(value)
    if cleaned is None:
        return EngagementReplyValue.OTHER.value if has_reply else EngagementReplyValue.NONE.value
    normalized = cleaned.casefold()
    allowed = {item.value for item in EngagementReplyValue}
    if normalized not in allowed:
        raise EngagementValidationError(
            "invalid_reply_value",
            "reply_value must describe the public reply type, not a person-level score",
        )
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = [
    "DEFAULT_REPLY_DEADLINE_MINUTES",
    "calculate_reply_deadline_at",
    "calculate_review_deadline_at",
    "ensure_aware_utc",
    "infer_candidate_timeliness",
    "normalize_moment_strength",
    "normalize_reply_value",
]
