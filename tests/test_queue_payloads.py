from __future__ import annotations

from uuid import uuid4

from backend.queue.payloads import AnalysisPayload, CollectionPayload


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

