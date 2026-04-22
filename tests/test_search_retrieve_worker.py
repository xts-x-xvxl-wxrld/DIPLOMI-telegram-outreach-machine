from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.db.enums import CommunityStatus, SearchQueryStatus, SearchRunStatus
from backend.db.models import Community, SearchCandidate, SearchCandidateEvidence, SearchQuery, SearchRun
from backend.queue.client import QueuedJob
from backend.services.search_retrieval import (
    EntitySearchEvidence,
    SearchRetrievalSummary,
    TelegramEntitySearchHit,
    mark_search_query_failed,
    retrieve_search_query,
)
from backend.services.seed_resolution import ResolverAccountRateLimited
from backend.workers.account_manager import AccountLease
from backend.workers.search_retrieve import process_search_retrieve


@pytest.mark.asyncio
async def test_retrieve_search_query_persists_candidates_and_evidence() -> None:
    search_run = _search_run()
    search_query = _search_query(search_run.id, query_text="hungarian saas")
    repository = FakeSearchRetrievalRepository(search_run, [search_query])
    rank_jobs: list[UUID] = []

    summary = await retrieve_search_query(
        repository,
        search_run_id=search_run.id,
        search_query_id=search_query.id,
        adapter=FakeAdapter(
            [
                TelegramEntitySearchHit(
                    tg_id=101,
                    username="HuSaaS",
                    title="Hungarian SaaS founders",
                    description="B2B SaaS operators in Hungary",
                    member_count=420,
                    is_group=True,
                    is_broadcast=False,
                    evidence=(
                        EntitySearchEvidence("entity_title_match", "Hungarian SaaS founders"),
                        EntitySearchEvidence("description_match", "B2B SaaS operators in Hungary"),
                    ),
                )
            ]
        ),
        requested_by="operator",
        enqueue_search_rank_fn=lambda search_run_id, **_kwargs: _rank_job(search_run_id, rank_jobs),
    )

    assert summary.query_status == SearchQueryStatus.COMPLETED.value
    assert search_run.status == SearchRunStatus.RANKING.value
    assert len(repository.communities) == 1
    assert len(repository.candidates) == 1
    assert len(repository.evidence) == 2
    assert repository.candidates[0].normalized_username == "husaas"
    assert repository.candidates[0].canonical_url == "https://t.me/husaas"
    assert repository.evidence[0].evidence_value == "Hungarian SaaS founders"
    assert rank_jobs == [search_run.id]


@pytest.mark.asyncio
async def test_retrieve_search_query_merges_duplicate_hits() -> None:
    search_run = _search_run()
    search_query = _search_query(search_run.id)
    repository = FakeSearchRetrievalRepository(search_run, [search_query])

    summary = await retrieve_search_query(
        repository,
        search_run_id=search_run.id,
        search_query_id=search_query.id,
        adapter=FakeAdapter(
            [
                TelegramEntitySearchHit(tg_id=202, username="StartupHU", title="Startup Hungary"),
                TelegramEntitySearchHit(tg_id=202, username="@startuphu", title="Startup Hungary Updates"),
            ]
        ),
        enqueue_search_rank_fn=lambda search_run_id, **_kwargs: QueuedJob(
            id=f"search.rank:{search_run_id}",
            type="search.rank",
        ),
    )

    assert summary.candidates_created == 1
    assert summary.candidates_merged == 1
    assert len(repository.candidates) == 1
    assert repository.candidates[0].raw_title == "Startup Hungary Updates"
    assert len(repository.evidence) == 2


@pytest.mark.asyncio
async def test_retrieve_search_query_counts_inaccessible_and_non_community_hits() -> None:
    search_run = _search_run()
    search_query = _search_query(search_run.id)
    repository = FakeSearchRetrievalRepository(search_run, [search_query])

    summary = await retrieve_search_query(
        repository,
        search_run_id=search_run.id,
        search_query_id=search_query.id,
        adapter=FakeAdapter(
            [
                TelegramEntitySearchHit(status="inaccessible", error_message="private result"),
                TelegramEntitySearchHit(status="not_community", username="person", title="Person"),
                TelegramEntitySearchHit(status="failed", error_message="bad result"),
            ]
        ),
        enqueue_search_rank_fn=lambda search_run_id, **_kwargs: QueuedJob(
            id=f"search.rank:{search_run_id}",
            type="search.rank",
        ),
    )

    assert summary.inaccessible_hits == 1
    assert summary.non_community_hits == 1
    assert summary.failed_hits == 1
    assert summary.candidates_created == 0
    assert search_query.status == SearchQueryStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_retrieve_search_query_preserves_existing_community_operator_decision() -> None:
    search_run = _search_run()
    search_query = _search_query(search_run.id)
    community = Community(
        id=uuid4(),
        tg_id=303,
        username="existing",
        status=CommunityStatus.APPROVED.value,
        store_messages=False,
    )
    repository = FakeSearchRetrievalRepository(search_run, [search_query], communities=[community])

    await retrieve_search_query(
        repository,
        search_run_id=search_run.id,
        search_query_id=search_query.id,
        adapter=FakeAdapter([TelegramEntitySearchHit(tg_id=303, username="existing", title="New title")]),
        enqueue_search_rank_fn=lambda search_run_id, **_kwargs: QueuedJob(
            id=f"search.rank:{search_run_id}",
            type="search.rank",
        ),
    )

    assert community.status == CommunityStatus.APPROVED.value
    assert community.title == "New title"
    assert repository.candidates[0].community_id == community.id


@pytest.mark.asyncio
async def test_mark_search_query_failed_preserves_successful_sibling_query() -> None:
    search_run = _search_run()
    completed_query = _search_query(search_run.id, status=SearchQueryStatus.COMPLETED.value)
    failed_query = _search_query(search_run.id)
    repository = FakeSearchRetrievalRepository(search_run, [completed_query, failed_query])
    rank_jobs: list[UUID] = []

    summary = await mark_search_query_failed(
        repository,
        search_run_id=search_run.id,
        search_query_id=failed_query.id,
        error_message="adapter failed",
        requested_by="operator",
        enqueue_search_rank_fn=lambda search_run_id, **_kwargs: _rank_job(search_run_id, rank_jobs),
    )

    assert summary.query_status == SearchQueryStatus.FAILED.value
    assert failed_query.error_message == "adapter failed"
    assert search_run.status == SearchRunStatus.RANKING.value
    assert rank_jobs == [search_run.id]


@pytest.mark.asyncio
async def test_search_retrieve_worker_marks_query_failed_on_flood_wait() -> None:
    search_run_id = uuid4()
    search_query_id = uuid4()
    account_id = uuid4()
    session = FakeSession()
    releases: list[dict[str, object]] = []
    marked_failures: list[str] = []

    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        assert session_arg is session
        assert purpose == "search_retrieve"
        return AccountLease(
            account_id=account_id,
            phone="+123456789",
            session_file_path="session",
            lease_owner=job_id,
            lease_expires_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )

    async def fake_retrieve(*_args: object, **_kwargs: object) -> SearchRetrievalSummary:
        raise ResolverAccountRateLimited(90, "flood wait")

    async def fake_mark_failed(*_args: object, **kwargs: object) -> SearchRetrievalSummary:
        marked_failures.append(str(kwargs["error_message"]))
        return SearchRetrievalSummary(
            search_run_id=search_run_id,
            search_query_id=search_query_id,
            query_status=SearchQueryStatus.FAILED.value,
            run_status=SearchRunStatus.RETRIEVING.value,
            error_message=str(kwargs["error_message"]),
        )

    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        assert session_arg is session
        releases.append(kwargs)

    result = await process_search_retrieve(
        {
            "search_run_id": str(search_run_id),
            "search_query_id": str(search_query_id),
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        adapter_factory=lambda lease: FakeAdapter([]),
        retrieve_search_query_fn=fake_retrieve,
        mark_search_query_failed_fn=fake_mark_failed,
    )

    assert result["status"] == "failed"
    assert marked_failures == ["flood wait"]
    assert releases[0]["outcome"] == "rate_limited"
    assert releases[0]["flood_wait_seconds"] == 90
    assert session.rollbacks == 1


def _search_run() -> SearchRun:
    now = datetime(2026, 4, 22, tzinfo=timezone.utc)
    return SearchRun(
        id=uuid4(),
        raw_query="hungarian saas",
        normalized_title="hungarian saas",
        requested_by="operator",
        status=SearchRunStatus.RETRIEVING.value,
        enabled_adapters=["telegram_entity_search"],
        language_hints=[],
        locale_hints=[],
        per_run_candidate_cap=100,
        per_adapter_caps={"telegram_entity_search": {"per_query": 25}},
        planner_metadata={},
        ranking_metadata={},
        created_at=now,
        updated_at=now,
    )


def _search_query(
    search_run_id: UUID,
    *,
    query_text: str = "hungarian saas",
    status: str = SearchQueryStatus.PENDING.value,
) -> SearchQuery:
    return SearchQuery(
        id=uuid4(),
        search_run_id=search_run_id,
        adapter="telegram_entity_search",
        query_text=query_text,
        normalized_query_key=query_text,
        include_terms=query_text.split(),
        exclusion_terms=[],
        status=status,
        planner_source="deterministic_v1",
        planner_metadata={},
        created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )


def _rank_job(search_run_id: UUID, rank_jobs: list[UUID]) -> QueuedJob:
    rank_jobs.append(search_run_id)
    return QueuedJob(id=f"search.rank:{search_run_id}", type="search.rank")


class FakeAdapter:
    def __init__(self, hits: list[TelegramEntitySearchHit]) -> None:
        self.hits = hits

    async def search_entities(self, query_text: str, *, limit: int) -> list[TelegramEntitySearchHit]:
        del query_text
        return self.hits[:limit]

    async def aclose(self) -> None:
        return None


class FakeSearchRetrievalRepository:
    def __init__(
        self,
        search_run: SearchRun,
        queries: list[SearchQuery],
        *,
        communities: list[Community] | None = None,
    ) -> None:
        self.search_run = search_run
        self.queries = {query.id: query for query in queries}
        self.communities = list(communities or [])
        self.candidates: list[SearchCandidate] = []
        self.evidence: list[SearchCandidateEvidence] = []

    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        return self.search_run if search_run_id == self.search_run.id else None

    async def get_search_query(self, search_query_id: UUID) -> SearchQuery | None:
        return self.queries.get(search_query_id)

    async def count_candidates(self, search_run_id: UUID) -> int:
        return len([candidate for candidate in self.candidates if candidate.search_run_id == search_run_id])

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return next((community for community in self.communities if community.tg_id == tg_id), None)

    async def add_community(self, community: Community) -> None:
        self.communities.append(community)

    async def find_candidate(
        self,
        *,
        search_run_id: UUID,
        community_id: UUID | None,
        normalized_username: str | None,
        canonical_url: str | None,
    ) -> SearchCandidate | None:
        for candidate in self.candidates:
            if candidate.search_run_id != search_run_id:
                continue
            if community_id is not None and candidate.community_id == community_id:
                return candidate
            if normalized_username is not None and candidate.normalized_username == normalized_username:
                return candidate
            if canonical_url is not None and candidate.canonical_url == canonical_url:
                return candidate
        return None

    async def add_candidate(self, candidate: SearchCandidate) -> None:
        self.candidates.append(candidate)

    async def add_evidence(self, evidence: SearchCandidateEvidence) -> None:
        self.evidence.append(evidence)

    async def list_query_statuses(self, search_run_id: UUID) -> list[str]:
        return [
            query.status
            for query in self.queries.values()
            if query.search_run_id == search_run_id
        ]

    async def flush(self) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
