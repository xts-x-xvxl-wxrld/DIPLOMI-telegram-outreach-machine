from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    CommunitySource,
    CommunityStatus,
    SearchAdapter,
    SearchCandidateStatus,
    SearchEvidenceType,
    SearchQueryStatus,
    SearchRunStatus,
)
from backend.db.models import Community, SearchCandidate, SearchCandidateEvidence, SearchQuery, SearchRun
from backend.queue.client import QueuedJob, enqueue_search_rank
from backend.services.seed_resolution import OPERATOR_COMMUNITY_STATUSES
from backend.services.search import normalize_search_query_text

TELEGRAM_ENTITY_SEARCH_DEFAULT_LIMIT = 25
EVIDENCE_VALUE_LIMIT = 500
EVIDENCE_METADATA_LIMIT = 8192
TERMINAL_QUERY_STATUSES = {
    SearchQueryStatus.COMPLETED.value,
    SearchQueryStatus.FAILED.value,
    SearchQueryStatus.SKIPPED.value,
}


class SearchRetrieveError(RuntimeError):
    pass


class SearchRetrieveNotFound(SearchRetrieveError):
    pass


class SearchRetrieveValidationError(SearchRetrieveError):
    pass


class TelegramEntitySearchError(SearchRetrieveError):
    pass


@dataclass(frozen=True)
class EntitySearchEvidence:
    evidence_type: str
    value: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TelegramEntitySearchHit:
    status: Literal["resolved", "inaccessible", "not_community", "failed"] = "resolved"
    tg_id: int | None = None
    username: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    description: str | None = None
    member_count: int | None = None
    is_group: bool | None = None
    is_broadcast: bool | None = None
    evidence: tuple[EntitySearchEvidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass(frozen=True)
class SearchRetrievalSummary:
    search_run_id: UUID
    search_query_id: UUID
    query_status: str
    run_status: str
    hits_seen: int = 0
    candidates_created: int = 0
    candidates_merged: int = 0
    evidence_created: int = 0
    inaccessible_hits: int = 0
    non_community_hits: int = 0
    failed_hits: int = 0
    rank_job: QueuedJob | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "failed" if self.query_status == SearchQueryStatus.FAILED.value else "processed",
            "job_type": "search.retrieve",
            "search_run_id": str(self.search_run_id),
            "search_query_id": str(self.search_query_id),
            "query_status": self.query_status,
            "run_status": self.run_status,
            "hits_seen": self.hits_seen,
            "candidates_created": self.candidates_created,
            "candidates_merged": self.candidates_merged,
            "evidence_created": self.evidence_created,
            "inaccessible_hits": self.inaccessible_hits,
            "non_community_hits": self.non_community_hits,
            "failed_hits": self.failed_hits,
            "rank_job": _serialize_job(self.rank_job),
            "error_message": self.error_message,
        }


class TelegramEntitySearchAdapter(Protocol):
    async def search_entities(self, query_text: str, *, limit: int) -> list[TelegramEntitySearchHit]:
        pass

SearchRankEnqueuer = Callable[..., QueuedJob]


class SearchRetrievalRepository(Protocol):
    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        pass

    async def get_search_query(self, search_query_id: UUID) -> SearchQuery | None:
        pass

    async def count_candidates(self, search_run_id: UUID) -> int:
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

    async def add_evidence(self, evidence: SearchCandidateEvidence) -> None:
        pass

    async def list_query_statuses(self, search_run_id: UUID) -> list[str]:
        pass

    async def flush(self) -> None:
        pass


class SqlAlchemySearchRetrievalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_search_run(self, search_run_id: UUID) -> SearchRun | None:
        return await self.session.get(SearchRun, search_run_id)

    async def get_search_query(self, search_query_id: UUID) -> SearchQuery | None:
        return await self.session.get(SearchQuery, search_query_id)

    async def count_candidates(self, search_run_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(SearchCandidate.id)).where(
                    SearchCandidate.search_run_id == search_run_id
                )
            )
            or 0
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

    async def add_evidence(self, evidence: SearchCandidateEvidence) -> None:
        self.session.add(evidence)

    async def list_query_statuses(self, search_run_id: UUID) -> list[str]:
        return list(
            (
                await self.session.scalars(
                    select(SearchQuery.status).where(SearchQuery.search_run_id == search_run_id)
                )
            ).all()
        )

    async def flush(self) -> None:
        await self.session.flush()


async def retrieve_search_query(
    repository: SearchRetrievalRepository,
    *,
    search_run_id: UUID,
    search_query_id: UUID,
    adapter: TelegramEntitySearchAdapter,
    requested_by: str | None = None,
    enqueue_search_rank_fn: SearchRankEnqueuer = enqueue_search_rank,
) -> SearchRetrievalSummary:
    search_run, search_query = await _load_retrieval_target(
        repository,
        search_run_id=search_run_id,
        search_query_id=search_query_id,
    )
    if search_query.status == SearchQueryStatus.COMPLETED.value:
        return SearchRetrievalSummary(
            search_run_id=search_run.id,
            search_query_id=search_query.id,
            query_status=search_query.status,
            run_status=search_run.status,
        )

    now = datetime.now(timezone.utc)
    search_query.status = SearchQueryStatus.RUNNING.value
    search_query.started_at = search_query.started_at or now
    search_query.completed_at = None
    search_query.error_message = None
    search_run.status = SearchRunStatus.RETRIEVING.value
    search_run.updated_at = now

    existing_candidate_count = await repository.count_candidates(search_run.id)
    remaining_candidate_slots = max(int(search_run.per_run_candidate_cap or 0) - existing_candidate_count, 0)
    if remaining_candidate_slots <= 0:
        search_query.status = SearchQueryStatus.SKIPPED.value
        search_query.error_message = "Per-run search candidate cap reached"
        search_query.completed_at = now
        rank_job = await _finalize_run_if_ready(
            repository,
            search_run=search_run,
            requested_by=requested_by,
            enqueue_search_rank_fn=enqueue_search_rank_fn,
        )
        return SearchRetrievalSummary(
            search_run_id=search_run.id,
            search_query_id=search_query.id,
            query_status=search_query.status,
            run_status=search_run.status,
            rank_job=rank_job,
            error_message=search_query.error_message,
        )

    per_query_cap = min(_per_query_cap(search_run, search_query.adapter), remaining_candidate_slots)
    hits = await adapter.search_entities(search_query.query_text, limit=per_query_cap)
    summary_counts = _empty_counts()
    candidate_count = existing_candidate_count

    for hit in hits:
        summary_counts["hits_seen"] += 1
        if hit.status == "inaccessible":
            summary_counts["inaccessible_hits"] += 1
            continue
        if hit.status == "not_community":
            summary_counts["non_community_hits"] += 1
            continue
        if hit.status == "failed":
            summary_counts["failed_hits"] += 1
            continue

        if candidate_count >= int(search_run.per_run_candidate_cap or 0):
            break

        normalized_username = normalize_telegram_username(hit.username)
        canonical_url = canonical_telegram_url(
            username=normalized_username,
            canonical_url=hit.canonical_url,
        )
        if hit.tg_id is None and normalized_username is None and canonical_url is None:
            summary_counts["failed_hits"] += 1
            continue

        community = await _upsert_search_community(repository, hit)
        candidate = await repository.find_candidate(
            search_run_id=search_run.id,
            community_id=community.id if community is not None else None,
            normalized_username=normalized_username,
            canonical_url=canonical_url,
        )
        if candidate is None:
            candidate = SearchCandidate(
                id=uuid4(),
                search_run_id=search_run.id,
                community_id=community.id if community is not None else None,
                status=SearchCandidateStatus.CANDIDATE.value,
                normalized_username=normalized_username,
                canonical_url=canonical_url,
                raw_title=hit.title,
                raw_description=hit.description,
                raw_member_count=hit.member_count,
                adapter_first_seen=search_query.adapter,
                score_components={},
                first_seen_at=now,
                last_seen_at=now,
            )
            await repository.add_candidate(candidate)
            candidate_count += 1
            summary_counts["candidates_created"] += 1
        else:
            summary_counts["candidates_merged"] += 1
            _refresh_candidate(candidate, hit, community, normalized_username, canonical_url, now)

        await repository.flush()
        evidence_rows = _evidence_rows_for_hit(
            search_run=search_run,
            search_query=search_query,
            candidate=candidate,
            community=community,
            hit=hit,
        )
        for evidence in evidence_rows:
            await repository.add_evidence(evidence)
            summary_counts["evidence_created"] += 1

    search_query.status = SearchQueryStatus.COMPLETED.value
    search_query.completed_at = datetime.now(timezone.utc)
    search_query.planner_metadata = {
        **dict(search_query.planner_metadata or {}),
        "retrieval": {
            "adapter": search_query.adapter,
            "requested_by": requested_by,
            "per_query_cap": per_query_cap,
            **summary_counts,
        },
    }
    rank_job = await _finalize_run_if_ready(
        repository,
        search_run=search_run,
        requested_by=requested_by,
        enqueue_search_rank_fn=enqueue_search_rank_fn,
    )
    return SearchRetrievalSummary(
        search_run_id=search_run.id,
        search_query_id=search_query.id,
        query_status=search_query.status,
        run_status=search_run.status,
        rank_job=rank_job,
        **summary_counts,
    )


async def mark_search_query_failed(
    repository: SearchRetrievalRepository,
    *,
    search_run_id: UUID,
    search_query_id: UUID,
    error_message: str,
    requested_by: str | None = None,
    enqueue_search_rank_fn: SearchRankEnqueuer = enqueue_search_rank,
) -> SearchRetrievalSummary:
    search_run, search_query = await _load_retrieval_target(
        repository,
        search_run_id=search_run_id,
        search_query_id=search_query_id,
    )
    now = datetime.now(timezone.utc)
    search_query.status = SearchQueryStatus.FAILED.value
    search_query.started_at = search_query.started_at or now
    search_query.completed_at = now
    search_query.error_message = _truncate_text(error_message, 500)
    search_query.planner_metadata = {
        **dict(search_query.planner_metadata or {}),
        "retrieval": {
            "adapter": search_query.adapter,
            "requested_by": requested_by,
            "failed_at": now.isoformat(),
        },
    }
    rank_job = await _finalize_run_if_ready(
        repository,
        search_run=search_run,
        requested_by=requested_by,
        enqueue_search_rank_fn=enqueue_search_rank_fn,
    )
    return SearchRetrievalSummary(
        search_run_id=search_run.id,
        search_query_id=search_query.id,
        query_status=search_query.status,
        run_status=search_run.status,
        rank_job=rank_job,
        error_message=search_query.error_message,
    )


async def _load_retrieval_target(
    repository: SearchRetrievalRepository,
    *,
    search_run_id: UUID,
    search_query_id: UUID,
) -> tuple[SearchRun, SearchQuery]:
    search_run = await repository.get_search_run(search_run_id)
    if search_run is None:
        raise SearchRetrieveNotFound(f"Search run not found: {search_run_id}")
    search_query = await repository.get_search_query(search_query_id)
    if search_query is None or search_query.search_run_id != search_run.id:
        raise SearchRetrieveNotFound(f"Search query not found for run: {search_query_id}")
    if search_query.adapter != SearchAdapter.TELEGRAM_ENTITY_SEARCH.value:
        raise SearchRetrieveValidationError(f"Unsupported search adapter: {search_query.adapter}")
    if search_run.status == SearchRunStatus.CANCELLED.value:
        raise SearchRetrieveValidationError("Search run is cancelled")
    return search_run, search_query


async def _upsert_search_community(
    repository: SearchRetrievalRepository,
    hit: TelegramEntitySearchHit,
) -> Community | None:
    if hit.tg_id is None:
        return None

    community = await repository.get_community_by_tg_id(hit.tg_id)
    if community is None:
        community = Community(
            id=uuid4(),
            tg_id=hit.tg_id,
            username=normalize_telegram_username(hit.username),
            title=hit.title,
            description=hit.description,
            member_count=hit.member_count,
            is_group=hit.is_group,
            is_broadcast=hit.is_broadcast,
            source=CommunitySource.TELEGRAM_SEARCH.value,
            match_reason="Telegram entity search result",
            status=CommunityStatus.CANDIDATE.value,
            store_messages=False,
        )
        await repository.add_community(community)
        await repository.flush()
        return community

    community.username = normalize_telegram_username(hit.username) or community.username
    community.title = hit.title or community.title
    if hit.description is not None:
        community.description = hit.description
    if hit.member_count is not None:
        community.member_count = hit.member_count
    if hit.is_group is not None:
        community.is_group = hit.is_group
    if hit.is_broadcast is not None:
        community.is_broadcast = hit.is_broadcast
    community.source = community.source or CommunitySource.TELEGRAM_SEARCH.value
    community.match_reason = community.match_reason or "Telegram entity search result"
    if community.status not in OPERATOR_COMMUNITY_STATUSES and not community.status:
        community.status = CommunityStatus.CANDIDATE.value
    await repository.flush()
    return community


def _refresh_candidate(
    candidate: SearchCandidate,
    hit: TelegramEntitySearchHit,
    community: Community | None,
    normalized_username: str | None,
    canonical_url: str | None,
    now: datetime,
) -> None:
    if community is not None and candidate.community_id is None:
        candidate.community_id = community.id
    candidate.normalized_username = candidate.normalized_username or normalized_username
    candidate.canonical_url = candidate.canonical_url or canonical_url
    candidate.raw_title = hit.title or candidate.raw_title
    if hit.description is not None:
        candidate.raw_description = hit.description
    if hit.member_count is not None:
        candidate.raw_member_count = hit.member_count
    candidate.last_seen_at = now


async def _finalize_run_if_ready(
    repository: SearchRetrievalRepository,
    *,
    search_run: SearchRun,
    requested_by: str | None,
    enqueue_search_rank_fn: SearchRankEnqueuer,
) -> QueuedJob | None:
    statuses = await repository.list_query_statuses(search_run.id)
    if not statuses or any(status not in TERMINAL_QUERY_STATUSES for status in statuses):
        search_run.updated_at = datetime.now(timezone.utc)
        return None

    now = datetime.now(timezone.utc)
    if SearchQueryStatus.COMPLETED.value not in statuses:
        search_run.status = SearchRunStatus.FAILED.value
        search_run.last_error = "All search retrieval queries failed or were skipped"
        search_run.completed_at = now
        search_run.updated_at = now
        return None

    search_run.status = SearchRunStatus.RANKING.value
    search_run.updated_at = now
    rank_job = enqueue_search_rank_fn(
        search_run.id,
        requested_by=requested_by or search_run.requested_by,
    )
    search_run.ranking_metadata = {
        **dict(search_run.ranking_metadata or {}),
        "retrieval_completed_at": now.isoformat(),
        "rank_job_id": rank_job.id,
        "query_status_counts": {
            status: statuses.count(status)
            for status in sorted(set(statuses))
        },
    }
    return rank_job


def _evidence_rows_for_hit(
    *,
    search_run: SearchRun,
    search_query: SearchQuery,
    candidate: SearchCandidate,
    community: Community | None,
    hit: TelegramEntitySearchHit,
) -> list[SearchCandidateEvidence]:
    evidence_items = list(hit.evidence) or _default_evidence_for_hit(search_query.query_text, hit)
    rows: list[SearchCandidateEvidence] = []
    for item in evidence_items:
        rows.append(
            SearchCandidateEvidence(
                id=uuid4(),
                search_run_id=search_run.id,
                search_candidate_id=candidate.id,
                community_id=community.id if community is not None else None,
                search_query_id=search_query.id,
                adapter=search_query.adapter,
                query_text=search_query.query_text,
                evidence_type=item.evidence_type,
                evidence_value=_truncate_text(item.value, EVIDENCE_VALUE_LIMIT),
                evidence_metadata=_compact_metadata(
                    {
                        **dict(item.metadata or {}),
                        "hit": _hit_metadata(hit),
                    }
                ),
            )
        )
    return rows


def _default_evidence_for_hit(query_text: str, hit: TelegramEntitySearchHit) -> list[EntitySearchEvidence]:
    query_terms = [term for term in normalize_search_query_text(query_text).casefold().split(" ") if term]
    evidence: list[EntitySearchEvidence] = []
    title = hit.title or ""
    username = normalize_telegram_username(hit.username) or ""
    description = hit.description or ""
    if _contains_any(title, query_terms):
        evidence.append(
            EntitySearchEvidence(SearchEvidenceType.ENTITY_TITLE_MATCH.value, title, {"field": "title"})
        )
    if username and _contains_any(username, query_terms):
        evidence.append(
            EntitySearchEvidence(
                SearchEvidenceType.ENTITY_USERNAME_MATCH.value,
                f"@{username}",
                {"field": "username"},
            )
        )
    if description and _contains_any(description, query_terms):
        evidence.append(
            EntitySearchEvidence(
                SearchEvidenceType.DESCRIPTION_MATCH.value,
                description,
                {"field": "description"},
            )
        )
    if evidence:
        return evidence
    fallback = title or (f"@{username}" if username else hit.canonical_url) or "Telegram entity search hit"
    return [
        EntitySearchEvidence(
            SearchEvidenceType.ENTITY_TITLE_MATCH.value,
            fallback,
            {"field": "telegram_entity_search"},
        )
    ]


def _per_query_cap(search_run: SearchRun, adapter: str) -> int:
    caps = dict(search_run.per_adapter_caps or {})
    adapter_caps = caps.get(adapter)
    if isinstance(adapter_caps, dict):
        raw_limit = adapter_caps.get("per_query")
        if isinstance(raw_limit, int) and raw_limit > 0:
            return raw_limit
    return TELEGRAM_ENTITY_SEARCH_DEFAULT_LIMIT


def normalize_telegram_username(username: str | None) -> str | None:
    if username is None:
        return None
    normalized = username.strip().lstrip("@").casefold()
    return normalized or None


def canonical_telegram_url(*, username: str | None, canonical_url: str | None = None) -> str | None:
    if username:
        return f"https://t.me/{username}"
    if not canonical_url:
        return None
    value = canonical_url.strip()
    if not value:
        return None
    if value.startswith("@"):
        return f"https://t.me/{normalize_telegram_username(value)}"
    lowered = value.casefold()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if lowered.startswith(prefix):
            handle = value[len(prefix) :].strip("/")
            if handle:
                return f"https://t.me/{handle.casefold()}"
    return value


def _contains_any(value: str, terms: list[str]) -> bool:
    folded = value.casefold()
    return any(term in folded for term in terms)


def _hit_metadata(hit: TelegramEntitySearchHit) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "tg_id": hit.tg_id,
            "username": normalize_telegram_username(hit.username),
            "canonical_url": canonical_telegram_url(
                username=normalize_telegram_username(hit.username),
                canonical_url=hit.canonical_url,
            ),
            "member_count": hit.member_count,
            "is_group": hit.is_group,
            "is_broadcast": hit.is_broadcast,
            **dict(hit.metadata or {}),
        }.items()
        if value is not None
    }


def _compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    try:
        encoded = json.dumps(metadata, sort_keys=True, default=str)
    except TypeError:
        return {"metadata_error": "non_serializable"}
    if len(encoded.encode("utf-8")) <= EVIDENCE_METADATA_LIMIT:
        return metadata
    return {"truncated": True, "original_bytes": len(encoded.encode("utf-8"))}


def _truncate_text(value: str | None, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _empty_counts() -> dict[str, int]:
    return {
        "hits_seen": 0,
        "candidates_created": 0,
        "candidates_merged": 0,
        "evidence_created": 0,
        "inaccessible_hits": 0,
        "non_community_hits": 0,
        "failed_hits": 0,
    }


def _serialize_job(job: QueuedJob | None) -> dict[str, str] | None:
    if job is None:
        return None
    return {"id": job.id, "type": job.type, "status": job.status}


__all__ = [
    "EVIDENCE_VALUE_LIMIT",
    "EntitySearchEvidence",
    "SearchRetrievalSummary",
    "SearchRetrieveError",
    "SearchRetrieveNotFound",
    "SearchRetrieveValidationError",
    "SqlAlchemySearchRetrievalRepository",
    "TelegramEntitySearchAdapter",
    "TelegramEntitySearchError",
    "TelegramEntitySearchHit",
    "canonical_telegram_url",
    "mark_search_query_failed",
    "normalize_telegram_username",
    "retrieve_search_query",
]
