from __future__ import annotations

from datetime import datetime, timezone

from backend.core.settings import Settings
from backend.queue.client import QueuedJob
from backend.workers.engagement_scheduler import process_account_health_refresh_scheduler_tick


def test_settings_default_account_health_refresh_interval_is_eight_hours() -> None:
    settings = Settings(_env_file=None)

    assert settings.engagement_account_health_refresh_interval_seconds == 28800


def test_account_health_refresh_scheduler_enqueues_refresh_job() -> None:
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
    captured: dict[str, object] = {}

    def enqueue_health_refresh(*, now: datetime) -> QueuedJob:
        captured["now"] = now
        return QueuedJob(id="account.health_refresh:2026043012", type="account.health_refresh")

    result = process_account_health_refresh_scheduler_tick(
        enqueue_health_refresh_fn=enqueue_health_refresh,
        now=now,
    )

    assert result == {
        "status": "processed",
        "job_type": "account.health_refresh_scheduler",
        "jobs_enqueued": 1,
        "enqueue_failures": 0,
        "job_ids": ["account.health_refresh:2026043012"],
    }
    assert captured == {"now": now}


def test_account_health_refresh_scheduler_treats_duplicate_job_as_safe() -> None:
    def enqueue_health_refresh(*, now: datetime) -> QueuedJob:
        del now
        return QueuedJob(
            id="account.health_refresh:2026043012",
            type="account.health_refresh",
            status="duplicate",
        )

    result = process_account_health_refresh_scheduler_tick(
        enqueue_health_refresh_fn=enqueue_health_refresh,
        now=datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc),
    )

    assert result["jobs_enqueued"] == 0
    assert result["enqueue_failures"] == 0
    assert result["job_ids"] == ["account.health_refresh:2026043012"]
