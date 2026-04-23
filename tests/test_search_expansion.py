from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.db.enums import CommunityStatus, SearchCandidateStatus, SearchRunStatus, SeedChannelStatus
from backend.db.models import Community, SearchCandidate, SearchCandidateEvidence, SearchRun, SeedChannel
from backend.queue.client import QueuedJob
from backend.services.search_expansion import (
    SearchExpansionRoot,
    SearchExpansionValidationError,
    expand_search_run,
)
from backend.services.seed_expansion import DiscoveredCommunityCandidate


@pytest.mark.asyncio
async def test_search_expansion_uses_promoted_resolved_candidate_roots_only() -> None:
    search_run = _search_run()
    root_community = _community(tg_id=100, username="root", title="Root Community")
    promoted = _candidate(
        search_run.id,
        community=root_community,
        status=SearchCandidateStatus.PROMOTED.value,
    )
    rejected = _candidate(
        search_run.id,
        community=_community(tg_id=101, username="rejectroot", title="Rejected Root"),
        status=SearchCandidateStatus.REJECTED.value,
    )
    repository = FakeSearchExpansionRepository(
        search_run=search_run,
        candidates=[promoted, rejected],
        communities=[root_community],
    )
    adapter = FakeSearchExpansionAdapter(
        [
            DiscoveredCommunityCandidate(
                tg_id=200,
                username="target",
                title="Target Community",
                description="Related graph result",
                member_count=450,
                is_group=True,
                is_broadcast=False,
                evidence_type="mention",
                evidence_value="@target",
            )
        ]
    )

    summary = await expand_search_run(
        repository,
        search_run_id=search_run.id,
        root_search_candidate_ids=[],
        seed_group_ids=[],
        depth=1,
        requested_by="operator",
        max_roots=5,
        max_neighbors_per_root=25,
        max_candidates_per_adapter=10,
        adapter=adapter,
        enqueue_search_rank_fn=lambda search_run_id, **kwargs: QueuedJob(  # noqa: ARG005
            id="rank-job",
            type="search.rank",
        ),
    )

    target_candidate = repository.candidates[-1]
    evidence = repository.evidence[0]
    assert summary.roots_expanded == 1
    assert summary.candidates_created == 1
    assert summary.evidence_created == 1
    assert adapter.calls == [("search_candidate", root_community.id, 1, 25)]
    assert target_candidate.community_id == repository.communities_by_tg_id[200].id
    assert evidence.source_community_id == root_community.id
    assert evidence.source_seed_group_id is None
    assert evidence.evidence_metadata["source_search_candidate_id"] == str(promoted.id)
    assert search_run.status == SearchRunStatus.RANKING.value
    assert search_run.ranking_metadata["last_expand_result"]["rank_job_id"] == "rank-job"


@pytest.mark.asyncio
async def test_search_expansion_rejects_unpromoted_or_unresolved_roots() -> None:
    search_run = _search_run()
    unresolved = _candidate(
        search_run.id,
        community=None,
        status=SearchCandidateStatus.PROMOTED.value,
    )
    unpromoted = _candidate(
        search_run.id,
        community=_community(tg_id=101, username="candidate", title="Candidate Root"),
        status=SearchCandidateStatus.CANDIDATE.value,
    )
    repository = FakeSearchExpansionRepository(
        search_run=search_run,
        candidates=[unresolved, unpromoted],
    )

    with pytest.raises(SearchExpansionValidationError):
        await expand_search_run(
            repository,
            search_run_id=search_run.id,
            root_search_candidate_ids=[unresolved.id, unpromoted.id],
            seed_group_ids=[],
            depth=1,
            requested_by="operator",
            max_roots=5,
            max_neighbors_per_root=25,
            max_candidates_per_adapter=10,
            adapter=FakeSearchExpansionAdapter([]),
        )


@pytest.mark.asyncio
async def test_search_expansion_allows_resolved_manual_seed_roots() -> None:
    search_run = _search_run()
    seed_group_id = uuid4()
    source = _community(tg_id=300, username="seed", title="Manual Seed")
    seed_channel = SeedChannel(
        id=uuid4(),
        seed_group_id=seed_group_id,
        raw_value="@seed",
        normalized_key="username:seed",
        username="seed",
        status=SeedChannelStatus.RESOLVED.value,
        community_id=source.id,
    )
    seed_channel.community = source
    repository = FakeSearchExpansionRepository(
        search_run=search_run,
        seed_channels=[seed_channel],
        communities=[source],
    )
    adapter = FakeSearchExpansionAdapter(
        [
            DiscoveredCommunityCandidate(
                tg_id=301,
                username="seedtarget",
                title="Seed Target",
                description=None,
                member_count=None,
                is_group=False,
                is_broadcast=True,
                evidence_type="telegram_link",
                evidence_value="https://t.me/seedtarget",
            )
        ]
    )

    summary = await expand_search_run(
        repository,
        search_run_id=search_run.id,
        root_search_candidate_ids=[],
        seed_group_ids=[seed_group_id],
        depth=1,
        requested_by="operator",
        max_roots=5,
        max_neighbors_per_root=25,
        max_candidates_per_adapter=10,
        adapter=adapter,
        enqueue_search_rank_fn=lambda search_run_id, **kwargs: QueuedJob(  # noqa: ARG005
            id="rank-job",
            type="search.rank",
        ),
    )

    evidence = repository.evidence[0]
    assert summary.roots_expanded == 1
    assert evidence.source_seed_group_id == seed_group_id
    assert evidence.source_seed_channel_id == seed_channel.id
    assert evidence.evidence_metadata["root_type"] == "manual_seed"


@pytest.mark.asyncio
async def test_search_expansion_does_not_use_globally_rejected_roots_or_targets() -> None:
    search_run = _search_run()
    root = _community(
        tg_id=100,
        username="root",
        title="Root Community",
        status=CommunityStatus.REJECTED.value,
    )
    promoted = _candidate(search_run.id, community=root, status=SearchCandidateStatus.PROMOTED.value)
    repository = FakeSearchExpansionRepository(
        search_run=search_run,
        candidates=[promoted],
        communities=[root],
    )

    with pytest.raises(SearchExpansionValidationError):
        await expand_search_run(
            repository,
            search_run_id=search_run.id,
            root_search_candidate_ids=[],
            seed_group_ids=[],
            depth=1,
            requested_by="operator",
            max_roots=5,
            max_neighbors_per_root=25,
            max_candidates_per_adapter=10,
            adapter=FakeSearchExpansionAdapter([]),
        )


class FakeSearchExpansionAdapter:
    def __init__(self, candidates: list[DiscoveredCommunityCandidate]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[str, UUID, int, int]] = []

    async def discover_from_root(
        self,
        *,
        root: SearchExpansionRoot,
        depth: int,
        max_neighbors: int,
    ) -> list[DiscoveredCommunityCandidate]:
        self.calls.append((root.root_type, root.source_community.id, depth, max_neighbors))
        return self.candidates


class FakeSearchExpansionRepository:
    def __init__(
        self,
        *,
        search_run: SearchRun,
        candidates: list[SearchCandidate] | None = None,
        seed_channels: list[SeedChannel] | None = None,
        communities: list[Community] | None = None,
    ) -> None:
        self.search_run = search_run
        self.candidates = candidates or []
        self.seed_channels = seed_channels or []
        self.communities_by_tg_id = {community.tg_id: community for community in communities or []}
        self.evidence: list[SearchCandidateEvidence] = []
        self.flushes = 0

    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        return self.search_run if search_run_id == self.search_run.id else None

    async def list_promoted_candidate_roots(
        self,
        *,
        search_run_id: UUID,
        root_search_candidate_ids: list[UUID],
        max_roots: int,
    ) -> list[SearchCandidate]:
        roots = [
            candidate
            for candidate in self.candidates
            if candidate.search_run_id == search_run_id
            and candidate.status == SearchCandidateStatus.PROMOTED.value
            and candidate.community_id is not None
            and (not root_search_candidate_ids or candidate.id in root_search_candidate_ids)
        ]
        return roots[:max_roots]

    async def list_seed_roots(self, *, seed_group_ids: list[UUID], remaining_roots: int) -> list[SeedChannel]:
        return [
            seed_channel
            for seed_channel in self.seed_channels
            if seed_channel.seed_group_id in seed_group_ids
            and seed_channel.status == SeedChannelStatus.RESOLVED.value
            and seed_channel.community_id is not None
        ][:remaining_roots]

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return self.communities_by_tg_id.get(tg_id)

    async def add_community(self, community: Community) -> None:
        self.communities_by_tg_id[community.tg_id] = community

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

    async def find_evidence(
        self,
        *,
        search_run_id: UUID,
        search_candidate_id: UUID,
        source_community_id: UUID,
        source_seed_channel_id: UUID | None,
        evidence_type: str,
        evidence_value: str | None,
    ) -> SearchCandidateEvidence | None:
        for row in self.evidence:
            if (
                row.search_run_id == search_run_id
                and row.search_candidate_id == search_candidate_id
                and row.source_community_id == source_community_id
                and row.source_seed_channel_id == source_seed_channel_id
                and row.evidence_type == evidence_type
                and row.evidence_value == evidence_value
            ):
                return row
        return None

    async def add_evidence(self, evidence: SearchCandidateEvidence) -> None:
        self.evidence.append(evidence)

    async def flush(self) -> None:
        self.flushes += 1


def _search_run() -> SearchRun:
    now = datetime(2026, 4, 22, tzinfo=timezone.utc)
    return SearchRun(
        id=uuid4(),
        raw_query="hungarian saas",
        normalized_title="hungarian saas",
        requested_by="operator",
        status=SearchRunStatus.COMPLETED.value,
        enabled_adapters=["telegram_entity_search"],
        language_hints=[],
        locale_hints=[],
        per_run_candidate_cap=100,
        per_adapter_caps={},
        planner_metadata={},
        ranking_metadata={},
        created_at=now,
        updated_at=now,
    )


def _candidate(
    search_run_id: UUID,
    *,
    community: Community | None,
    status: str,
) -> SearchCandidate:
    now = datetime(2026, 4, 22, tzinfo=timezone.utc)
    candidate = SearchCandidate(
        id=uuid4(),
        search_run_id=search_run_id,
        community_id=community.id if community is not None else None,
        status=status,
        normalized_username=community.username if community is not None else None,
        canonical_url=f"https://t.me/{community.username}" if community is not None else None,
        raw_title=community.title if community is not None else None,
        score_components={},
        first_seen_at=now,
        last_seen_at=now,
    )
    candidate.community = community
    return candidate


def _community(
    *,
    tg_id: int,
    username: str,
    title: str,
    status: str = CommunityStatus.CANDIDATE.value,
) -> Community:
    return Community(
        id=uuid4(),
        tg_id=tg_id,
        username=username,
        title=title,
        status=status,
        store_messages=False,
    )
