from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.queue.client import QueuedJob, enqueue_collection


def test_enqueue_engagement_collection_uses_minute_bucket_job_id(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_enqueue_job(
        job_type: str,
        payload: dict[str, object],
        *,
        queue_name: str,
        job_id: str | None = None,
    ) -> QueuedJob:
        captured.update(
            {
                "job_type": job_type,
                "payload": payload,
                "queue_name": queue_name,
                "job_id": job_id,
            }
        )
        return QueuedJob(id="collection-job", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    community_id = uuid4()

    job = enqueue_collection(
        community_id,
        reason="engagement",
        requested_by=None,
        now=datetime(2026, 4, 19, 13, 30, 45, tzinfo=timezone.utc),
    )

    assert job == QueuedJob(id="collection-job", type="collection.run")
    assert captured == {
        "job_type": "collection.run",
        "payload": {
            "community_id": str(community_id),
            "reason": "engagement",
            "requested_by": None,
            "window_days": 90,
        },
        "queue_name": "scheduled",
        "job_id": f"collection:engagement:{community_id}:202604191330",
    }
