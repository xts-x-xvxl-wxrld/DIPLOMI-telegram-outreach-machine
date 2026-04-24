from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.queue.client import (
    QueuedJob,
    QueueUnavailable,
    enqueue_brief_process,
    enqueue_community_join,
    enqueue_community_snapshot,
    enqueue_engagement_detect,
    enqueue_manual_engagement_detect,
    enqueue_engagement_send,
    enqueue_engagement_target_resolve,
    enqueue_job,
    enqueue_search_plan,
    enqueue_search_rank,
    enqueue_search_retrieve,
    enqueue_seed_expansion,
    enqueue_seed_resolve,
    enqueue_telegram_entity_resolve,
)
from backend.queue.payloads import (
    AnalysisPayload,
    BriefProcessPayload,
    CommunitySnapshotPayload,
    CollectionPayload,
    CommunityJoinPayload,
    DiscoveryPayload,
    EngagementDetectPayload,
    EngagementSendPayload,
    EngagementTargetResolvePayload,
    SearchPlanPayload,
    SearchRankPayload,
    SearchRetrievePayload,
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


def test_search_plan_payload_matches_contract() -> None:
    search_run_id = uuid4()
    payload = SearchPlanPayload(search_run_id=search_run_id, requested_by="telegram_bot")

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "search_run_id": str(search_run_id),
        "requested_by": "telegram_bot",
    }


def test_search_retrieve_payload_matches_contract() -> None:
    search_run_id = uuid4()
    search_query_id = uuid4()
    payload = SearchRetrievePayload(
        search_run_id=search_run_id,
        search_query_id=search_query_id,
        requested_by="telegram_bot",
    )

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "search_run_id": str(search_run_id),
        "search_query_id": str(search_query_id),
        "requested_by": "telegram_bot",
    }


def test_search_rank_payload_matches_contract() -> None:
    search_run_id = uuid4()
    payload = SearchRankPayload(search_run_id=search_run_id, requested_by="telegram_bot")

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "search_run_id": str(search_run_id),
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


def test_enqueue_search_plan_uses_default_queue_and_stable_job_id(monkeypatch) -> None:
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
        return QueuedJob(id="job-search-plan", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    search_run_id = uuid4()

    job = enqueue_search_plan(search_run_id, requested_by="operator")

    assert job == QueuedJob(id="job-search-plan", type="search.plan")
    assert captured == {
        "job_type": "search.plan",
        "payload": {
            "search_run_id": str(search_run_id),
            "requested_by": "operator",
        },
        "queue_name": "default",
        "job_id": f"search.plan:{search_run_id}",
    }


def test_enqueue_search_retrieve_uses_default_queue_and_query_job_id(monkeypatch) -> None:
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
        return QueuedJob(id="job-search-retrieve", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    search_run_id = uuid4()
    search_query_id = uuid4()

    job = enqueue_search_retrieve(
        search_run_id,
        search_query_id,
        requested_by="operator",
    )

    assert job == QueuedJob(id="job-search-retrieve", type="search.retrieve")
    assert captured == {
        "job_type": "search.retrieve",
        "payload": {
            "search_run_id": str(search_run_id),
            "search_query_id": str(search_query_id),
            "requested_by": "operator",
        },
        "queue_name": "default",
        "job_id": f"search.retrieve:{search_run_id}:{search_query_id}",
    }


def test_enqueue_search_rank_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-search-rank", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    search_run_id = uuid4()

    job = enqueue_search_rank(search_run_id, requested_by="operator")

    assert job == QueuedJob(id="job-search-rank", type="search.rank")
    assert captured == {
        "job_type": "search.rank",
        "payload": {
            "search_run_id": str(search_run_id),
            "requested_by": "operator",
        },
        "queue_name": "default",
        "job_id": f"search.rank:{search_run_id}",
    }


def test_enqueue_community_snapshot_uses_high_queue(monkeypatch) -> None:
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
        return QueuedJob(id="snapshot-1", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    community_id = uuid4()

    job = enqueue_community_snapshot(community_id, reason="manual", requested_by="operator")

    assert job == QueuedJob(id="snapshot-1", type="community.snapshot")
    assert captured["job_type"] == "community.snapshot"
    assert captured["payload"] == {
        "community_id": str(community_id),
        "reason": "manual",
        "requested_by": "operator",
        "window_days": 90,
    }
    assert captured["queue_name"] == "high"
    assert str(captured["job_id"]).startswith(f"community.snapshot:{community_id}:")


def test_community_snapshot_payload_matches_contract() -> None:
    payload = CommunitySnapshotPayload(community_id=uuid4(), reason="manual", requested_by="operator")

    dumped = payload.model_dump(mode="json")

    assert dumped["reason"] == "manual"
    assert dumped["window_days"] == 90
    assert "community_id" in dumped


def test_collection_payload_is_reserved_for_engagement_collection() -> None:
    payload = CollectionPayload(community_id=uuid4(), reason="engagement", requested_by="operator")

    dumped = payload.model_dump(mode="json")

    assert dumped["reason"] == "engagement"


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
        "collection_run_id": None,
        "window_minutes": 60,
        "requested_by": None,
    }


def test_engagement_target_resolve_payload_matches_contract() -> None:
    target_id = uuid4()
    payload = EngagementTargetResolvePayload(target_id=target_id, requested_by="operator")

    dumped = payload.model_dump(mode="json")

    assert dumped == {
        "target_id": str(target_id),
        "requested_by": "operator",
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
        "collection_run_id": None,
        "window_minutes": 30,
        "requested_by": "operator",
    }
    assert captured["queue_name"] == "engagement"
    assert str(captured["job_id"]).startswith(f"engagement.detect:{community_id}:")


def test_enqueue_engagement_target_resolve_uses_engagement_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-target-resolve", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    target_id = uuid4()

    job = enqueue_engagement_target_resolve(target_id, requested_by="operator")

    assert job == QueuedJob(id="job-target-resolve", type="engagement_target.resolve")
    assert captured == {
        "job_type": "engagement_target.resolve",
        "payload": {
            "target_id": str(target_id),
            "requested_by": "operator",
        },
        "queue_name": "engagement",
        "job_id": f"engagement_target.resolve:{target_id}",
    }


def test_enqueue_manual_engagement_detect_uses_distinct_job_id_prefix(monkeypatch) -> None:
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
        return QueuedJob(id="job-manual-detect", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    community_id = uuid4()

    job = enqueue_manual_engagement_detect(
        community_id,
        window_minutes=45,
        requested_by="operator",
        now=datetime(2026, 4, 19, 13, 30, tzinfo=timezone.utc),
    )

    assert job == QueuedJob(id="job-manual-detect", type="engagement.detect")
    assert captured == {
        "job_type": "engagement.detect",
            "payload": {
                "community_id": str(community_id),
                "collection_run_id": None,
                "window_minutes": 45,
                "requested_by": "operator",
            },
        "queue_name": "engagement",
        "job_id": f"engagement.detect.manual:{community_id}:2026041913",
    }


def test_enqueue_engagement_detect_with_collection_run_uses_exact_job_id(monkeypatch) -> None:
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
        return QueuedJob(id="job-exact-detect", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    community_id = uuid4()
    collection_run_id = uuid4()

    job = enqueue_engagement_detect(
        community_id,
        collection_run_id=collection_run_id,
        window_minutes=10,
        requested_by=None,
    )

    assert job == QueuedJob(id="job-exact-detect", type="engagement.detect")
    assert captured == {
        "job_type": "engagement.detect",
        "payload": {
            "community_id": str(community_id),
            "collection_run_id": str(collection_run_id),
            "window_minutes": 10,
            "requested_by": None,
        },
        "queue_name": "engagement",
        "job_id": f"engagement.detect:{community_id}:{collection_run_id}",
    }


def test_enqueue_job_returns_duplicate_status_for_existing_job_id(monkeypatch) -> None:
    class FakeRetry:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    class FakeQueue:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def enqueue(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("Job already exists")

    monkeypatch.setattr(
        "backend.queue.client._queue_dependencies",
        lambda: (FakeQueue, FakeRetry, object()),
    )

    job = enqueue_job(
        "engagement.detect",
        {"community_id": str(uuid4()), "window_minutes": 60, "requested_by": None},
        queue_name="engagement",
        job_id="engagement.detect:community:2026041913",
    )

    assert job == QueuedJob(
        id="engagement.detect:community:2026041913",
        type="engagement.detect",
        status="duplicate",
    )


def test_enqueue_job_raises_queue_unavailable_for_connection_errors(monkeypatch) -> None:
    class FakeRetry:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    class FakeQueue:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def enqueue(self, *args: object, **kwargs: object) -> object:
            raise ConnectionRefusedError("Error 111 connecting to redis")

    logged: list[tuple[str, object]] = []

    monkeypatch.setattr(
        "backend.queue.client._queue_dependencies",
        lambda: (FakeQueue, FakeRetry, object()),
    )
    monkeypatch.setattr(
        "backend.queue.client.LOGGER.exception",
        lambda message, *, extra: logged.append((message, extra)),
    )

    with pytest.raises(QueueUnavailable, match="Queue backend unavailable"):
        enqueue_job(
            "engagement_target.resolve",
            {"target_id": str(uuid4()), "requested_by": "operator"},
            queue_name="engagement",
            job_id=f"engagement_target.resolve:{uuid4()}",
        )
    assert len(logged) == 1
    assert logged[0][0] == "Failed to enqueue job"
    assert logged[0][1]["job_type"] == "engagement_target.resolve"
    assert logged[0][1]["queue_name"] == "engagement"


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
        "backend.workers.jobs.run_community_snapshot",
        lambda payload: {"status": "processed", "job_type": "community.snapshot", "payload": payload},
    )
    monkeypatch.setattr(
        "backend.workers.jobs.run_community_join",
        lambda payload: {"status": "processed", "job_type": "community.join", "payload": payload},
    )
    monkeypatch.setattr(
        "backend.workers.jobs.run_engagement_detect",
        lambda payload: {"status": "processed", "job_type": "engagement.detect", "payload": payload},
    )
    monkeypatch.setattr(
        "backend.workers.jobs.run_engagement_target_resolve",
        lambda payload: {
            "status": "processed",
            "job_type": "engagement_target.resolve",
            "payload": payload,
        },
    )
    monkeypatch.setattr(
        "backend.workers.jobs.run_engagement_send",
        lambda payload: {"status": "processed", "job_type": "engagement.send", "payload": payload},
    )
    community_id = str(uuid4())
    candidate_id = str(uuid4())
    target_id = str(uuid4())

    assert dispatch_job(
        "community.snapshot",
        {
            "community_id": community_id,
            "reason": "manual",
            "requested_by": "operator",
            "window_days": 90,
        },
    ) == {
        "status": "processed",
        "job_type": "community.snapshot",
        "payload": {
            "community_id": community_id,
            "reason": "manual",
            "requested_by": "operator",
            "window_days": 90,
        },
    }
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
        "engagement_target.resolve",
        {"target_id": target_id, "requested_by": "operator"},
    ) == {
        "status": "processed",
        "job_type": "engagement_target.resolve",
        "payload": {"target_id": target_id, "requested_by": "operator"},
    }
    assert dispatch_job(
        "engagement.detect",
        {"community_id": community_id, "window_minutes": 60, "requested_by": None},
    ) == {
        "status": "processed",
        "job_type": "engagement.detect",
        "payload": {"community_id": community_id, "window_minutes": 60, "requested_by": None},
    }
    assert dispatch_job("engagement.send", {"candidate_id": candidate_id, "approved_by": "op"}) == {
        "status": "processed",
        "job_type": "engagement.send",
        "payload": {"candidate_id": candidate_id, "approved_by": "op"},
    }


def test_jobs_module_import_does_not_eagerly_import_worker_modules(monkeypatch) -> None:
    import importlib
    import sys

    jobs_module = sys.modules["backend.workers.jobs"]

    for module_name in (
        "backend.workers.brief_process",
        "backend.workers.collection",
        "backend.workers.community_join",
        "backend.workers.community_snapshot",
        "backend.workers.engagement_detect",
        "backend.workers.engagement_send",
        "backend.workers.engagement_target_resolve",
        "backend.workers.search_expand",
        "backend.workers.search_plan",
        "backend.workers.search_rank",
        "backend.workers.search_retrieve",
        "backend.workers.seed_expand",
        "backend.workers.seed_resolve",
        "backend.workers.telegram_entity_resolve",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    importlib.reload(jobs_module)

    assert jobs_module.__name__ == "backend.workers.jobs"
    assert "backend.workers.engagement_target_resolve" not in sys.modules
    assert "backend.workers.collection" not in sys.modules


def test_dispatch_recognizes_search_job_types(monkeypatch) -> None:
    monkeypatch.setattr("backend.workers.jobs.set_job_status", lambda *_args: None)
    monkeypatch.setattr(
        "backend.workers.jobs.run_search_plan",
        lambda payload: {"status": "processed", "job_type": "search.plan", "payload": payload},
    )
    monkeypatch.setattr(
        "backend.workers.jobs.run_search_retrieve",
        lambda payload: {"status": "processed", "job_type": "search.retrieve", "payload": payload},
    )
    monkeypatch.setattr(
        "backend.workers.jobs.run_search_rank",
        lambda payload: {"status": "processed", "job_type": "search.rank", "payload": payload},
    )
    search_run_id = str(uuid4())
    search_query_id = str(uuid4())

    assert dispatch_job(
        "search.plan",
        {"search_run_id": search_run_id, "requested_by": "operator"},
    ) == {
        "status": "processed",
        "job_type": "search.plan",
        "payload": {"search_run_id": search_run_id, "requested_by": "operator"},
    }
    assert dispatch_job(
        "search.retrieve",
        {
            "search_run_id": search_run_id,
            "search_query_id": search_query_id,
            "requested_by": "operator",
        },
    ) == {
        "status": "processed",
        "job_type": "search.retrieve",
        "payload": {
            "search_run_id": search_run_id,
            "search_query_id": search_query_id,
            "requested_by": "operator",
        },
    }
    assert dispatch_job(
        "search.rank",
        {"search_run_id": search_run_id, "requested_by": "operator"},
    ) == {
        "status": "processed",
        "job_type": "search.rank",
        "payload": {"search_run_id": search_run_id, "requested_by": "operator"},
    }
