from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.enums import (
    CollectionRunStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStatus,
    EngagementTargetStatus,
)
from backend.db.models import (
    CollectionRun,
    CommunityEngagementSettings,
    Engagement,
    EngagementCandidate,
    EngagementSettings,
    EngagementTarget,
)
from backend.db.session import AsyncSessionLocal
from backend.queue.client import (
    QueuedJob,
    enqueue_account_health_refresh,
    enqueue_collection,
    enqueue_engagement_detect,
)
from backend.services.community_engagement import get_engagement_settings
from backend.services.engagement_account_behavior import ACCOUNT_HEALTH_REFRESH_HOURS
from backend.services.engagement_due_state import (
    DueDecision,
    EngagementDueStateUnavailable,
    RedisEngagementDueState,
)

LOGGER = logging.getLogger(__name__)

SCHEDULER_JOB_TYPE = "engagement.scheduler"
ENABLED_MODES = {
    EngagementMode.OBSERVE.value,
    EngagementMode.SUGGEST.value,
    EngagementMode.REQUIRE_APPROVAL.value,
}
ACTIVE_CANDIDATE_STATUSES = {
    EngagementCandidateStatus.NEEDS_REVIEW.value,
    EngagementCandidateStatus.APPROVED.value,
}


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


@dataclass(frozen=True)
class EngagementDetectionTarget:
    community_id: UUID
    mode: str
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    latest_collection_completed_at: datetime | None
    active_candidate_count: int


@dataclass(frozen=True)
class EngagementCollectionTarget:
    community_id: UUID
    mode: str
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    latest_collection_completed_at: datetime | None
    active_collection_count: int
    has_detect_permission: bool


@dataclass
class EngagementSchedulerSummary:
    window_minutes: int
    targets_checked: int = 0
    jobs_enqueued: int = 0
    skipped_disabled: int = 0
    skipped_no_recent_collection: int = 0
    skipped_active_candidate: int = 0
    skipped_quiet_hours: int = 0
    enqueue_failures: int = 0
    job_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": SCHEDULER_JOB_TYPE,
            "window_minutes": self.window_minutes,
            "targets_checked": self.targets_checked,
            "jobs_enqueued": self.jobs_enqueued,
            "skipped_disabled": self.skipped_disabled,
            "skipped_no_recent_collection": self.skipped_no_recent_collection,
            "skipped_active_candidate": self.skipped_active_candidate,
            "skipped_quiet_hours": self.skipped_quiet_hours,
            "enqueue_failures": self.enqueue_failures,
            "job_ids": self.job_ids,
        }


@dataclass
class EngagementCollectionSchedulerSummary:
    interval_seconds: int
    targets_checked: int = 0
    jobs_enqueued: int = 0
    duplicate_jobs: int = 0
    skipped_disabled: int = 0
    skipped_missing_target_permission: int = 0
    skipped_recent_collection: int = 0
    skipped_not_due: int = 0
    skipped_due_state_unavailable: int = 0
    skipped_active_collection: int = 0
    skipped_quiet_hours: int = 0
    enqueue_failures: int = 0
    job_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": "engagement.collection_scheduler",
            "interval_seconds": self.interval_seconds,
            "targets_checked": self.targets_checked,
            "jobs_enqueued": self.jobs_enqueued,
            "duplicate_jobs": self.duplicate_jobs,
            "skipped_disabled": self.skipped_disabled,
            "skipped_missing_target_permission": self.skipped_missing_target_permission,
            "skipped_recent_collection": self.skipped_recent_collection,
            "skipped_not_due": self.skipped_not_due,
            "skipped_due_state_unavailable": self.skipped_due_state_unavailable,
            "skipped_active_collection": self.skipped_active_collection,
            "skipped_quiet_hours": self.skipped_quiet_hours,
            "enqueue_failures": self.enqueue_failures,
            "job_ids": self.job_ids,
        }


TargetLoader = Callable[[AsyncSession], Awaitable[list[EngagementDetectionTarget]]]
CollectionTargetLoader = Callable[[AsyncSession], Awaitable[list[EngagementCollectionTarget]]]
EnqueueDetectFn = Callable[..., QueuedJob]
EnqueueCollectionFn = Callable[..., QueuedJob]
EnqueueHealthRefreshFn = Callable[..., QueuedJob]


class CollectionDueState(Protocol):
    def collection_due(self, community_id: UUID, *, now: datetime) -> DueDecision:
        pass

    def mark_collection_enqueued(self, community_id: UUID, *, now: datetime) -> datetime:
        pass


def process_account_health_refresh_scheduler_tick(
    *,
    enqueue_health_refresh_fn: EnqueueHealthRefreshFn = enqueue_account_health_refresh,
    now: datetime | None = None,
) -> dict[str, object]:
    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    try:
        job = enqueue_health_refresh_fn(now=current_time)
    except Exception:
        LOGGER.exception("Failed to enqueue account health refresh")
        return {
            "status": "processed",
            "job_type": "account.health_refresh_scheduler",
            "jobs_enqueued": 0,
            "enqueue_failures": 1,
            "job_ids": [],
        }
    return {
        "status": "processed",
        "job_type": "account.health_refresh_scheduler",
        "jobs_enqueued": 0 if job.status == "duplicate" else 1,
        "enqueue_failures": 0,
        "job_ids": [job.id],
    }


async def process_engagement_scheduler_tick(
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    target_loader: TargetLoader | None = None,
    enqueue_detect_fn: EnqueueDetectFn = enqueue_engagement_detect,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    runtime_settings = settings or get_settings()
    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    window_minutes = runtime_settings.engagement_detection_window_minutes
    target_loader = target_loader or load_engagement_detection_targets
    summary = EngagementSchedulerSummary(window_minutes=window_minutes)

    async with session_factory() as session:
        targets = await target_loader(session)

    for target in targets:
        summary.targets_checked += 1
        skip_reason = detection_target_skip_reason(
            target,
            now=current_time,
            window_minutes=window_minutes,
        )
        if skip_reason is not None:
            _record_skip(summary, skip_reason)
            continue

        try:
            job = enqueue_detect_fn(
                target.community_id,
                window_minutes=window_minutes,
                requested_by=None,
                now=current_time,
            )
        except Exception:
            summary.enqueue_failures += 1
            LOGGER.exception("Failed to enqueue engagement detection for community %s", target.community_id)
            continue

        summary.jobs_enqueued += 1
        summary.job_ids.append(job.id)

    return summary.to_dict()


async def process_engagement_collection_scheduler_tick(
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    target_loader: CollectionTargetLoader | None = None,
    enqueue_collection_fn: EnqueueCollectionFn = enqueue_collection,
    due_state: CollectionDueState | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    runtime_settings = settings or get_settings()
    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    interval_seconds = max(runtime_settings.engagement_active_collection_interval_seconds, 60)
    target_loader = target_loader or load_engagement_collection_targets
    due_state = due_state or RedisEngagementDueState(settings=runtime_settings)
    summary = EngagementCollectionSchedulerSummary(interval_seconds=interval_seconds)

    async with session_factory() as session:
        targets = await target_loader(session)

    for target in targets:
        summary.targets_checked += 1
        skip_reason = collection_target_skip_reason(
            target,
            now=current_time,
            interval_seconds=interval_seconds,
        )
        if skip_reason is not None:
            _record_collection_skip(summary, skip_reason)
            continue
        try:
            due_decision = due_state.collection_due(target.community_id, now=current_time)
        except EngagementDueStateUnavailable:
            summary.skipped_due_state_unavailable += 1
            LOGGER.exception("Engagement collection due-state unavailable for community %s", target.community_id)
            continue
        if not due_decision.due:
            summary.skipped_not_due += 1
            continue

        try:
            job = enqueue_collection_fn(
                target.community_id,
                reason="engagement",
                requested_by=None,
                now=current_time,
            )
        except Exception:
            summary.enqueue_failures += 1
            LOGGER.exception("Failed to enqueue engagement collection for community %s", target.community_id)
            continue

        if job.status == "duplicate":
            summary.duplicate_jobs += 1
        else:
            summary.jobs_enqueued += 1
        try:
            due_state.mark_collection_enqueued(target.community_id, now=current_time)
        except EngagementDueStateUnavailable:
            LOGGER.exception("Failed to update engagement collection due-state for community %s", target.community_id)
        summary.job_ids.append(job.id)

    return summary.to_dict()


async def load_engagement_detection_targets(
    session: AsyncSession,
) -> list[EngagementDetectionTarget]:
    targets: list[EngagementDetectionTarget] = []
    for community_id in await _load_effective_settings_community_ids(session):
        settings = await get_engagement_settings(session, community_id)
        if settings.mode not in ENABLED_MODES:
            continue
        latest_collection_completed_at = await _latest_completed_collection_at(session, community_id=community_id)
        active_candidate_count = await _active_candidate_count(session, community_id=community_id)
        targets.append(
            EngagementDetectionTarget(
                community_id=community_id,
                mode=settings.mode,
                quiet_hours_start=settings.quiet_hours_start,
                quiet_hours_end=settings.quiet_hours_end,
                latest_collection_completed_at=latest_collection_completed_at,
                active_candidate_count=active_candidate_count,
            )
        )
    return targets


async def load_engagement_collection_targets(
    session: AsyncSession,
) -> list[EngagementCollectionTarget]:
    targets: list[EngagementCollectionTarget] = []
    for community_id in await _load_effective_settings_community_ids(session):
        settings = await get_engagement_settings(session, community_id)
        latest_collection_completed_at = await _latest_completed_collection_at(
            session,
            community_id=community_id,
            require_analysis_input=True,
        )
        active_collection_count = await _active_collection_count(session, community_id=community_id)
        detect_target_count = await _detect_target_count(session, community_id=community_id)
        targets.append(
            EngagementCollectionTarget(
                community_id=community_id,
                mode=settings.mode,
                quiet_hours_start=settings.quiet_hours_start,
                quiet_hours_end=settings.quiet_hours_end,
                latest_collection_completed_at=latest_collection_completed_at,
                active_collection_count=active_collection_count,
                has_detect_permission=detect_target_count > 0,
            )
        )
    return targets


async def _load_effective_settings_community_ids(session: AsyncSession) -> list[UUID]:
    community_ids = {
        community_id
        for community_id in list(await session.scalars(select(CommunityEngagementSettings.community_id)))
        if community_id is not None
    }
    community_ids.update(
        community_id
        for community_id in list(
            await session.scalars(
                select(Engagement.community_id)
                .join(EngagementSettings, EngagementSettings.engagement_id == Engagement.id)
                .where(Engagement.status == EngagementStatus.ACTIVE.value)
            )
        )
        if community_id is not None
    )
    return sorted(community_ids, key=str)


async def _latest_completed_collection_at(
    session: AsyncSession,
    *,
    community_id: UUID,
    require_analysis_input: bool = False,
) -> datetime | None:
    query = select(func.max(CollectionRun.completed_at)).where(
        CollectionRun.community_id == community_id,
        CollectionRun.status == CollectionRunStatus.COMPLETED.value,
        CollectionRun.completed_at.is_not(None),
    )
    if require_analysis_input:
        query = query.where(CollectionRun.analysis_input.is_not(None))
    return await session.scalar(query)


async def _active_candidate_count(session: AsyncSession, *, community_id: UUID) -> int:
    count = await session.scalar(
        select(func.count(EngagementCandidate.id)).where(
            EngagementCandidate.community_id == community_id,
            EngagementCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
        )
    )
    return int(count or 0)


async def _active_collection_count(session: AsyncSession, *, community_id: UUID) -> int:
    count = await session.scalar(
        select(func.count(CollectionRun.id)).where(
            CollectionRun.community_id == community_id,
            CollectionRun.status == CollectionRunStatus.RUNNING.value,
        )
    )
    return int(count or 0)


async def _detect_target_count(session: AsyncSession, *, community_id: UUID) -> int:
    count = await session.scalar(
        select(func.count(EngagementTarget.id)).where(
            EngagementTarget.community_id == community_id,
            EngagementTarget.status == EngagementTargetStatus.APPROVED.value,
            EngagementTarget.allow_detect.is_(True),
        )
    )
    return int(count or 0)


def detection_target_skip_reason(
    target: EngagementDetectionTarget,
    *,
    now: datetime,
    window_minutes: int,
) -> str | None:
    if target.mode not in ENABLED_MODES:
        return "disabled"
    if target.latest_collection_completed_at is None:
        return "no_recent_collection"
    cutoff = _ensure_aware_utc(now) - timedelta(minutes=window_minutes)
    if _ensure_aware_utc(target.latest_collection_completed_at) < cutoff:
        return "no_recent_collection"
    if target.active_candidate_count > 0:
        return "active_candidate"
    if is_quiet_time(
        now,
        quiet_hours_start=target.quiet_hours_start,
        quiet_hours_end=target.quiet_hours_end,
    ):
        return "quiet_hours"
    return None


def collection_target_skip_reason(
    target: EngagementCollectionTarget,
    *,
    now: datetime,
    interval_seconds: int,
) -> str | None:
    if target.mode not in ENABLED_MODES:
        return "disabled"
    if not target.has_detect_permission:
        return "missing_target_permission"
    if target.active_collection_count > 0:
        return "active_collection"
    if target.latest_collection_completed_at is not None:
        cutoff = _ensure_aware_utc(now) - timedelta(seconds=interval_seconds)
        if _ensure_aware_utc(target.latest_collection_completed_at) >= cutoff:
            return "recent_collection"
    if is_quiet_time(
        now,
        quiet_hours_start=target.quiet_hours_start,
        quiet_hours_end=target.quiet_hours_end,
    ):
        return "quiet_hours"
    return None


def is_quiet_time(
    now: datetime,
    *,
    quiet_hours_start: time | None,
    quiet_hours_end: time | None,
) -> bool:
    if quiet_hours_start is None or quiet_hours_end is None:
        return False
    current_time = _ensure_aware_utc(now).time().replace(tzinfo=None)
    if quiet_hours_start == quiet_hours_end:
        return True
    if quiet_hours_start < quiet_hours_end:
        return quiet_hours_start <= current_time < quiet_hours_end
    return current_time >= quiet_hours_start or current_time < quiet_hours_end


async def run_scheduler_loop() -> None:
    settings = get_settings()
    detection_interval_seconds = max(settings.engagement_scheduler_interval_seconds, 60)
    collection_interval_seconds = max(settings.engagement_active_collection_interval_seconds, 60)
    health_refresh_interval_seconds = max(
        getattr(settings, "engagement_account_health_refresh_interval_seconds", ACCOUNT_HEALTH_REFRESH_HOURS * 3600),
        3600,
    )
    next_detection_at: datetime | None = None
    next_collection_at: datetime | None = None
    next_health_refresh_at: datetime | None = None
    while True:
        now = datetime.now(timezone.utc)
        if next_health_refresh_at is None or now >= next_health_refresh_at:
            try:
                summary = process_account_health_refresh_scheduler_tick(now=now)
                LOGGER.info("Account health refresh scheduler tick: %s", summary)
            except Exception:
                LOGGER.exception("Account health refresh scheduler tick failed")
            next_health_refresh_at = now + timedelta(seconds=health_refresh_interval_seconds)

        if next_collection_at is None or now >= next_collection_at:
            try:
                summary = await process_engagement_collection_scheduler_tick(settings=settings, now=now)
                LOGGER.info("Engagement collection scheduler tick: %s", summary)
            except Exception:
                LOGGER.exception("Engagement collection scheduler tick failed")
            next_collection_at = now + timedelta(seconds=collection_interval_seconds)

        if next_detection_at is None or now >= next_detection_at:
            try:
                summary = await process_engagement_scheduler_tick(settings=settings, now=now)
                LOGGER.info("Engagement detection scheduler tick: %s", summary)
            except Exception:
                LOGGER.exception("Engagement detection scheduler tick failed")
            next_detection_at = now + timedelta(seconds=detection_interval_seconds)

        sleep_until = min(next_collection_at, next_detection_at, next_health_refresh_at)
        sleep_seconds = max((sleep_until - datetime.now(timezone.utc)).total_seconds(), 1)
        await asyncio.sleep(min(sleep_seconds, 60))


async def run_detection_scheduler_loop() -> None:
    settings = get_settings()
    interval_seconds = max(settings.engagement_scheduler_interval_seconds, 60)
    while True:
        try:
            summary = await process_engagement_scheduler_tick(settings=settings)
            LOGGER.info("Engagement detection scheduler tick: %s", summary)
        except Exception:
            LOGGER.exception("Engagement detection scheduler tick failed")
        await asyncio.sleep(interval_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler_loop())


def _record_skip(summary: EngagementSchedulerSummary, reason: str) -> None:
    if reason == "disabled":
        summary.skipped_disabled += 1
    elif reason == "no_recent_collection":
        summary.skipped_no_recent_collection += 1
    elif reason == "active_candidate":
        summary.skipped_active_candidate += 1
    elif reason == "quiet_hours":
        summary.skipped_quiet_hours += 1


def _record_collection_skip(summary: EngagementCollectionSchedulerSummary, reason: str) -> None:
    if reason == "disabled":
        summary.skipped_disabled += 1
    elif reason == "missing_target_permission":
        summary.skipped_missing_target_permission += 1
    elif reason == "recent_collection":
        summary.skipped_recent_collection += 1
    elif reason == "active_collection":
        summary.skipped_active_collection += 1
    elif reason == "quiet_hours":
        summary.skipped_quiet_hours += 1


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


if __name__ == "__main__":
    main()
