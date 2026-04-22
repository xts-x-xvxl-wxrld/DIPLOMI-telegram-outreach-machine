from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.deps import settings_dep
from backend.api.routes.search import (
    get_search_run_candidates,
    get_search_run_detail,
    get_search_run_queries,
    get_search_runs,
    post_search_candidate_review,
    post_search_rerank_job,
    post_search_run,
)
from backend.api.schemas import SearchCandidateReviewRequest, SearchRunCreateRequest
from backend.db.enums import SearchCandidateStatus, SearchReviewAction, SearchRunStatus
from backend.db.models import SearchCandidate, SearchQuery, SearchReview, SearchRun
from backend.queue.client import QueuedJob, QueueUnavailable
from backend.services.search import (
    SearchCandidateEvidenceSummaryView,
    SearchCandidateListItemView,
    SearchCandidateListResult,
    SearchRunCountsView,
    SearchRunListItemView,
    SearchRunListResult,
)


def test_search_routes_require_api_auth() -> None:
    app = create_app()
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace(bot_api_token="token")
    client = TestClient(app)

    response = client.get("/api/search-runs")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_search_run_persists_run_and_enqueues_search_plan(monkeypatch) -> None:
    db = FakeDb()
    captured: dict[str, object] = {}

    def fake_enqueue(search_run_id: object, *, requested_by: str | None = None) -> QueuedJob:
        captured.update({"search_run_id": search_run_id, "requested_by": requested_by})
        return QueuedJob(id="search-plan-job", type="search.plan")

    monkeypatch.setattr("backend.api.routes.search.enqueue_search_plan", fake_enqueue)

    response = await post_search_run(
        SearchRunCreateRequest(
            query="  Hungarian SaaS founders  ",
            requested_by="telegram:123",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.search_run.raw_query == "Hungarian SaaS founders"
    assert response.search_run.status == SearchRunStatus.DRAFT.value
    assert response.search_run.enabled_adapters == ["telegram_entity_search"]
    assert response.job.id == "search-plan-job"
    assert captured["requested_by"] == "telegram:123"
    assert db.commits == 1
    assert isinstance(db.added[0], SearchRun)


@pytest.mark.asyncio
async def test_post_search_run_returns_503_when_queue_is_unavailable(monkeypatch) -> None:
    db = FakeDb()

    def fake_enqueue(search_run_id: object, *, requested_by: str | None = None) -> QueuedJob:
        del search_run_id, requested_by
        raise QueueUnavailable("queue offline")

    monkeypatch.setattr("backend.api.routes.search.enqueue_search_plan", fake_enqueue)

    with pytest.raises(HTTPException) as exc_info:
        await post_search_run(
            SearchRunCreateRequest(query="Founder communities"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 503
    assert db.commits == 0


@pytest.mark.asyncio
async def test_get_search_runs_returns_contract_fields(monkeypatch) -> None:
    created_at = datetime(2026, 4, 22, tzinfo=timezone.utc)
    run_id = uuid4()

    async def fake_list(db: object, **kwargs: object) -> SearchRunListResult:
        assert db is not None
        assert kwargs == {
            "status": "completed",
            "requested_by": "telegram:123",
            "limit": 5,
            "offset": 10,
        }
        return SearchRunListResult(
            items=[
                SearchRunListItemView(
                    id=run_id,
                    raw_query="Hungarian SaaS founders",
                    normalized_title="Hungarian SaaS founders",
                    status="completed",
                    query_count=3,
                    candidate_count=12,
                    promoted_count=1,
                    rejected_count=2,
                    last_error=None,
                    created_at=created_at,
                    completed_at=created_at,
                )
            ],
            limit=5,
            offset=10,
            total=21,
        )

    monkeypatch.setattr("backend.api.routes.search.list_search_runs", fake_list)

    response = await get_search_runs(
        FakeDb(),  # type: ignore[arg-type]
        status="completed",
        requested_by="telegram:123",
        limit=5,
        offset=10,
    )

    assert response.total == 21
    assert response.items[0].id == run_id
    assert response.items[0].candidate_count == 12


@pytest.mark.asyncio
async def test_get_search_run_detail_returns_run_and_counts(monkeypatch) -> None:
    run_id = uuid4()
    search_run = SearchRun(
        id=run_id,
        raw_query="Hungarian SaaS founders",
        normalized_title="Hungarian SaaS founders",
        status=SearchRunStatus.RETRIEVING.value,
        enabled_adapters=["telegram_entity_search"],
        language_hints=["hu"],
        locale_hints=["HU"],
        per_run_candidate_cap=100,
        per_adapter_caps={"telegram_entity_search": {"per_query": 25}},
        planner_source="deterministic_v1",
        planner_metadata={},
        ranking_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    async def fake_get(db: object, *, search_run_id: object) -> SearchRun:
        assert db is not None
        assert search_run_id == run_id
        return search_run

    async def fake_counts(db: object, *, search_run_id: object) -> SearchRunCountsView:
        assert db is not None
        assert search_run_id == run_id
        return SearchRunCountsView(queries=3, queries_completed=1, candidates=8, promoted=1)

    monkeypatch.setattr("backend.api.routes.search.get_search_run", fake_get)
    monkeypatch.setattr("backend.api.routes.search.get_search_run_counts", fake_counts)

    response = await get_search_run_detail(run_id, FakeDb())  # type: ignore[arg-type]

    assert response.search_run.id == run_id
    assert response.counts.queries == 3
    assert response.counts.candidates == 8


@pytest.mark.asyncio
async def test_get_search_run_queries_lists_planner_outputs(monkeypatch) -> None:
    run_id = uuid4()
    query = SearchQuery(
        id=uuid4(),
        search_run_id=run_id,
        adapter="telegram_entity_search",
        query_text="hungarian saas founders",
        normalized_query_key="hungarian saas founders",
        language_hint="en",
        locale_hint="HU",
        include_terms=["hungarian", "saas"],
        exclusion_terms=[],
        status="completed",
        planner_source="deterministic_v1",
        planner_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    async def fake_list(db: object, *, search_run_id: object) -> list[SearchQuery]:
        assert db is not None
        assert search_run_id == run_id
        return [query]

    monkeypatch.setattr("backend.api.routes.search.list_search_queries", fake_list)

    response = await get_search_run_queries(run_id, FakeDb())  # type: ignore[arg-type]

    assert response.total == 1
    assert response.items[0].query_text == "hungarian saas founders"


@pytest.mark.asyncio
async def test_get_search_run_candidates_returns_empty_until_retrieval_exists(monkeypatch) -> None:
    run_id = uuid4()

    async def fake_list(db: object, **kwargs: object) -> SearchCandidateListResult:
        assert db is not None
        assert kwargs == {
            "search_run_id": run_id,
            "statuses": None,
            "limit": 10,
            "offset": 0,
            "include_archived": False,
            "include_rejected": False,
        }
        return SearchCandidateListResult(items=[], limit=10, offset=0, total=0)

    monkeypatch.setattr("backend.api.routes.search.list_search_candidates", fake_list)

    response = await get_search_run_candidates(  # type: ignore[arg-type]
        run_id,
        FakeDb(),
        status=None,
        limit=10,
        offset=0,
        include_archived=False,
        include_rejected=False,
    )

    assert response.items == []
    assert response.total == 0


@pytest.mark.asyncio
async def test_get_search_run_candidates_returns_ranked_items(monkeypatch) -> None:
    run_id = uuid4()
    candidate_id = uuid4()

    async def fake_list(db: object, **kwargs: object) -> SearchCandidateListResult:
        assert db is not None
        assert kwargs["search_run_id"] == run_id
        return SearchCandidateListResult(
            items=[
                SearchCandidateListItemView(
                    id=candidate_id,
                    search_run_id=run_id,
                    status=SearchCandidateStatus.CANDIDATE.value,
                    community_id=None,
                    title="Founder Circle",
                    username="founders",
                    telegram_url="https://t.me/founders",
                    description="Public founder chat",
                    member_count=1234,
                    score=Decimal("72.5"),
                    ranking_version="search_rank_v1",
                    score_components={"title_username_match": 40},
                    evidence_summary=SearchCandidateEvidenceSummaryView(
                        total=1,
                        types=["entity_title_match"],
                        snippets=["Founder match"],
                    ),
                    first_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
                    last_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
                )
            ],
            limit=10,
            offset=0,
            total=1,
        )

    monkeypatch.setattr("backend.api.routes.search.list_search_candidates", fake_list)

    response = await get_search_run_candidates(  # type: ignore[arg-type]
        run_id,
        FakeDb(),
        status=None,
        limit=10,
        offset=0,
        include_archived=False,
        include_rejected=False,
    )

    assert response.total == 1
    assert response.items[0].score == Decimal("72.5")
    assert response.items[0].evidence_summary.types == ["entity_title_match"]


@pytest.mark.asyncio
async def test_post_search_rerank_job_enqueues_search_rank(monkeypatch) -> None:
    run_id = uuid4()
    db = FakeDb(
        search_run=SearchRun(
            id=run_id,
            raw_query="Hungarian SaaS founders",
            normalized_title="Hungarian SaaS founders",
            requested_by="telegram:123",
            status=SearchRunStatus.COMPLETED.value,
            enabled_adapters=["telegram_entity_search"],
            language_hints=[],
            locale_hints=[],
            per_run_candidate_cap=100,
            per_adapter_caps={},
            planner_metadata={},
            ranking_metadata={},
            created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )
    )
    captured: dict[str, object] = {}

    def fake_enqueue(search_run_id: object, *, requested_by: str | None = None) -> QueuedJob:
        captured.update({"search_run_id": search_run_id, "requested_by": requested_by})
        return QueuedJob(id="search-rank-job", type="search.rank")

    monkeypatch.setattr("backend.api.routes.search.enqueue_search_rank", fake_enqueue)

    response = await post_search_rerank_job(run_id, db)  # type: ignore[arg-type]

    assert response.job.id == "search-rank-job"
    assert captured == {"search_run_id": run_id, "requested_by": "telegram:123"}


@pytest.mark.asyncio
async def test_post_search_candidate_review_updates_run_scoped_status() -> None:
    candidate = SearchCandidate(
        id=uuid4(),
        search_run_id=uuid4(),
        status=SearchCandidateStatus.CANDIDATE.value,
        community_id=None,
        score_components={},
        first_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    db = FakeDb(candidate=candidate)

    response = await post_search_candidate_review(
        candidate.id,
        SearchCandidateReviewRequest(
            action=SearchReviewAction.PROMOTE,
            requested_by="telegram:123",
            notes="Looks relevant",
        ),
        db,  # type: ignore[arg-type]
    )

    assert response.candidate.status == SearchCandidateStatus.PROMOTED.value
    assert response.candidate.last_reviewed_by == "telegram:123"
    assert response.review.action == SearchReviewAction.PROMOTE.value
    assert response.review.scope == "run"
    assert db.commits == 1
    assert isinstance(db.added[0], SearchReview)


@pytest.mark.asyncio
async def test_post_search_candidate_review_rejects_unimplemented_global_actions() -> None:
    candidate = SearchCandidate(
        id=uuid4(),
        search_run_id=uuid4(),
        status=SearchCandidateStatus.CANDIDATE.value,
        community_id=None,
        score_components={},
        first_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    db = FakeDb(candidate=candidate)

    with pytest.raises(HTTPException) as exc_info:
        await post_search_candidate_review(
            candidate.id,
            SearchCandidateReviewRequest(action=SearchReviewAction.GLOBAL_REJECT),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "unsupported_review_action"
    assert db.commits == 0


class FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items)


class FakeDb:
    def __init__(
        self,
        *,
        search_run: SearchRun | None = None,
        candidate: SearchCandidate | None = None,
    ) -> None:
        self.search_run = search_run
        self.candidate = candidate
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model: object, item_id: object) -> object | None:
        if model is SearchRun:
            return self.search_run
        if model is SearchCandidate:
            return self.candidate
        return None

    async def scalar(self, statement: object) -> object | None:
        del statement
        return None

    async def scalars(self, statement: object) -> FakeScalarResult:
        del statement
        return FakeScalarResult([])

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1
