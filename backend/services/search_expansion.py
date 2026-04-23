from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.enums import (
    CommunitySource,
    CommunityStatus,
    SearchCandidateStatus,
    SearchRunStatus,
    SeedChannelStatus,
)
from backend.db.models import Community, SearchCandidate, SearchCandidateEvidence, SearchRun, SeedChannel
from backend.queue.client import QueuedJob, enqueue_search_rank
from backend.services.seed_expansion import DiscoveredCommunityCandidate
from backend.services.seed_resolution import OPERATOR_COMMUNITY_STATUSES
from backend.services.search_retrieval import canonical_telegram_url, normalize_telegram_username

EVIDENCE_VALUE_LIMIT = 500
SEARCH_GRAPH_ADAPTER = "seed_graph_expand"


class SearchExpansionError(RuntimeError):
    pass


class SearchExpansionNotFound(SearchExpansionError):
    pass


class SearchExpansionValidationError(SearchExpansionError):
    pass


@dataclass(frozen=True)
class SearchExpansionRoot:
    root_type: str
    source_community: Community
    source_search_candidate: SearchCandidate | None = None
    source_seed_channel: SeedChannel | None = None


@dataclass
class SearchExpansionSummary:
    search_run_id: UUID
    roots_expanded: int = 0
    discovered_count: int = 0
    candidates_created: int = 0
    candidates_merged: int = 0
    evidence_created: int = 0
    skipped_global_rejected: int = 0
    rank_job: QueuedJob | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "processed",
            "job_type": "search.expand",
            "search_run_id": str(self.search_run_id),
            "roots_expanded": self.roots_expanded,
            "discovered_count": self.discovered_count,
            "candidates_created": self.candidates_created,
            "candidates_merged": self.candidates_merged,
            "evidence_created": self.evidence_created,
            "skipped_global_rejected": self.skipped_global_rejected,
            "rank_job": _serialize_job(self.rank_job),
        }


class SearchExpansionAdapter(Protocol):
    async def discover_from_root(
        self,
        *,
        root: SearchExpansionRoot,
        depth: int,
        max_neighbors: int,
    ) -> list[DiscoveredCommunityCandidate]:
        pass


class SearchExpansionRepository(Protocol):
    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        pass

    async def list_promoted_candidate_roots(
        self,
        *,
        search_run_id: UUID,
        root_search_candidate_ids: list[UUID],
        max_roots: int,
    ) -> list[SearchCandidate]:
        pass

    async def list_seed_roots(self, *, seed_group_ids: list[UUID], remaining_roots: int) -> list[SeedChannel]:
        pass

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        pass

    async def add_community(self, community: Community) -> None:
        pass

    async def find_candidate(
        self,
        *,
        search_run_id: UUID,
        community_id: UUID | None,
        normalized_username: str | None,
        canonical_url: str | None,
    ) -> SearchCandidate | None:
        pass

    async def add_candidate(self, candidate: SearchCandidate) -> None:
        pass

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
        pass

    async def add_evidence(self, evidence: SearchCandidateEvidence) -> None:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemySearchExpansionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        return await self.session.get(SearchRun, search_run_id)

    async def list_promoted_candidate_roots(
        self,
        *,
        search_run_id: UUID,
        root_search_candidate_ids: list[UUID],
        max_roots: int,
    ) -> list[SearchCandidate]:
        statement = (
            select(SearchCandidate)
            .where(SearchCandidate.search_run_id == search_run_id)
            .where(SearchCandidate.status == SearchCandidateStatus.PROMOTED.value)
            .where(SearchCandidate.community_id.is_not(None))
            .options(selectinload(SearchCandidate.community))
            .order_by(SearchCandidate.reviewed_at.asc().nullslast(), SearchCandidate.first_seen_at.asc())
            .limit(max_roots)
        )
        if root_search_candidate_ids:
            statement = statement.where(SearchCandidate.id.in_(root_search_candidate_ids))
        return list((await self.session.scalars(statement)).all())

    async def list_seed_roots(self, *, seed_group_ids: list[UUID], remaining_roots: int) -> list[SeedChannel]:
        if not seed_group_ids or remaining_roots <= 0:
            return []
        return list(
            (
                await self.session.scalars(
                    select(SeedChannel)
                    .where(SeedChannel.seed_group_id.in_(seed_group_ids))
                    .where(SeedChannel.status == SeedChannelStatus.RESOLVED.value)
                    .where(SeedChannel.community_id.is_not(None))
                    .options(selectinload(SeedChannel.community))
                    .order_by(SeedChannel.created_at.asc(), SeedChannel.id.asc())
                    .limit(remaining_roots)
                )
            ).all()
        )

    async def get_community_by_tg_id(self, tg_id: int) -> Community | None:
        return await self.session.scalar(select(Community).where(Community.tg_id == tg_id))

    async def add_community(self, community: Community) -> None:
        self.session.add(community)

    async def find_candidate(
        self,
        *,
        search_run_id: UUID,
        community_id: UUID | None,
        normalized_username: str | None,
        canonical_url: str | None,
    ) -> SearchCandidate | None:
        if community_id is not None:
            candidate = await self.session.scalar(
                select(SearchCandidate)
                .where(SearchCandidate.search_run_id == search_run_id)
                .where(SearchCandidate.community_id == community_id)
                .limit(1)
            )
            if candidate is not None:
                return candidate
        if normalized_username is not None:
            candidate = await self.session.scalar(
                select(SearchCandidate)
                .where(SearchCandidate.search_run_id == search_run_id)
                .where(SearchCandidate.normalized_username == normalized_username)
                .limit(1)
            )
            if candidate is not None:
                return candidate
        if canonical_url is not None:
            return await self.session.scalar(
                select(SearchCandidate)
                .where(SearchCandidate.search_run_id == search_run_id)
                .where(SearchCandidate.canonical_url == canonical_url)
                .limit(1)
            )
        return None

    async def add_candidate(self, candidate: SearchCandidate) -> None:
        self.session.add(candidate)

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
        value_filter = (
            SearchCandidateEvidence.evidence_value.is_(None)
            if evidence_value is None
            else SearchCandidateEvidence.evidence_value == evidence_value
        )
        seed_filter = (
            SearchCandidateEvidence.source_seed_channel_id.is_(None)
            if source_seed_channel_id is None
            else SearchCandidateEvidence.source_seed_channel_id == source_seed_channel_id
        )
        return await self.session.scalar(
            select(SearchCandidateEvidence)
            .where(SearchCandidateEvidence.search_run_id == search_run_id)
            .where(SearchCandidateEvidence.search_candidate_id == search_candidate_id)
            .where(SearchCandidateEvidence.source_community_id == source_community_id)
            .where(SearchCandidateEvidence.evidence_type == evidence_type)
            .where(value_filter)
            .where(seed_filter)
            .limit(1)
        )

    async def add_evidence(self, evidence: SearchCandidateEvidence) -> None:
        self.session.add(evidence)

    async def flush(self) -> None:
        await self.session.flush()


async def expand_search_run(
    repository: SearchExpansionRepository,
    *,
    search_run_id: UUID,
    root_search_candidate_ids: list[UUID],
    seed_group_ids: list[UUID],
    depth: int,
    requested_by: str | None,
    max_roots: int,
    max_neighbors_per_root: int,
    max_candidates_per_adapter: int,
    adapter: SearchExpansionAdapter,
    enqueue_search_rank_fn=enqueue_search_rank,
) -> SearchExpansionSummary:
    search_run = await repository.get_search_run(search_run_id)
    if search_run is None:
        raise SearchExpansionNotFound(f"Search run not found: {search_run_id}")
    if search_run.status == SearchRunStatus.CANCELLED.value:
        raise SearchExpansionValidationError("Search run is cancelled")

    roots = await _eligible_roots(
        repository,
        search_run_id=search_run.id,
        root_search_candidate_ids=root_search_candidate_ids,
        seed_group_ids=seed_group_ids,
        max_roots=max_roots,
    )
    if not roots:
        raise SearchExpansionValidationError(
            "Search expansion requires a promoted resolved search candidate or resolved manual seed root"
        )

    summary = SearchExpansionSummary(search_run_id=search_run.id, roots_expanded=len(roots))
    emitted_candidates = 0
    normalized_depth = max(depth, 1)
    now = datetime.now(timezone.utc)

    for root in roots:
        if emitted_candidates >= max_candidates_per_adapter:
            break
        discovered = await adapter.discover_from_root(
            root=root,
            depth=normalized_depth,
            max_neighbors=max_neighbors_per_root,
        )
        for discovered_candidate in discovered:
            if emitted_candidates >= max_candidates_per_adapter:
                break
            summary.discovered_count += 1
            community, created = await _upsert_community(
                repository,
                discovered_candidate,
                root=root,
            )
            if community.status == CommunityStatus.REJECTED.value:
                summary.skipped_global_rejected += 1
                continue
            candidate, candidate_created = await _upsert_search_candidate(
                repository,
                search_run=search_run,
                community=community,
                discovered_candidate=discovered_candidate,
                now=now,
            )
            await repository.flush()
            if candidate_created:
                summary.candidates_created += 1
            else:
                summary.candidates_merged += 1
            if await _ensure_evidence(
                repository,
                search_run=search_run,
                candidate=candidate,
                community=community,
                root=root,
                discovered_candidate=discovered_candidate,
                depth=normalized_depth,
                requested_by=requested_by,
            ):
                summary.evidence_created += 1
            if created or candidate_created:
                emitted_candidates += 1

    rank_job = enqueue_search_rank_fn(search_run.id, requested_by=requested_by or search_run.requested_by)
    summary.rank_job = rank_job
    search_run.status = SearchRunStatus.RANKING.value
    search_run.updated_at = datetime.now(timezone.utc)
    search_run.ranking_metadata = {
        **dict(search_run.ranking_metadata or {}),
        "last_expand_result": {
            "rank_job_id": rank_job.id,
            "queued_at": search_run.updated_at.isoformat(),
            "requested_by": requested_by or search_run.requested_by,
            "roots_expanded": summary.roots_expanded,
            "adapter": SEARCH_GRAPH_ADAPTER,
        },
    }
    await repository.flush()
    return summary


async def _eligible_roots(
    repository: SearchExpansionRepository,
    *,
    search_run_id: UUID,
    root_search_candidate_ids: list[UUID],
    seed_group_ids: list[UUID],
    max_roots: int,
) -> list[SearchExpansionRoot]:
    candidate_roots = await repository.list_promoted_candidate_roots(
        search_run_id=search_run_id,
        root_search_candidate_ids=root_search_candidate_ids,
        max_roots=max_roots,
    )
    roots = [
        SearchExpansionRoot(
            root_type="search_candidate",
            source_search_candidate=candidate,
            source_community=candidate.community,
        )
        for candidate in candidate_roots
        if candidate.community is not None and candidate.community.status != CommunityStatus.REJECTED.value
    ]
    remaining_roots = max(max_roots - len(roots), 0)
    seed_roots = await repository.list_seed_roots(
        seed_group_ids=seed_group_ids,
        remaining_roots=remaining_roots,
    )
    roots.extend(
        SearchExpansionRoot(
            root_type="manual_seed",
            source_seed_channel=seed_channel,
            source_community=seed_channel.community,
        )
        for seed_channel in seed_roots
        if seed_channel.community is not None and seed_channel.community.status != CommunityStatus.REJECTED.value
    )
    return roots[:max_roots]


async def _upsert_community(
    repository: SearchExpansionRepository,
    discovered_candidate: DiscoveredCommunityCandidate,
    *,
    root: SearchExpansionRoot,
) -> tuple[Community, bool]:
    community = await repository.get_community_by_tg_id(discovered_candidate.tg_id)
    created = community is None
    if community is None:
        community = Community(
            id=uuid.uuid4(),
            tg_id=discovered_candidate.tg_id,
            source=CommunitySource.EXPANSION.value,
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
        await repository.add_community(community)

    community.username = normalize_telegram_username(discovered_candidate.username) or community.username
    community.title = discovered_candidate.title or community.title
    if discovered_candidate.description is not None:
        community.description = discovered_candidate.description
    if discovered_candidate.member_count is not None:
        community.member_count = discovered_candidate.member_count
    community.is_group = discovered_candidate.is_group
    community.is_broadcast = discovered_candidate.is_broadcast
    community.source = community.source or CommunitySource.EXPANSION.value
    reason = _match_reason(root=root, discovered_candidate=discovered_candidate)
    if reason not in (community.match_reason or ""):
        community.match_reason = f"{community.match_reason}; {reason}" if community.match_reason else reason
    if community.status not in OPERATOR_COMMUNITY_STATUSES and not community.status:
        community.status = CommunityStatus.CANDIDATE.value
    return community, created


async def _upsert_search_candidate(
    repository: SearchExpansionRepository,
    *,
    search_run: SearchRun,
    community: Community,
    discovered_candidate: DiscoveredCommunityCandidate,
    now: datetime,
) -> tuple[SearchCandidate, bool]:
    normalized_username = normalize_telegram_username(discovered_candidate.username)
    canonical_url = canonical_telegram_url(username=normalized_username)
    candidate = await repository.find_candidate(
        search_run_id=search_run.id,
        community_id=community.id,
        normalized_username=normalized_username,
        canonical_url=canonical_url,
    )
    if candidate is None:
        candidate = SearchCandidate(
            id=uuid.uuid4(),
            search_run_id=search_run.id,
            community_id=community.id,
            status=SearchCandidateStatus.CANDIDATE.value,
            normalized_username=normalized_username,
            canonical_url=canonical_url,
            raw_title=discovered_candidate.title,
            raw_description=discovered_candidate.description,
            raw_member_count=discovered_candidate.member_count,
            adapter_first_seen=SEARCH_GRAPH_ADAPTER,
            score_components={},
            first_seen_at=now,
            last_seen_at=now,
        )
        await repository.add_candidate(candidate)
        return candidate, True

    candidate.community_id = candidate.community_id or community.id
    candidate.normalized_username = candidate.normalized_username or normalized_username
    candidate.canonical_url = candidate.canonical_url or canonical_url
    candidate.raw_title = discovered_candidate.title or candidate.raw_title
    if discovered_candidate.description is not None:
        candidate.raw_description = discovered_candidate.description
    if discovered_candidate.member_count is not None:
        candidate.raw_member_count = discovered_candidate.member_count
    candidate.last_seen_at = now
    return candidate, False


async def _ensure_evidence(
    repository: SearchExpansionRepository,
    *,
    search_run: SearchRun,
    candidate: SearchCandidate,
    community: Community,
    root: SearchExpansionRoot,
    discovered_candidate: DiscoveredCommunityCandidate,
    depth: int,
    requested_by: str | None,
) -> bool:
    evidence_value = _truncate_text(discovered_candidate.evidence_value, EVIDENCE_VALUE_LIMIT)
    source_seed_channel_id = (
        root.source_seed_channel.id
        if root.source_seed_channel is not None
        else None
    )
    existing = await repository.find_evidence(
        search_run_id=search_run.id,
        search_candidate_id=candidate.id,
        source_community_id=root.source_community.id,
        source_seed_channel_id=source_seed_channel_id,
        evidence_type=discovered_candidate.evidence_type,
        evidence_value=evidence_value,
    )
    if existing is not None:
        return False

    source_seed_group_id = (
        root.source_seed_channel.seed_group_id
        if root.source_seed_channel is not None
        else None
    )
    await repository.add_evidence(
        SearchCandidateEvidence(
            id=uuid.uuid4(),
            search_run_id=search_run.id,
            search_candidate_id=candidate.id,
            community_id=community.id,
            adapter=SEARCH_GRAPH_ADAPTER,
            query_text=None,
            evidence_type=discovered_candidate.evidence_type,
            evidence_value=evidence_value,
            evidence_metadata={
                "root_type": root.root_type,
                "source_search_candidate_id": (
                    str(root.source_search_candidate.id)
                    if root.source_search_candidate is not None
                    else None
                ),
                "depth": depth,
                "requested_by": requested_by,
            },
            source_community_id=root.source_community.id,
            source_seed_group_id=source_seed_group_id,
            source_seed_channel_id=source_seed_channel_id,
            captured_at=datetime.now(timezone.utc),
        )
    )
    return True


def _match_reason(*, root: SearchExpansionRoot, discovered_candidate: DiscoveredCommunityCandidate) -> str:
    source_label = root.source_community.title or root.source_community.username or str(root.source_community.id)
    evidence = discovered_candidate.evidence_type.replace("_", " ")
    if discovered_candidate.evidence_value:
        evidence = f"{evidence}: {discovered_candidate.evidence_value}"
    if root.source_search_candidate is not None:
        return f"Expanded from promoted search candidate via {evidence} from {source_label}"
    return f"Expanded from manual seed via {evidence} from {source_label}"


def _truncate_text(value: str | None, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _serialize_job(job: QueuedJob | None) -> dict[str, str] | None:
    if job is None:
        return None
    return {"id": job.id, "type": job.type, "status": job.status}


__all__ = [
    "SearchExpansionAdapter",
    "SearchExpansionError",
    "SearchExpansionNotFound",
    "SearchExpansionRepository",
    "SearchExpansionRoot",
    "SearchExpansionSummary",
    "SearchExpansionValidationError",
    "SqlAlchemySearchExpansionRepository",
    "expand_search_run",
]
