from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.core.settings import Settings
from backend.db.enums import EngagementMode
from backend.queue.client import QueuedJob
from backend.services.engagement_due_state import DueDecision, EngagementDueStateUnavailable
from backend.workers.engagement_scheduler import (
    EngagementCollectionTarget,
    EngagementDetectionTarget,
    collection_target_skip_reason,
    detection_target_skip_reason,
    is_quiet_time,
    process_engagement_collection_scheduler_tick,
    process_engagement_scheduler_tick,
)


def test_settings_default_engagement_collection_interval_is_three_minutes() -> None:
    settings = Settings(_env_file=None)

    assert settings.engagement_active_collection_interval_seconds == 180


@pytest.mark.asyncio
async def test_engagement_scheduler_enqueues_only_due_detection_targets() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
    due_id = uuid4()
    stale_id = uuid4()
    active_id = uuid4()
    quiet_id = uuid4()
    disabled_id = uuid4()
    targets = [
        _target(due_id, latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc)),
        _target(stale_id, latest_collection_completed_at=datetime(2026, 4, 19, 11, 0, tzinfo=timezone.utc)),
        _target(
            active_id,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
            active_candidate_count=1,
        ),
        _target(
            quiet_id,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
            quiet_hours_start=time(13, 0),
            quiet_hours_end=time(14, 0),
        ),
        _target(
            disabled_id,
            mode=EngagementMode.DISABLED.value,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
        ),
    ]
    enqueued: list[dict[str, object]] = []

    async def target_loader(_session: object) -> list[EngagementDetectionTarget]:
        return targets

    def enqueue_detect(
        community_id: object,
        *,
        window_minutes: int,
        requested_by: str | None,
        now: datetime,
    ) -> QueuedJob:
        enqueued.append(
            {
                "community_id": community_id,
                "window_minutes": window_minutes,
                "requested_by": requested_by,
                "now": now,
            }
        )
        return QueuedJob(id=f"engagement.detect:{community_id}:2026041913", type="engagement.detect")

    result = await process_engagement_scheduler_tick(
        session_factory=lambda: FakeSession(),
        target_loader=target_loader,
        enqueue_detect_fn=enqueue_detect,
        settings=SimpleNamespace(engagement_detection_window_minutes=60),  # type: ignore[arg-type]
        now=now,
    )

    assert result["status"] == "processed"
    assert result["targets_checked"] == 5
    assert result["jobs_enqueued"] == 1
    assert result["skipped_no_recent_collection"] == 1
    assert result["skipped_active_candidate"] == 1
    assert result["skipped_quiet_hours"] == 1
    assert result["skipped_disabled"] == 1
    assert enqueued == [
        {
            "community_id": due_id,
            "window_minutes": 60,
            "requested_by": None,
            "now": now,
        }
    ]
    assert result["job_ids"] == [f"engagement.detect:{due_id}:2026041913"]


def test_detection_target_skip_reason_requires_recent_collection() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
    target = _target(
        uuid4(),
        latest_collection_completed_at=datetime(2026, 4, 19, 12, 29, tzinfo=timezone.utc),
    )

    assert detection_target_skip_reason(target, now=now, window_minutes=60) == "no_recent_collection"


@pytest.mark.asyncio
async def test_engagement_collection_scheduler_enqueues_only_due_targets() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
    due_id = uuid4()
    recent_id = uuid4()
    active_id = uuid4()
    quiet_id = uuid4()
    disabled_id = uuid4()
    missing_permission_id = uuid4()
    targets = [
        _collection_target(
            due_id,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
        ),
        _collection_target(
            recent_id,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 25, tzinfo=timezone.utc),
        ),
        _collection_target(active_id, latest_collection_completed_at=None, active_collection_count=1),
        _collection_target(
            quiet_id,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
            quiet_hours_start=time(13, 0),
            quiet_hours_end=time(14, 0),
        ),
        _collection_target(
            disabled_id,
            mode=EngagementMode.DISABLED.value,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
        ),
        _collection_target(
            missing_permission_id,
            latest_collection_completed_at=datetime(2026, 4, 19, 13, 10, tzinfo=timezone.utc),
            has_detect_permission=False,
        ),
    ]
    enqueued: list[dict[str, object]] = []

    async def target_loader(_session: object) -> list[EngagementCollectionTarget]:
        return targets

    def enqueue_collection(
        community_id: object,
        *,
        reason: str,
        requested_by: str | None,
        now: datetime,
    ) -> QueuedJob:
        enqueued.append(
            {
                "community_id": community_id,
                "reason": reason,
                "requested_by": requested_by,
                "now": now,
            }
        )
        return QueuedJob(id=f"collection:engagement:{community_id}:202604191330", type="collection.run")

    result = await process_engagement_collection_scheduler_tick(
        session_factory=lambda: FakeSession(),
        target_loader=target_loader,
        enqueue_collection_fn=enqueue_collection,
        due_state=AlwaysDueState(),
        settings=SimpleNamespace(engagement_active_collection_interval_seconds=600),  # type: ignore[arg-type]
        now=now,
    )

    assert result["status"] == "processed"
    assert result["targets_checked"] == 6
    assert result["jobs_enqueued"] == 1
    assert result["duplicate_jobs"] == 0
    assert result["skipped_recent_collection"] == 1
    assert result["skipped_active_collection"] == 1
    assert result["skipped_quiet_hours"] == 1
    assert result["skipped_disabled"] == 1
    assert result["skipped_missing_target_permission"] == 1
    assert enqueued == [
        {
            "community_id": due_id,
            "reason": "engagement",
            "requested_by": None,
            "now": now,
        }
    ]
    assert result["job_ids"] == [f"collection:engagement:{due_id}:202604191330"]


@pytest.mark.asyncio
async def test_engagement_collection_scheduler_treats_duplicate_jobs_as_safe() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
    community_id = uuid4()

    async def target_loader(_session: object) -> list[EngagementCollectionTarget]:
        return [_collection_target(community_id, latest_collection_completed_at=None)]

    def enqueue_collection(*_args: object, **_kwargs: object) -> QueuedJob:
        return QueuedJob(
            id=f"collection:engagement:{community_id}:202604191330",
            type="collection.run",
            status="duplicate",
        )

    result = await process_engagement_collection_scheduler_tick(
        session_factory=lambda: FakeSession(),
        target_loader=target_loader,
        enqueue_collection_fn=enqueue_collection,
        due_state=AlwaysDueState(),
        settings=SimpleNamespace(engagement_active_collection_interval_seconds=600),  # type: ignore[arg-type]
        now=now,
    )

    assert result["jobs_enqueued"] == 0
    assert result["duplicate_jobs"] == 1
    assert result["enqueue_failures"] == 0
    assert result["job_ids"] == [f"collection:engagement:{community_id}:202604191330"]


@pytest.mark.asyncio
async def test_engagement_collection_scheduler_records_enqueue_failure() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)

    async def target_loader(_session: object) -> list[EngagementCollectionTarget]:
        return [_collection_target(uuid4(), latest_collection_completed_at=None)]

    def enqueue_collection(*_args: object, **_kwargs: object) -> QueuedJob:
        raise RuntimeError("redis unavailable")

    result = await process_engagement_collection_scheduler_tick(
        session_factory=lambda: FakeSession(),
        target_loader=target_loader,
        enqueue_collection_fn=enqueue_collection,
        due_state=AlwaysDueState(),
        settings=SimpleNamespace(engagement_active_collection_interval_seconds=600),  # type: ignore[arg-type]
        now=now,
    )

    assert result["jobs_enqueued"] == 0
    assert result["enqueue_failures"] == 1


@pytest.mark.asyncio
async def test_engagement_collection_scheduler_initializes_future_due_without_enqueue() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
    community_id = uuid4()

    async def target_loader(_session: object) -> list[EngagementCollectionTarget]:
        return [_collection_target(community_id, latest_collection_completed_at=None)]

    def enqueue_collection(*_args: object, **_kwargs: object) -> QueuedJob:
        raise AssertionError("not-due communities should not enqueue")

    result = await process_engagement_collection_scheduler_tick(
        session_factory=lambda: FakeSession(),
        target_loader=target_loader,
        enqueue_collection_fn=enqueue_collection,
        due_state=NeverDueState(due_at=now + timedelta(minutes=5)),
        settings=SimpleNamespace(engagement_active_collection_interval_seconds=600),  # type: ignore[arg-type]
        now=now,
    )

    assert result["jobs_enqueued"] == 0
    assert result["skipped_not_due"] == 1
    assert result["skipped_recent_collection"] == 0


@pytest.mark.asyncio
async def test_engagement_collection_scheduler_skips_when_due_state_unavailable() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)

    async def target_loader(_session: object) -> list[EngagementCollectionTarget]:
        return [_collection_target(uuid4(), latest_collection_completed_at=None)]

    result = await process_engagement_collection_scheduler_tick(
        session_factory=lambda: FakeSession(),
        target_loader=target_loader,
        enqueue_collection_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no enqueue")),
        due_state=UnavailableDueState(),
        settings=SimpleNamespace(engagement_active_collection_interval_seconds=600),  # type: ignore[arg-type]
        now=now,
    )

    assert result["jobs_enqueued"] == 0
    assert result["skipped_due_state_unavailable"] == 1


def test_collection_target_skip_reason_uses_interval_boundary() -> None:
    now = datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc)
    recent = _collection_target(
        uuid4(),
        latest_collection_completed_at=datetime(2026, 4, 19, 13, 20, tzinfo=timezone.utc),
    )
    due = _collection_target(
        uuid4(),
        latest_collection_completed_at=datetime(2026, 4, 19, 13, 19, 59, tzinfo=timezone.utc),
    )

    assert collection_target_skip_reason(recent, now=now, interval_seconds=600) == "recent_collection"
    assert collection_target_skip_reason(due, now=now, interval_seconds=600) is None


def test_quiet_hours_support_overnight_windows() -> None:
    assert is_quiet_time(
        datetime(2026, 4, 19, 23, 0, tzinfo=timezone.utc),
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(6, 0),
    )
    assert is_quiet_time(
        datetime(2026, 4, 19, 5, 30, tzinfo=timezone.utc),
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(6, 0),
    )
    assert not is_quiet_time(
        datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(6, 0),
    )


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class AlwaysDueState:
    def __init__(self) -> None:
        self.marked: list[object] = []

    def collection_due(self, community_id: object, *, now: datetime) -> DueDecision:
        return DueDecision(due=True, due_at=now)

    def mark_collection_enqueued(self, community_id: object, *, now: datetime) -> datetime:
        self.marked.append(community_id)
        return now + timedelta(minutes=5)


class NeverDueState:
    def __init__(self, *, due_at: datetime) -> None:
        self.due_at = due_at

    def collection_due(self, community_id: object, *, now: datetime) -> DueDecision:
        del community_id, now
        return DueDecision(due=False, due_at=self.due_at)

    def mark_collection_enqueued(self, community_id: object, *, now: datetime) -> datetime:
        raise AssertionError("not-due communities should not be marked enqueued")


class UnavailableDueState:
    def collection_due(self, community_id: object, *, now: datetime) -> DueDecision:
        del community_id, now
        raise EngagementDueStateUnavailable("redis unavailable")

    def mark_collection_enqueued(self, community_id: object, *, now: datetime) -> datetime:
        raise AssertionError("unavailable due-state should not be marked enqueued")


def _target(
    community_id: object,
    *,
    mode: str = EngagementMode.SUGGEST.value,
    quiet_hours_start: time | None = None,
    quiet_hours_end: time | None = None,
    latest_collection_completed_at: datetime | None,
    active_candidate_count: int = 0,
) -> EngagementDetectionTarget:
    return EngagementDetectionTarget(
        community_id=community_id,  # type: ignore[arg-type]
        mode=mode,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
        latest_collection_completed_at=latest_collection_completed_at,
        active_candidate_count=active_candidate_count,
    )


def _collection_target(
    community_id: object,
    *,
    mode: str = EngagementMode.SUGGEST.value,
    quiet_hours_start: time | None = None,
    quiet_hours_end: time | None = None,
    latest_collection_completed_at: datetime | None,
    active_collection_count: int = 0,
    has_detect_permission: bool = True,
) -> EngagementCollectionTarget:
    return EngagementCollectionTarget(
        community_id=community_id,  # type: ignore[arg-type]
        mode=mode,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
        latest_collection_completed_at=latest_collection_completed_at,
        active_collection_count=active_collection_count,
        has_detect_permission=has_detect_permission,
    )
