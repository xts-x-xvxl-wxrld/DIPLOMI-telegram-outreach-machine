from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.queue.client import QueuedJob, enqueue_account_health_refresh
from backend.queue.payloads import AccountHealthRefreshPayload
from backend.workers.jobs import dispatch_job


def test_account_health_refresh_payload_defaults_to_all_accounts() -> None:
    payload = AccountHealthRefreshPayload()

    assert payload.model_dump(mode="json") == {
        "account_ids": [],
        "spot_check_limit": 2,
    }


def test_enqueue_account_health_refresh_uses_eight_hour_job_bucket(monkeypatch) -> None:
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
        return QueuedJob(id="account-health-job", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    account_id = uuid4()

    job = enqueue_account_health_refresh(
        account_ids=[account_id],
        spot_check_limit=1,
        now=datetime(2026, 4, 30, 10, 30, tzinfo=timezone.utc),
    )

    assert job == QueuedJob(id="account-health-job", type="account.health_refresh")
    assert captured == {
        "job_type": "account.health_refresh",
        "payload": {
            "account_ids": [str(account_id)],
            "spot_check_limit": 1,
        },
        "queue_name": "default",
        "job_id": "account.health_refresh:2026043008",
    }


def test_dispatch_recognizes_account_health_refresh(monkeypatch) -> None:
    monkeypatch.setattr("backend.workers.jobs.set_job_status", lambda *_args: None)
    monkeypatch.setattr(
        "backend.workers.jobs.run_account_health_refresh",
        lambda payload: {"status": "processed", "job_type": "account.health_refresh", "payload": payload},
    )

    assert dispatch_job("account.health_refresh", {"account_ids": [], "spot_check_limit": 2}) == {
        "status": "processed",
        "job_type": "account.health_refresh",
        "payload": {"account_ids": [], "spot_check_limit": 2},
    }
