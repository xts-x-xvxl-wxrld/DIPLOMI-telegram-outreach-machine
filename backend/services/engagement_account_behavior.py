from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID


SEND_DELAY_MIN_SECONDS = 45
SEND_DELAY_MAX_SECONDS = 120
INITIAL_JOIN_READ_LIMIT = 5
WARMUP_DURATION_MINUTES = 60
WARMUP_READ_INTERVAL_MIN_MINUTES = 1
WARMUP_READ_INTERVAL_MAX_MINUTES = 15
WARMUP_READ_CHECKS_MAX = 5
COLLECTION_INITIAL_JITTER_MIN_MINUTES = 1
COLLECTION_INITIAL_JITTER_MAX_MINUTES = 15
COLLECTION_NEXT_JITTER_MIN_MINUTES = 3
COLLECTION_NEXT_JITTER_MAX_MINUTES = 15
READ_RECEIPT_JITTER_MIN_MINUTES = 1
READ_RECEIPT_JITTER_MAX_MINUTES = 15
MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_4H = 3
MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_24H = 12
MIN_MINUTES_BETWEEN_STARTED_OPPORTUNITIES = 15
SAME_COMMUNITY_NEW_OPPORTUNITY_COOLDOWN_MINUTES = 90
MAX_CONTINUATION_REPLIES_PER_OPPORTUNITY_24H = 3
MIN_MINUTES_BETWEEN_CONTINUATION_REPLIES = 5
ACCOUNT_HEALTH_REFRESH_HOURS = 8


@dataclass(frozen=True)
class JitterRange:
    minimum: int
    maximum: int

    def validate(self) -> None:
        if self.minimum < 0:
            raise ValueError("minimum must be non-negative")
        if self.maximum < self.minimum:
            raise ValueError("maximum must be greater than or equal to minimum")


def stable_jitter_seconds(
    *,
    minimum_seconds: int,
    maximum_seconds: int,
    seed_parts: tuple[Any, ...],
) -> int:
    return _stable_jitter_value(
        jitter_range=JitterRange(minimum_seconds, maximum_seconds),
        seed_parts=seed_parts,
    )


def stable_jitter_minutes(
    *,
    minimum_minutes: int,
    maximum_minutes: int,
    seed_parts: tuple[Any, ...],
) -> int:
    return _stable_jitter_value(
        jitter_range=JitterRange(minimum_minutes, maximum_minutes),
        seed_parts=seed_parts,
    )


def utc_epoch_bucket(value: datetime, *, bucket_seconds: int) -> int:
    if bucket_seconds <= 0:
        raise ValueError("bucket_seconds must be positive")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    epoch_seconds = int(value.astimezone(timezone.utc).timestamp())
    return epoch_seconds // bucket_seconds


def engagement_send_delay_seconds(candidate_id: UUID) -> int:
    return stable_jitter_seconds(
        minimum_seconds=SEND_DELAY_MIN_SECONDS,
        maximum_seconds=SEND_DELAY_MAX_SECONDS,
        seed_parts=("engagement-send-delay", candidate_id),
    )


def engagement_send_scheduled_at(candidate_id: UUID, *, now: datetime | None = None) -> datetime:
    current_time = ensure_aware_utc(now or datetime.now(timezone.utc))
    return current_time + timedelta(seconds=engagement_send_delay_seconds(candidate_id))


def post_join_warmup_skip_reason(
    *,
    joined_at: datetime | None,
    now: datetime | None = None,
) -> str | None:
    if joined_at is None:
        return "missing_joined_at"
    current_time = ensure_aware_utc(now or datetime.now(timezone.utc))
    warmup_ends_at = ensure_aware_utc(joined_at) + timedelta(minutes=WARMUP_DURATION_MINUTES)
    if current_time < warmup_ends_at:
        return "post_join_warmup_active"
    return None


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _stable_jitter_value(*, jitter_range: JitterRange, seed_parts: tuple[Any, ...]) -> int:
    jitter_range.validate()
    if not seed_parts:
        raise ValueError("seed_parts must not be empty")
    spread = jitter_range.maximum - jitter_range.minimum
    if spread == 0:
        return jitter_range.minimum
    digest = hashlib.sha256(_seed_bytes(seed_parts)).digest()
    offset = int.from_bytes(digest[:8], byteorder="big") % (spread + 1)
    return jitter_range.minimum + offset


def _seed_bytes(seed_parts: tuple[Any, ...]) -> bytes:
    normalized = "\x1f".join(_normalize_seed_part(part) for part in seed_parts)
    return normalized.encode("utf-8")


def _normalize_seed_part(value: Any) -> str:
    if isinstance(value, datetime):
        return ensure_aware_utc(value).isoformat()
    return str(value)
