from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from backend.queue.client import QueuedJob, enqueue_engagement_send, enqueue_job


def test_enqueue_engagement_send_uses_delayed_engagement_queue(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_enqueue_job(
        job_type: str,
        payload: dict[str, object],
        *,
        queue_name: str,
        job_id: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> QueuedJob:
        captured.update(
            {
                "job_type": job_type,
                "payload": payload,
                "queue_name": queue_name,
                "job_id": job_id,
                "scheduled_at": scheduled_at,
            }
        )
        return QueuedJob(id="job-7", type=job_type, status="scheduled")

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    candidate_id = uuid4()
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    job = enqueue_engagement_send(candidate_id, approved_by="operator", now=now)

    assert job == QueuedJob(id="job-7", type="engagement.send", status="scheduled")
    scheduled_at = captured.pop("scheduled_at")
    assert isinstance(scheduled_at, datetime)
    assert timedelta(seconds=45) <= scheduled_at - now <= timedelta(seconds=120)
    assert captured == {
        "job_type": "engagement.send",
        "payload": {
            "candidate_id": str(candidate_id),
            "approved_by": "operator",
        },
        "queue_name": "engagement",
        "job_id": f"engagement.send:{candidate_id}",
    }


def test_enqueue_engagement_send_accepts_explicit_delay(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_enqueue_job(
        job_type: str,
        payload: dict[str, object],
        *,
        queue_name: str,
        job_id: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> QueuedJob:
        captured.update({"job_id": job_id, "scheduled_at": scheduled_at, "queue_name": queue_name})
        return QueuedJob(id="send-job", type=job_type, status="scheduled")

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    candidate_id = uuid4()
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    job = enqueue_engagement_send(candidate_id, approved_by="operator", delay_seconds=60, now=now)

    assert job.status == "scheduled"
    assert captured == {
        "job_id": f"engagement.send:{candidate_id}",
        "queue_name": "engagement",
        "scheduled_at": now + timedelta(seconds=60),
    }


def test_enqueue_job_uses_rq_scheduled_registry_for_delayed_jobs(monkeypatch) -> None:
    scheduled_at = datetime(2026, 4, 30, 12, 1, tzinfo=timezone.utc)
    captured: dict[str, object] = {}

    class FakeRetry:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    class FakeJob:
        id = "scheduled-job"

    class FakeQueue:
        def __init__(self, name: str, *, connection: object) -> None:
            captured["queue_name"] = name
            captured["connection"] = connection

        def enqueue_at(
            self,
            due_at: datetime,
            worker_dispatch: str,
            job_type: str,
            payload: dict[str, object],
            **kwargs: object,
        ) -> FakeJob:
            captured.update(
                {
                    "due_at": due_at,
                    "worker_dispatch": worker_dispatch,
                    "job_type": job_type,
                    "payload": payload,
                    "kwargs": kwargs,
                }
            )
            return FakeJob()

    redis_conn = object()
    monkeypatch.setattr(
        "backend.queue.client._queue_dependencies",
        lambda: (FakeQueue, FakeRetry, redis_conn),
    )

    job = enqueue_job(
        "engagement.send",
        {"candidate_id": "candidate-1", "approved_by": "operator"},
        queue_name="engagement",
        job_id="engagement.send:candidate-1",
        scheduled_at=scheduled_at,
    )

    assert job == QueuedJob(id="scheduled-job", type="engagement.send", status="scheduled")
    assert captured["queue_name"] == "engagement"
    assert captured["due_at"] == scheduled_at
    assert captured["worker_dispatch"] == "backend.workers.jobs.dispatch_job"
    assert captured["job_type"] == "engagement.send"
    assert captured["payload"] == {"candidate_id": "candidate-1", "approved_by": "operator"}
    assert captured["kwargs"]["job_id"] == "engagement_send_candidate-1"
    assert captured["kwargs"]["meta"]["status_message"] == "scheduled"
    assert captured["kwargs"]["meta"]["scheduled_at"] == scheduled_at.isoformat()


def test_worker_runner_promotes_scheduled_jobs(monkeypatch) -> None:
    from backend.workers import runner

    captured: dict[str, object] = {}

    class FakeRedis:
        @classmethod
        def from_url(cls, redis_url: str) -> object:
            captured["redis_url"] = redis_url
            return "redis-connection"

    class FakeQueue:
        def __init__(self, name: str, *, connection: object) -> None:
            captured.setdefault("queues", []).append((name, connection))

    class FakeWorker:
        def __init__(self, queues: list[object], *, connection: object) -> None:
            captured["worker_queues"] = queues
            captured["worker_connection"] = connection

        def work(self, **kwargs: object) -> None:
            captured["work_kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=FakeRedis))
    monkeypatch.setitem(sys.modules, "rq", SimpleNamespace(Queue=FakeQueue, Worker=FakeWorker))
    monkeypatch.setattr(runner, "get_settings", lambda: SimpleNamespace(redis_url="redis://test/0"))

    runner.main()

    assert captured["redis_url"] == "redis://test/0"
    assert captured["work_kwargs"] == {"with_scheduler": True}
