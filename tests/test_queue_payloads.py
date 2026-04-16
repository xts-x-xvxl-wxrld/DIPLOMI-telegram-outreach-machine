from __future__ import annotations

from uuid import uuid4

from backend.queue.client import (
    QueuedJob,
    enqueue_brief_process,
    enqueue_seed_expansion,
    enqueue_seed_resolve,
    enqueue_telegram_entity_resolve,
)
from backend.queue.payloads import (
    AnalysisPayload,
    BriefProcessPayload,
    CollectionPayload,
    DiscoveryPayload,
    SeedExpandPayload,
    SeedResolvePayload,
    TelegramEntityResolvePayload,
)


def test_brief_process_payload_matches_contract() -> None:
    brief_id = uuid4()
    payload = BriefProcessPayload(
        brief_id=brief_id,
        requested_by="operator",
        auto_start_discovery=False,
    )

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "brief_id": str(brief_id),
        "requested_by": "operator",
        "auto_start_discovery": False,
    }


def test_discovery_payload_does_not_auto_expand_by_default() -> None:
    payload = DiscoveryPayload(brief_id=uuid4(), requested_by="operator")

    dumped = payload.model_dump(mode="json")

    assert dumped["limit"] == 50
    assert dumped["auto_expand"] is False


def test_seed_resolve_payload_matches_contract() -> None:
    seed_group_id = uuid4()
    payload = SeedResolvePayload(
        seed_group_id=seed_group_id,
        requested_by="operator",
        limit=25,
        retry_failed=True,
    )

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "seed_group_id": str(seed_group_id),
        "requested_by": "operator",
        "limit": 25,
        "retry_failed": True,
    }


def test_seed_expand_payload_matches_contract() -> None:
    seed_group_id = uuid4()
    brief_id = uuid4()
    payload = SeedExpandPayload(
        seed_group_id=seed_group_id,
        brief_id=brief_id,
        depth=1,
        requested_by="operator",
    )

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "seed_group_id": str(seed_group_id),
        "brief_id": str(brief_id),
        "depth": 1,
        "requested_by": "operator",
    }


def test_telegram_entity_resolve_payload_matches_contract() -> None:
    intake_id = uuid4()
    payload = TelegramEntityResolvePayload(intake_id=intake_id, requested_by="telegram_bot")

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "intake_id": str(intake_id),
        "requested_by": "telegram_bot",
    }


def test_enqueue_brief_process_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-1", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    brief_id = uuid4()

    job = enqueue_brief_process(
        brief_id,
        requested_by="operator",
        auto_start_discovery=False,
    )

    assert job == QueuedJob(id="job-1", type="brief.process")
    assert captured == {
        "job_type": "brief.process",
        "payload": {
            "brief_id": str(brief_id),
            "requested_by": "operator",
            "auto_start_discovery": False,
        },
        "queue_name": "default",
        "job_id": None,
    }


def test_enqueue_seed_resolve_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-2", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    seed_group_id = uuid4()

    job = enqueue_seed_resolve(
        seed_group_id,
        requested_by="operator",
        limit=10,
        retry_failed=True,
    )

    assert job == QueuedJob(id="job-2", type="seed.resolve")
    assert captured == {
        "job_type": "seed.resolve",
        "payload": {
            "seed_group_id": str(seed_group_id),
            "requested_by": "operator",
            "limit": 10,
            "retry_failed": True,
        },
        "queue_name": "default",
        "job_id": None,
    }


def test_enqueue_seed_expansion_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-3", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    seed_group_id = uuid4()

    job = enqueue_seed_expansion(
        seed_group_id,
        None,
        depth=1,
        requested_by="operator",
    )

    assert job == QueuedJob(id="job-3", type="seed.expand")
    assert captured == {
        "job_type": "seed.expand",
        "payload": {
            "seed_group_id": str(seed_group_id),
            "brief_id": None,
            "depth": 1,
            "requested_by": "operator",
        },
        "queue_name": "default",
        "job_id": None,
    }


def test_enqueue_telegram_entity_resolve_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-4", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    intake_id = uuid4()

    job = enqueue_telegram_entity_resolve(intake_id, requested_by="telegram_bot")

    assert job == QueuedJob(id="job-4", type="telegram_entity.resolve")
    assert captured == {
        "job_type": "telegram_entity.resolve",
        "payload": {
            "intake_id": str(intake_id),
            "requested_by": "telegram_bot",
        },
        "queue_name": "default",
        "job_id": None,
    }


def test_collection_payload_matches_contract() -> None:
    payload = CollectionPayload(community_id=uuid4(), reason="manual", requested_by="operator")

    dumped = payload.model_dump(mode="json")

    assert dumped["reason"] == "manual"
    assert dumped["window_days"] == 90
    assert "community_id" in dumped


def test_analysis_payload_uses_collection_run_id_only() -> None:
    payload = AnalysisPayload(collection_run_id=uuid4(), requested_by=None)

    dumped = payload.model_dump(mode="json")

    assert set(dumped) == {"collection_run_id", "requested_by"}
