from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.queue.client import QueuedJob
from backend.workers.brief_process import (
    BriefExtraction,
    BriefValidationError,
    normalize_brief_extraction,
    process_brief,
)


def test_normalize_brief_extraction_dedupes_trims_and_caps_fields() -> None:
    extraction = BriefExtraction(
        keywords=[" SaaS  founders ", "saas founders", *[f"term {index}" for index in range(20)]],
        related_phrases=[f"phrase {index}" for index in range(30)],
        language_hints=[" hu ", "HU", "en"],
        geography_hints=[f"geo {index}" for index in range(12)],
        exclusion_terms=[f"exclude {index}" for index in range(20)],
        community_types=[" group ", "channel", "GROUP", "discussion"],
    )

    normalized = normalize_brief_extraction(extraction)

    assert normalized.keywords == ["SaaS founders", *[f"term {index}" for index in range(11)]]
    assert len(normalized.related_phrases) == 20
    assert normalized.language_hints == ["hu", "en"]
    assert len(normalized.geography_hints) == 10
    assert len(normalized.exclusion_terms) == 12
    assert normalized.community_types == ["group", "channel", "discussion"]


def test_normalize_brief_extraction_requires_search_signal() -> None:
    extraction = BriefExtraction(
        language_hints=["en"],
        geography_hints=["Europe"],
        exclusion_terms=["jobs"],
        community_types=["group"],
    )

    with pytest.raises(BriefValidationError, match="keyword or related phrase"):
        normalize_brief_extraction(extraction)


@pytest.mark.asyncio
async def test_process_brief_writes_fields_without_auto_discovery(monkeypatch) -> None:
    brief_id = uuid4()
    brief = SimpleNamespace(
        raw_input="Hungarian SaaS founders",
        keywords=None,
        related_phrases=None,
        language_hints=None,
        geography_hints=None,
        exclusion_terms=None,
        community_types=None,
    )
    session = FakeSession(brief)
    monkeypatch.setattr("backend.workers.brief_process.AsyncSessionLocal", lambda: session)

    async def fake_extractor(raw_input: str) -> BriefExtraction:
        assert raw_input == "Hungarian SaaS founders"
        return BriefExtraction(
            keywords=["SaaS", "founders"],
            related_phrases=["startup marketing"],
            language_hints=["hu"],
            geography_hints=["Hungary"],
            exclusion_terms=["jobs"],
            community_types=["group", "channel"],
        )

    def fake_enqueue_discovery(*args, **kwargs) -> QueuedJob:
        raise AssertionError("discovery should not be enqueued")

    result = await process_brief(
        {
            "brief_id": str(brief_id),
            "requested_by": "operator",
            "auto_start_discovery": False,
        },
        extractor=fake_extractor,
        enqueue_discovery_fn=fake_enqueue_discovery,
    )

    assert session.committed is True
    assert brief.keywords == ["SaaS", "founders"]
    assert brief.related_phrases == ["startup marketing"]
    assert brief.language_hints == ["hu"]
    assert brief.geography_hints == ["Hungary"]
    assert brief.exclusion_terms == ["jobs"]
    assert brief.community_types == ["group", "channel"]
    assert result["discovery_job"] is None


@pytest.mark.asyncio
async def test_process_brief_enqueues_discovery_after_commit(monkeypatch) -> None:
    brief_id = uuid4()
    brief = SimpleNamespace(
        raw_input="German thesis writing communities",
        keywords=None,
        related_phrases=None,
        language_hints=None,
        geography_hints=None,
        exclusion_terms=None,
        community_types=None,
    )
    session = FakeSession(brief)
    monkeypatch.setattr("backend.workers.brief_process.AsyncSessionLocal", lambda: session)

    async def fake_extractor(raw_input: str) -> BriefExtraction:
        assert raw_input == "German thesis writing communities"
        return BriefExtraction(keywords=["thesis writing"], community_types=["group"])

    def fake_enqueue_discovery(*args, **kwargs) -> QueuedJob:
        assert session.committed is True
        assert args == (brief_id,)
        assert kwargs == {
            "requested_by": "operator",
            "limit": 50,
            "auto_expand": False,
        }
        return QueuedJob(id="discovery-job-1", type="discovery.run")

    result = await process_brief(
        {
            "brief_id": str(brief_id),
            "requested_by": "operator",
            "auto_start_discovery": True,
        },
        extractor=fake_extractor,
        enqueue_discovery_fn=fake_enqueue_discovery,
    )

    assert result["discovery_job"] == {
        "id": "discovery-job-1",
        "type": "discovery.run",
        "status": "queued",
    }


@pytest.mark.asyncio
async def test_process_brief_does_not_commit_or_enqueue_invalid_extraction(monkeypatch) -> None:
    brief_id = uuid4()
    session = FakeSession(SimpleNamespace(raw_input="too vague"))
    monkeypatch.setattr("backend.workers.brief_process.AsyncSessionLocal", lambda: session)

    async def fake_extractor(raw_input: str) -> BriefExtraction:
        return BriefExtraction(language_hints=["en"])

    def fake_enqueue_discovery(*args, **kwargs) -> QueuedJob:
        raise AssertionError("discovery should not be enqueued")

    with pytest.raises(BriefValidationError):
        await process_brief(
            {
                "brief_id": str(brief_id),
                "requested_by": "operator",
                "auto_start_discovery": True,
            },
            extractor=fake_extractor,
            enqueue_discovery_fn=fake_enqueue_discovery,
        )

    assert session.committed is False


class FakeSession:
    def __init__(self, brief: object | None) -> None:
        self.brief = brief
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def get(self, model, object_id):
        return self.brief

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
