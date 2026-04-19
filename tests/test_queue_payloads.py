from __future__ import annotations

from uuid import uuid4

from backend.queue.client import (
    QueuedJob,
    enqueue_brief_process,
    enqueue_community_join,
    enqueue_engagement_detect,
    enqueue_engagement_send,
    enqueue_seed_expansion,
    enqueue_seed_resolve,
    enqueue_telegram_entity_resolve,
)
from backend.queue.payloads import (
    AnalysisPayload,
    BriefProcessPayload,
    CollectionPayload,
    CommunityJoinPayload,
    DiscoveryPayload,
    EngagementDetectPayload,
    EngagementSendPayload,
    SeedExpandPayload,
    SeedResolvePayload,
    TelegramEntityResolvePayload,
)
from backend.workers.jobs import dispatch_job


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


def test_community_join_payload_matches_contract() -> None:
    community_id = uuid4()
    telegram_account_id = uuid4()
    payload = CommunityJoinPayload(
        community_id=community_id,
        telegram_account_id=telegram_account_id,
        requested_by="operator",
    )

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "community_id": str(community_id),
        "telegram_account_id": str(telegram_account_id),
        "requested_by": "operator",
    }


def test_engagement_detect_payload_matches_contract_defaults() -> None:
    community_id = uuid4()
    payload = EngagementDetectPayload(community_id=community_id)

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "community_id": str(community_id),
        "window_minutes": 60,
        "requested_by": None,
    }


def test_engagement_send_payload_matches_contract() -> None:
    candidate_id = uuid4()
    payload = EngagementSendPayload(candidate_id=candidate_id, approved_by="operator")

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "candidate_id": str(candidate_id),
        "approved_by": "operator",
    }


def test_enqueue_community_join_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-5", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    community_id = uuid4()
    telegram_account_id = uuid4()

    job = enqueue_community_join(
        community_id,
        requested_by="operator",
        telegram_account_id=telegram_account_id,
    )

    assert job == QueuedJob(id="job-5", type="community.join")
    assert captured == {
        "job_type": "community.join",
        "payload": {
            "community_id": str(community_id),
            "telegram_account_id": str(telegram_account_id),
            "requested_by": "operator",
        },
        "queue_name": "default",
        "job_id": None,
    }


def test_enqueue_engagement_detect_uses_engagement_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-6", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    community_id = uuid4()

    job = enqueue_engagement_detect(community_id, window_minutes=30, requested_by="operator")

    assert job == QueuedJob(id="job-6", type="engagement.detect")
    assert captured["job_type"] == "engagement.detect"
    assert captured["payload"] == {
        "community_id": str(community_id),
        "window_minutes": 30,
        "requested_by": "operator",
    }
    assert captured["queue_name"] == "engagement"
    assert str(captured["job_id"]).startswith(f"engagement.detect:{community_id}:")


def test_enqueue_engagement_send_uses_engagement_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-7", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    candidate_id = uuid4()

    job = enqueue_engagement_send(candidate_id, approved_by="operator")

    assert job == QueuedJob(id="job-7", type="engagement.send")
    assert captured == {
        "job_type": "engagement.send",
        "payload": {
            "candidate_id": str(candidate_id),
            "approved_by": "operator",
        },
        "queue_name": "engagement",
        "job_id": f"engagement.send:{candidate_id}",
    }


def test_dispatch_recognizes_engagement_job_types(monkeypatch) -> None:
    monkeypatch.setattr("backend.workers.jobs.set_job_status", lambda *_args: None)
    monkeypatch.setattr(
        "backend.workers.jobs.run_community_join",
        lambda payload: {"status": "processed", "job_type": "community.join", "payload": payload},
    )
    community_id = str(uuid4())
    candidate_id = str(uuid4())

    assert dispatch_job(
        "community.join",
        {
            "community_id": community_id,
            "telegram_account_id": None,
            "requested_by": "operator",
        },
    ) == {
        "status": "processed",
        "job_type": "community.join",
        "payload": {
            "community_id": community_id,
            "telegram_account_id": None,
            "requested_by": "operator",
        },
    }
    assert dispatch_job(
        "engagement.detect",
        {"community_id": community_id, "window_minutes": 60, "requested_by": None},
    ) == {
        "status": "stubbed",
        "job_type": "engagement.detect",
        "payload": {"community_id": community_id, "window_minutes": 60, "requested_by": None},
    }
    assert dispatch_job("engagement.send", {"candidate_id": candidate_id, "approved_by": "op"}) == {
        "status": "stubbed",
        "job_type": "engagement.send",
        "payload": {"candidate_id": candidate_id, "approved_by": "op"},
    }
