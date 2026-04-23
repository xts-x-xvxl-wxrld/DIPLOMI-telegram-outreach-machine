from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.db.enums import SearchCandidateStatus, SearchEvidenceType, SearchRunStatus
from backend.db.models import SearchCandidate, SearchCandidateEvidence, SearchRun
from backend.services.search_ranking import RANKING_VERSION, rank_search_candidates
from backend.workers.search_rank import process_search_rank


@pytest.mark.asyncio
async def test_rank_search_candidates_persists_scores_and_explanations() -> None:
    search_run = _search_run()
    candidate = _candidate(
        search_run.id,
        title="Hungarian SaaS founders",
        username="husaas",
        member_count=1200,
    )
    first_query_id = uuid4()
    second_query_id = uuid4()
    repository = FakeSearchRankingRepository(
        search_run,
        [candidate],
        [
            _evidence(
                search_run.id,
                candidate.id,
                SearchEvidenceType.ENTITY_TITLE_MATCH.value,
                "Hungarian SaaS founders",
                search_query_id=first_query_id,
                query_text="hungarian saas",
            ),
            _evidence(
                search_run.id,
                candidate.id,
                SearchEvidenceType.DESCRIPTION_MATCH.value,
                "B2B SaaS operators in Hungary",
                search_query_id=second_query_id,
                query_text="saas operators",
            ),
        ],
    )

    summary = await rank_search_candidates(
        repository,
        search_run_id=search_run.id,
        requested_by="operator",
    )

    assert summary.ranking_version == RANKING_VERSION
    assert summary.run_status == SearchRunStatus.COMPLETED.value
    assert search_run.status == SearchRunStatus.COMPLETED.value
    assert search_run.ranking_version == RANKING_VERSION
    assert candidate.ranking_version == RANKING_VERSION
    assert candidate.score == Decimal("90.000")
    assert candidate.score_components == {
        "title_username_match": 40,
        "description_match": 25,
        "cross_query_confirmation": 15,
        "cross_adapter_confirmation": 0,
        "activity_hint": 10,
        "prior_run_rejection_penalty": 0,
        "spam_penalty": 0,
    }
    assert search_run.ranking_metadata["component_weights"]["spam_penalty"] == -30
    assert search_run.ranking_metadata["component_shape"] == [
        "title_username_match",
        "description_match",
        "cross_query_confirmation",
        "cross_adapter_confirmation",
        "activity_hint",
        "prior_run_rejection_penalty",
        "spam_penalty",
    ]
    assert repository.flushes == 1


@pytest.mark.asyncio
async def test_rank_search_candidates_uses_penalties_and_confirmation_components() -> None:
    search_run = _search_run()
    community_id = uuid4()
    candidate = _candidate(
        search_run.id,
        community_id=community_id,
        title="Guaranteed profit pump group!!!!",
        member_count=300,
    )
    repository = FakeSearchRankingRepository(
        search_run,
        [candidate],
        [
            _evidence(
                search_run.id,
                candidate.id,
                SearchEvidenceType.ENTITY_USERNAME_MATCH.value,
                "@profitpump",
                adapter="telegram_entity_search",
            ),
            _evidence(
                search_run.id,
                candidate.id,
                SearchEvidenceType.WEB_RESULT.value,
                "https://t.me/profitpump",
                adapter="web_search_tme",
            ),
        ],
        prior_rejected_community_ids={community_id},
    )

    await rank_search_candidates(repository, search_run_id=search_run.id)

    assert candidate.score == Decimal("2.500")
    assert candidate.score_components["title_username_match"] == 40
    assert candidate.score_components["cross_adapter_confirmation"] == 10
    assert candidate.score_components["activity_hint"] == 7.5
    assert candidate.score_components["prior_run_rejection_penalty"] == -25
    assert candidate.score_components["spam_penalty"] == -30


@pytest.mark.asyncio
async def test_rank_search_candidates_orders_with_deterministic_tie_breakers() -> None:
    search_run = _search_run()
    later = datetime(2026, 4, 22, 0, 5, tzinfo=timezone.utc)
    promoted = _candidate(
        search_run.id,
        status=SearchCandidateStatus.PROMOTED.value,
        title="Beta",
    )
    candidate_a = _candidate(search_run.id, title="Alpha")
    candidate_null_title = _candidate(search_run.id, title=None)
    rejected = _candidate(
        search_run.id,
        status=SearchCandidateStatus.REJECTED.value,
        title="Alpha",
        first_seen_at=later,
    )
    evidence = [
        _evidence(search_run.id, item.id, SearchEvidenceType.ENTITY_TITLE_MATCH.value, item.raw_title)
        for item in [promoted, candidate_a, candidate_null_title, rejected]
    ]
    repository = FakeSearchRankingRepository(
        search_run,
        [rejected, candidate_null_title, candidate_a, promoted],
        evidence,
    )

    summary = await rank_search_candidates(repository, search_run_id=search_run.id)

    assert summary.ranked_candidate_ids == [
        promoted.id,
        candidate_a.id,
        candidate_null_title.id,
        rejected.id,
    ]
    assert search_run.ranking_metadata["ranked_candidate_ids"] == [
        str(promoted.id),
        str(candidate_a.id),
        str(candidate_null_title.id),
        str(rejected.id),
    ]


@pytest.mark.asyncio
async def test_process_search_rank_validates_payload_and_commits() -> None:
    search_run = _search_run()
    session = FakeSession()
    calls: list[UUID] = []

    async def fake_rank(repository: object, **kwargs: object):
        assert repository is not None
        calls.append(kwargs["search_run_id"])  # type: ignore[arg-type]
        return await rank_search_candidates(
            FakeSearchRankingRepository(search_run, [], []),
            search_run_id=kwargs["search_run_id"],  # type: ignore[arg-type]
            requested_by=kwargs["requested_by"],  # type: ignore[arg-type]
        )

    result = await process_search_rank(
        {"search_run_id": str(search_run.id), "requested_by": "operator"},
        session_factory=lambda: session,
        rank_search_candidates_fn=fake_rank,
    )

    assert result["status"] == "ranked"
    assert result["job_type"] == "search.rank"
    assert calls == [search_run.id]
    assert session.commits == 1
    assert session.rollbacks == 0


def _search_run() -> SearchRun:
    now = datetime(2026, 4, 22, tzinfo=timezone.utc)
    return SearchRun(
        id=uuid4(),
        raw_query="hungarian saas",
        normalized_title="hungarian saas",
        requested_by="operator",
        status=SearchRunStatus.RANKING.value,
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


def _candidate(
    search_run_id: UUID,
    *,
    community_id: UUID | None = None,
    status: str = SearchCandidateStatus.CANDIDATE.value,
    title: str | None = "Candidate",
    username: str | None = "candidate",
    member_count: int | None = None,
    first_seen_at: datetime | None = None,
) -> SearchCandidate:
    now = first_seen_at or datetime(2026, 4, 22, tzinfo=timezone.utc)
    return SearchCandidate(
        id=uuid4(),
        search_run_id=search_run_id,
        community_id=community_id,
        status=status,
        normalized_username=username,
        canonical_url=f"https://t.me/{username}" if username else None,
        raw_title=title,
        raw_member_count=member_count,
        score_components={},
        first_seen_at=now,
        last_seen_at=now,
    )


def _evidence(
    search_run_id: UUID,
    candidate_id: UUID,
    evidence_type: str,
    value: str | None,
    *,
    search_query_id: UUID | None = None,
    query_text: str | None = "hungarian saas",
    adapter: str = "telegram_entity_search",
) -> SearchCandidateEvidence:
    return SearchCandidateEvidence(
        id=uuid4(),
        search_run_id=search_run_id,
        search_candidate_id=candidate_id,
        search_query_id=search_query_id,
        adapter=adapter,
        query_text=query_text,
        evidence_type=evidence_type,
        evidence_value=value,
        evidence_metadata={},
        captured_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )


class FakeSearchRankingRepository:
    def __init__(
        self,
        search_run: SearchRun,
        candidates: list[SearchCandidate],
        evidence: list[SearchCandidateEvidence],
        *,
        prior_rejected_community_ids: set[UUID] | None = None,
    ) -> None:
        self.search_run = search_run
        self.candidates = candidates
        self.evidence = evidence
        self.prior_rejected_community_ids = prior_rejected_community_ids or set()
        self.flushes = 0

    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        return self.search_run if search_run_id == self.search_run.id else None

    async def list_candidates(self, search_run_id: UUID) -> list[SearchCandidate]:
        return [candidate for candidate in self.candidates if candidate.search_run_id == search_run_id]

    async def list_evidence(self, search_run_id: UUID) -> list[SearchCandidateEvidence]:
        return [row for row in self.evidence if row.search_run_id == search_run_id]

    async def list_prior_rejected_community_ids(
        self,
        *,
        search_run: SearchRun,
        community_ids: set[UUID],
    ) -> set[UUID]:
        assert search_run is self.search_run
        return set(community_ids) & self.prior_rejected_community_ids

    async def flush(self) -> None:
        self.flushes += 1


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
