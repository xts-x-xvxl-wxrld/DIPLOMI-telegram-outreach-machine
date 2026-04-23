from __future__ import annotations

from uuid import uuid4

from backend.queue.client import QueuedJob, enqueue_search_expand
from backend.queue.payloads import SearchExpandPayload
from backend.workers.jobs import dispatch_job


def test_search_expand_payload_matches_contract() -> None:
    search_run_id = uuid4()
    root_candidate_id = uuid4()
    seed_group_id = uuid4()
    payload = SearchExpandPayload(
        search_run_id=search_run_id,
        root_search_candidate_ids=[root_candidate_id],
        seed_group_ids=[seed_group_id],
        depth=1,
        requested_by="telegram_bot",
        max_roots=3,
        max_neighbors_per_root=20,
        max_candidates_per_adapter=15,
    )

    assert payload.model_dump(mode="json") == {
        "search_run_id": str(search_run_id),
        "root_search_candidate_ids": [str(root_candidate_id)],
        "seed_group_ids": [str(seed_group_id)],
        "depth": 1,
        "requested_by": "telegram_bot",
        "max_roots": 3,
        "max_neighbors_per_root": 20,
        "max_candidates_per_adapter": 15,
    }


def test_enqueue_search_expand_uses_default_queue(monkeypatch) -> None:
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
        return QueuedJob(id="job-search-expand", type=job_type)

    monkeypatch.setattr("backend.queue.client.enqueue_job", fake_enqueue_job)
    search_run_id = uuid4()
    root_candidate_id = uuid4()
    seed_group_id = uuid4()

    job = enqueue_search_expand(
        search_run_id,
        root_search_candidate_ids=[root_candidate_id],
        seed_group_ids=[seed_group_id],
        requested_by="operator",
        max_roots=3,
    )

    assert job == QueuedJob(id="job-search-expand", type="search.expand")
    assert captured == {
        "job_type": "search.expand",
        "payload": {
            "search_run_id": str(search_run_id),
            "root_search_candidate_ids": [str(root_candidate_id)],
            "seed_group_ids": [str(seed_group_id)],
            "depth": 1,
            "requested_by": "operator",
            "max_roots": 3,
            "max_neighbors_per_root": 50,
            "max_candidates_per_adapter": 50,
        },
        "queue_name": "default",
        "job_id": None,
    }


def test_dispatch_recognizes_search_expand_job(monkeypatch) -> None:
    monkeypatch.setattr("backend.workers.jobs.set_job_status", lambda *_args: None)
    monkeypatch.setattr(
        "backend.workers.jobs.run_search_expand",
        lambda payload: {"status": "processed", "job_type": "search.expand", "payload": payload},
    )
    payload = {
        "search_run_id": str(uuid4()),
        "root_search_candidate_ids": [],
        "seed_group_ids": [],
        "depth": 1,
        "requested_by": "operator",
        "max_roots": 5,
        "max_neighbors_per_root": 50,
        "max_candidates_per_adapter": 50,
    }

    assert dispatch_job("search.expand", payload) == {
        "status": "processed",
        "job_type": "search.expand",
        "payload": payload,
    }
