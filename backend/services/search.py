from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import SearchCandidateStatus, SearchReviewAction, SearchReviewScope, SearchRunStatus
from backend.db.models import Community, SearchCandidate, SearchCandidateEvidence, SearchQuery, SearchReview, SearchRun


class SearchServiceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SearchNotFound(SearchServiceError):
    pass


class SearchValidationError(SearchServiceError):
    pass


@dataclass(frozen=True)
class SearchRunListItemView:
    id: UUID
    raw_query: str
    normalized_title: str
    status: str
    query_count: int
    candidate_count: int
    promoted_count: int
    rejected_count: int
    last_error: str | None
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class SearchRunListResult:
    items: list[SearchRunListItemView]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True)
class SearchRunCountsView:
    queries: int = 0
    queries_completed: int = 0
    candidates: int = 0
    promoted: int = 0
    rejected: int = 0
    archived: int = 0


@dataclass(frozen=True)
class SearchCandidateEvidenceSummaryView:
    total: int = 0
    types: list[str] | None = None
    snippets: list[str] | None = None


@dataclass(frozen=True)
class SearchCandidateListItemView:
    id: UUID
    search_run_id: UUID
    status: str
    community_id: UUID | None
    title: str | None
    username: str | None
    telegram_url: str | None
    description: str | None
    member_count: int | None
    score: Decimal | None
    ranking_version: str | None
    score_components: dict[str, Any]
    evidence_summary: SearchCandidateEvidenceSummaryView
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class SearchCandidateListResult:
    items: list[SearchCandidateListItemView]
    limit: int
    offset: int
    total: int


def normalize_search_query_text(value: str) -> str:
    return " ".join(value.split()).strip()


async def create_search_run(
    db: AsyncSession,
    *,
    query: str,
    requested_by: str | None,
    language_hints: list[str],
    locale_hints: list[str],
    enabled_adapters: list[str],
    per_run_candidate_cap: int,
    per_adapter_caps: dict[str, Any],
) -> SearchRun:
    normalized_query = normalize_search_query_text(query)
    if not normalized_query:
        raise SearchValidationError("invalid_query", "Search query must not be empty")

    created_at = datetime.now(timezone.utc)
    search_run = SearchRun(
        id=uuid4(),
        raw_query=normalized_query,
        normalized_title=normalized_query,
        requested_by=requested_by,
        status=SearchRunStatus.DRAFT.value,
        enabled_adapters=enabled_adapters,
        language_hints=language_hints,
        locale_hints=locale_hints,
        per_run_candidate_cap=per_run_candidate_cap,
        per_adapter_caps=per_adapter_caps,
        planner_metadata={},
        ranking_metadata={},
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(search_run)
    await db.flush()
    return search_run


async def list_search_runs(
    db: AsyncSession,
    *,
    status: str | None = None,
    requested_by: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchRunListResult:
    filters = []
    if status:
        filters.append(SearchRun.status == status)
    if requested_by:
        filters.append(SearchRun.requested_by == requested_by)

    total = int(
        await db.scalar(
            select(func.count(SearchRun.id)).where(*filters)
        )
        or 0
    )

    runs = list(
        (
            await db.scalars(
                select(SearchRun)
                .where(*filters)
                .order_by(SearchRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    if not runs:
        return SearchRunListResult(items=[], limit=limit, offset=offset, total=total)

    run_ids = [search_run.id for search_run in runs]
    query_counts = {
        row.search_run_id: row.query_count
        for row in (
            await db.execute(
                select(
                    SearchQuery.search_run_id,
                    func.count(SearchQuery.id).label("query_count"),
                )
                .where(SearchQuery.search_run_id.in_(run_ids))
                .group_by(SearchQuery.search_run_id)
            )
        ).all()
    }
    candidate_counts = {
        row.search_run_id: row
        for row in (
            await db.execute(
                select(
                    SearchCandidate.search_run_id,
                    func.count(SearchCandidate.id).label("candidate_count"),
                    func.coalesce(
                        func.sum(
                            case(
                                (SearchCandidate.status == SearchCandidateStatus.PROMOTED.value, 1),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("promoted_count"),
                    func.coalesce(
                        func.sum(
                            case(
                                (SearchCandidate.status == SearchCandidateStatus.REJECTED.value, 1),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("rejected_count"),
                )
                .where(SearchCandidate.search_run_id.in_(run_ids))
                .group_by(SearchCandidate.search_run_id)
            )
        ).all()
    }

    items = [
        SearchRunListItemView(
            id=search_run.id,
            raw_query=search_run.raw_query,
            normalized_title=search_run.normalized_title,
            status=search_run.status,
            query_count=int(query_counts.get(search_run.id, 0)),
            candidate_count=int(getattr(candidate_counts.get(search_run.id), "candidate_count", 0) or 0),
            promoted_count=int(getattr(candidate_counts.get(search_run.id), "promoted_count", 0) or 0),
            rejected_count=int(getattr(candidate_counts.get(search_run.id), "rejected_count", 0) or 0),
            last_error=search_run.last_error,
            created_at=search_run.created_at,
            completed_at=search_run.completed_at,
        )
        for search_run in runs
    ]
    return SearchRunListResult(items=items, limit=limit, offset=offset, total=total)


async def get_search_run(db: AsyncSession, *, search_run_id: UUID) -> SearchRun:
    search_run = await db.get(SearchRun, search_run_id)
    if search_run is None:
        raise SearchNotFound("not_found", "Search run not found")
    return search_run


async def get_search_run_counts(db: AsyncSession, *, search_run_id: UUID) -> SearchRunCountsView:
    await get_search_run(db, search_run_id=search_run_id)

    query_row = (
        await db.execute(
            select(
                func.count(SearchQuery.id).label("queries"),
                func.coalesce(
                    func.sum(
                        case((SearchQuery.status == "completed", 1), else_=0)
                    ),
                    0,
                ).label("queries_completed"),
            ).where(SearchQuery.search_run_id == search_run_id)
        )
    ).one()
    candidate_row = (
        await db.execute(
            select(
                func.count(SearchCandidate.id).label("candidates"),
                func.coalesce(
                    func.sum(
                        case(
                            (SearchCandidate.status == SearchCandidateStatus.PROMOTED.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("promoted"),
                func.coalesce(
                    func.sum(
                        case(
                            (SearchCandidate.status == SearchCandidateStatus.REJECTED.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("rejected"),
                func.coalesce(
                    func.sum(
                        case(
                            (SearchCandidate.status == SearchCandidateStatus.ARCHIVED.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("archived"),
            ).where(SearchCandidate.search_run_id == search_run_id)
        )
    ).one()
    return SearchRunCountsView(
        queries=int(query_row.queries or 0),
        queries_completed=int(query_row.queries_completed or 0),
        candidates=int(candidate_row.candidates or 0),
        promoted=int(candidate_row.promoted or 0),
        rejected=int(candidate_row.rejected or 0),
        archived=int(candidate_row.archived or 0),
    )


async def list_search_queries(db: AsyncSession, *, search_run_id: UUID) -> list[SearchQuery]:
    await get_search_run(db, search_run_id=search_run_id)
    return list(
        (
            await db.scalars(
                select(SearchQuery)
                .where(SearchQuery.search_run_id == search_run_id)
                .order_by(SearchQuery.created_at.asc(), SearchQuery.id.asc())
            )
        ).all()
    )


async def list_search_candidates(
    db: AsyncSession,
    *,
    search_run_id: UUID,
    statuses: list[str] | None = None,
    limit: int = 10,
    offset: int = 0,
    include_archived: bool = False,
    include_rejected: bool = False,
) -> SearchCandidateListResult:
    await get_search_run(db, search_run_id=search_run_id)

    if statuses is None:
        requested_statuses = [
            SearchCandidateStatus.CANDIDATE.value,
            SearchCandidateStatus.PROMOTED.value,
        ]
        if include_archived:
            requested_statuses.append(SearchCandidateStatus.ARCHIVED.value)
        if include_rejected:
            requested_statuses.append(SearchCandidateStatus.REJECTED.value)
    else:
        requested_statuses = statuses

    evidence_counts = (
        select(
            SearchCandidateEvidence.search_candidate_id.label("candidate_id"),
            func.count(SearchCandidateEvidence.id).label("evidence_count"),
        )
        .group_by(SearchCandidateEvidence.search_candidate_id)
        .subquery()
    )
    title_order = func.lower(func.coalesce(Community.title, SearchCandidate.raw_title, ""))
    status_order = case(
        (SearchCandidate.status == SearchCandidateStatus.PROMOTED.value, 0),
        (SearchCandidate.status == SearchCandidateStatus.CANDIDATE.value, 1),
        (SearchCandidate.status == SearchCandidateStatus.ARCHIVED.value, 2),
        (SearchCandidate.status == SearchCandidateStatus.REJECTED.value, 3),
        (SearchCandidate.status == SearchCandidateStatus.CONVERTED_TO_SEED.value, 4),
        else_=5,
    )
    title_null_order = case((func.coalesce(Community.title, SearchCandidate.raw_title).is_(None), 1), else_=0)
    filters = [SearchCandidate.search_run_id == search_run_id]
    if requested_statuses:
        filters.append(SearchCandidate.status.in_(requested_statuses))

    total = int(
        await db.scalar(
            select(func.count(SearchCandidate.id)).where(*filters)
        )
        or 0
    )
    candidates = list(
        (
            await db.scalars(
                select(SearchCandidate)
                .outerjoin(Community, Community.id == SearchCandidate.community_id)
                .outerjoin(
                    evidence_counts,
                    evidence_counts.c.candidate_id == SearchCandidate.id,
                )
                .options(joinedload(SearchCandidate.community))
                .where(*filters)
                .order_by(
                    SearchCandidate.score.desc().nullslast(),
                    status_order.asc(),
                    func.coalesce(evidence_counts.c.evidence_count, 0).desc(),
                    title_null_order.asc(),
                    title_order.asc(),
                    SearchCandidate.first_seen_at.asc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    if not candidates:
        return SearchCandidateListResult(items=[], limit=limit, offset=offset, total=total)

    candidate_ids = [candidate.id for candidate in candidates]
    evidence_rows = list(
        (
            await db.scalars(
                select(SearchCandidateEvidence)
                .where(SearchCandidateEvidence.search_candidate_id.in_(candidate_ids))
                .order_by(
                    SearchCandidateEvidence.search_candidate_id.asc(),
                    SearchCandidateEvidence.captured_at.asc(),
                )
            )
        ).all()
    )
    evidence_by_candidate: dict[UUID, list[SearchCandidateEvidence]] = {}
    for evidence in evidence_rows:
        evidence_by_candidate.setdefault(evidence.search_candidate_id, []).append(evidence)

    items = [
        _search_candidate_view(
            candidate,
            evidence_by_candidate.get(candidate.id, []),
        )
        for candidate in candidates
    ]
    return SearchCandidateListResult(items=items, limit=limit, offset=offset, total=total)


async def review_search_candidate(
    db: AsyncSession,
    *,
    candidate_id: UUID,
    action: SearchReviewAction,
    requested_by: str | None,
    notes: str | None,
) -> tuple[SearchCandidate, SearchReview]:
    supported_actions = {
        SearchReviewAction.PROMOTE: SearchCandidateStatus.PROMOTED.value,
        SearchReviewAction.REJECT: SearchCandidateStatus.REJECTED.value,
        SearchReviewAction.ARCHIVE: SearchCandidateStatus.ARCHIVED.value,
    }
    next_status = supported_actions.get(action)
    if next_status is None:
        raise SearchValidationError(
            "unsupported_review_action",
            "Only promote, reject, and archive are supported in the API skeleton",
        )

    candidate = await db.get(SearchCandidate, candidate_id)
    if candidate is None:
        raise SearchNotFound("not_found", "Search candidate not found")

    reviewed_at = datetime.now(timezone.utc)
    candidate.status = next_status
    candidate.reviewed_at = reviewed_at
    candidate.last_reviewed_by = requested_by or "operator"

    review = SearchReview(
        id=uuid4(),
        search_run_id=candidate.search_run_id,
        search_candidate_id=candidate.id,
        community_id=candidate.community_id,
        action=action.value,
        scope=SearchReviewScope.RUN.value,
        requested_by=requested_by,
        notes=notes,
        created_at=reviewed_at,
    )
    db.add(review)
    await db.flush()
    return candidate, review


def _search_candidate_view(
    candidate: SearchCandidate,
    evidence_rows: list[SearchCandidateEvidence],
) -> SearchCandidateListItemView:
    community = candidate.community
    snippets = [row.evidence_value for row in evidence_rows if row.evidence_value][:3]
    evidence_summary = SearchCandidateEvidenceSummaryView(
        total=len(evidence_rows),
        types=sorted({row.evidence_type for row in evidence_rows}),
        snippets=snippets,
    )
    return SearchCandidateListItemView(
        id=candidate.id,
        search_run_id=candidate.search_run_id,
        status=candidate.status,
        community_id=candidate.community_id,
        title=community.title if community is not None else candidate.raw_title,
        username=community.username if community is not None else candidate.normalized_username,
        telegram_url=community.telegram_url if community is not None else candidate.canonical_url,
        description=community.description if community is not None else candidate.raw_description,
        member_count=community.member_count if community is not None else candidate.raw_member_count,
        score=candidate.score,
        ranking_version=candidate.ranking_version,
        score_components=dict(candidate.score_components or {}),
        evidence_summary=evidence_summary,
        first_seen_at=candidate.first_seen_at,
        last_seen_at=candidate.last_seen_at,
    )


__all__ = [
    "SearchServiceError",
    "SearchNotFound",
    "SearchValidationError",
    "SearchRunListItemView",
    "SearchRunListResult",
    "SearchRunCountsView",
    "SearchCandidateEvidenceSummaryView",
    "SearchCandidateListItemView",
    "SearchCandidateListResult",
    "normalize_search_query_text",
    "create_search_run",
    "list_search_runs",
    "get_search_run",
    "get_search_run_counts",
    "list_search_queries",
    "list_search_candidates",
    "review_search_candidate",
]
