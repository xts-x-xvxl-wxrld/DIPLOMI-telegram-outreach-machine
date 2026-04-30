from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.core.settings import Settings, get_settings
from backend.services.engagement_account_behavior import (
    COLLECTION_INITIAL_JITTER_MAX_MINUTES,
    COLLECTION_INITIAL_JITTER_MIN_MINUTES,
    COLLECTION_NEXT_JITTER_MAX_MINUTES,
    COLLECTION_NEXT_JITTER_MIN_MINUTES,
    READ_RECEIPT_JITTER_MAX_MINUTES,
    READ_RECEIPT_JITTER_MIN_MINUTES,
    ensure_aware_utc,
    stable_jitter_minutes,
)


class EngagementDueStateUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DueDecision:
    due: bool
    due_at: datetime


class RedisEngagementDueState:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._redis = None

    def collection_due(self, community_id: UUID, *, now: datetime) -> DueDecision:
        current_time = ensure_aware_utc(now)
        key = _collection_key(community_id)
        try:
            raw_due = self._redis_client().get(key)
            if raw_due is None:
                due_at = _initial_collection_due_at(community_id, now=current_time)
                self._redis_client().set(key, str(int(due_at.timestamp())))
                return DueDecision(due=False, due_at=due_at)
            due_at = datetime.fromtimestamp(int(raw_due), tz=timezone.utc)
            return DueDecision(due=due_at <= current_time, due_at=due_at)
        except Exception as exc:
            raise EngagementDueStateUnavailable(str(exc)) from exc

    def mark_collection_enqueued(self, community_id: UUID, *, now: datetime) -> datetime:
        current_time = ensure_aware_utc(now)
        due_at = _next_collection_due_at(community_id, now=current_time)
        try:
            self._redis_client().set(_collection_key(community_id), str(int(due_at.timestamp())))
        except Exception as exc:
            raise EngagementDueStateUnavailable(str(exc)) from exc
        return due_at

    def read_receipt_due(self, telegram_account_id: UUID, community_id: UUID, *, now: datetime) -> DueDecision:
        current_time = ensure_aware_utc(now)
        key = _read_key(telegram_account_id, community_id)
        try:
            raw_due = self._redis_client().get(key)
            if raw_due is None:
                return DueDecision(due=True, due_at=current_time)
            due_at = datetime.fromtimestamp(int(raw_due), tz=timezone.utc)
            return DueDecision(due=due_at <= current_time, due_at=due_at)
        except Exception as exc:
            raise EngagementDueStateUnavailable(str(exc)) from exc

    def mark_read_receipt_checked(
        self,
        telegram_account_id: UUID,
        community_id: UUID,
        *,
        now: datetime,
    ) -> datetime:
        current_time = ensure_aware_utc(now)
        due_at = _next_read_due_at(telegram_account_id, community_id, now=current_time)
        try:
            self._redis_client().set(
                _read_key(telegram_account_id, community_id),
                str(int(due_at.timestamp())),
            )
        except Exception as exc:
            raise EngagementDueStateUnavailable(str(exc)) from exc
        return due_at

    def _redis_client(self):
        if self._redis is None:
            try:
                from redis import Redis
            except ImportError as exc:
                raise EngagementDueStateUnavailable("redis is not installed") from exc
            self._redis = Redis.from_url(self.settings.redis_url)
        return self._redis


def _collection_key(community_id: UUID) -> str:
    return f"engagement:collection:next:{community_id}"


def _read_key(telegram_account_id: UUID, community_id: UUID) -> str:
    return f"engagement:read:next:{telegram_account_id}:{community_id}"


def _initial_collection_due_at(community_id: UUID, *, now: datetime) -> datetime:
    minutes = stable_jitter_minutes(
        minimum_minutes=COLLECTION_INITIAL_JITTER_MIN_MINUTES,
        maximum_minutes=COLLECTION_INITIAL_JITTER_MAX_MINUTES,
        seed_parts=("collection-initial", community_id),
    )
    return now + timedelta(minutes=minutes)


def _next_collection_due_at(community_id: UUID, *, now: datetime) -> datetime:
    minutes = stable_jitter_minutes(
        minimum_minutes=COLLECTION_NEXT_JITTER_MIN_MINUTES,
        maximum_minutes=COLLECTION_NEXT_JITTER_MAX_MINUTES,
        seed_parts=("collection-next", community_id, int(now.timestamp()) // 3600),
    )
    return now + timedelta(minutes=minutes)


def _next_read_due_at(telegram_account_id: UUID, community_id: UUID, *, now: datetime) -> datetime:
    minutes = stable_jitter_minutes(
        minimum_minutes=READ_RECEIPT_JITTER_MIN_MINUTES,
        maximum_minutes=READ_RECEIPT_JITTER_MAX_MINUTES,
        seed_parts=("read-receipt", telegram_account_id, community_id, int(now.timestamp()) // 900),
    )
    return now + timedelta(minutes=minutes)


__all__ = ["DueDecision", "EngagementDueStateUnavailable", "RedisEngagementDueState"]
