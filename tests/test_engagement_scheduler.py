from __future__ import annotations

from datetime import datetime, time, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.db.enums import EngagementMode
from backend.queue.client import QueuedJob
from backend.workers.engagement_scheduler import (
    EngagementDetectionTarget,
    detection_target_skip_reason,
    is_quiet_time,
    process_engagement_scheduler_tick,
)


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
