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
from backend.db.enums import CollectionRunStatus, EngagementCandidateStatus, EngagementMode
from backend.db.models import CollectionRun, CommunityEngagementSettings, EngagementCandidate
from backend.db.session import AsyncSessionLocal
from backend.queue.client import QueuedJob, enqueue_engagement_detect

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


TargetLoader = Callable[[AsyncSession], Awaitable[list[EngagementDetectionTarget]]]
EnqueueDetectFn = Callable[..., QueuedJob]


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


async def load_engagement_detection_targets(
    session: AsyncSession,
) -> list[EngagementDetectionTarget]:
    latest_collection_completed_at = (
        select(func.max(CollectionRun.completed_at))
        .where(
            CollectionRun.community_id == CommunityEngagementSettings.community_id,
            CollectionRun.status == CollectionRunStatus.COMPLETED.value,
            CollectionRun.completed_at.is_not(None),
        )
        .correlate(CommunityEngagementSettings)
        .scalar_subquery()
    )
    active_candidate_count = (
        select(func.count(EngagementCandidate.id))
        .where(
            EngagementCandidate.community_id == CommunityEngagementSettings.community_id,
            EngagementCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
        )
        .correlate(CommunityEngagementSettings)
        .scalar_subquery()
    )

    rows = await session.execute(
        select(
            CommunityEngagementSettings.community_id.label("community_id"),
            CommunityEngagementSettings.mode.label("mode"),
            CommunityEngagementSettings.quiet_hours_start.label("quiet_hours_start"),
            CommunityEngagementSettings.quiet_hours_end.label("quiet_hours_end"),
            latest_collection_completed_at.label("latest_collection_completed_at"),
            active_candidate_count.label("active_candidate_count"),
        )
        .where(CommunityEngagementSettings.mode.in_(ENABLED_MODES))
        .order_by(CommunityEngagementSettings.community_id)
    )
    return [
        EngagementDetectionTarget(
            community_id=row["community_id"],
            mode=row["mode"],
            quiet_hours_start=row["quiet_hours_start"],
            quiet_hours_end=row["quiet_hours_end"],
            latest_collection_completed_at=row["latest_collection_completed_at"],
            active_candidate_count=int(row["active_candidate_count"] or 0),
        )
        for row in rows.mappings().all()
    ]


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
    interval_seconds = max(settings.engagement_scheduler_interval_seconds, 60)
    while True:
        try:
            summary = await process_engagement_scheduler_tick(settings=settings)
            LOGGER.info("Engagement scheduler tick: %s", summary)
        except Exception:
            LOGGER.exception("Engagement scheduler tick failed")
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


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


if __name__ == "__main__":
    main()
