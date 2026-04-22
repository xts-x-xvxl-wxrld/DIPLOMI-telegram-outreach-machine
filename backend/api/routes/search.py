from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    JobResponse,
    SearchCandidateListItem,
    SearchCandidateListResponse,
    SearchCandidateReviewRequest,
    SearchCandidateReviewResponse,
    SearchCandidateReviewOut,
    SearchCandidateEvidenceSummaryOut,
    SearchQueryListResponse,
    SearchQueryOut,
    SearchReviewOut,
    SearchRunCreateRequest,
    SearchRunCreateResponse,
    SearchRunCounts,
    SearchRunDetailResponse,
    SearchRunListItem,
    SearchRunListResponse,
    SearchRunOut,
)
from backend.queue.client import QueueUnavailable, enqueue_search_plan, enqueue_search_rank
from backend.services.search import (
    SearchNotFound,
    SearchServiceError,
    SearchValidationError,
    create_search_run,
    get_search_run,
    get_search_run_counts,
    list_search_candidates,
    list_search_queries,
    list_search_runs,
    review_search_candidate,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.post("/search-runs", response_model=SearchRunCreateResponse, status_code=201)
async def post_search_run(
    payload: SearchRunCreateRequest,
    db: DbSession,
) -> SearchRunCreateResponse:
    try:
        search_run = await create_search_run(
            db,
            query=payload.query,
            requested_by=payload.requested_by,
            language_hints=payload.language_hints,
            locale_hints=payload.locale_hints,
            enabled_adapters=[adapter.value for adapter in payload.enabled_adapters],
            per_run_candidate_cap=payload.per_run_candidate_cap,
            per_adapter_caps=payload.per_adapter_caps,
        )
        job = enqueue_search_plan(
            search_run.id,
            requested_by=payload.requested_by,
        )
    except SearchServiceError as exc:
        raise _http_error(exc) from exc
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.commit()
    return SearchRunCreateResponse(
        search_run=SearchRunOut.model_validate(search_run),
        job=job,
    )


@router.get("/search-runs", response_model=SearchRunListResponse)
async def get_search_runs(
    db: DbSession,
    status: str | None = None,
    requested_by: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchRunListResponse:
    try:
        result = await list_search_runs(
            db,
            status=status,
            requested_by=requested_by,
            limit=limit,
            offset=offset,
        )
    except SearchServiceError as exc:
        raise _http_error(exc) from exc

    return SearchRunListResponse(
        items=[
            SearchRunListItem(
                id=item.id,
                raw_query=item.raw_query,
                normalized_title=item.normalized_title,
                status=item.status,
                query_count=item.query_count,
                candidate_count=item.candidate_count,
                promoted_count=item.promoted_count,
                rejected_count=item.rejected_count,
                last_error=item.last_error,
                created_at=item.created_at,
                completed_at=item.completed_at,
            )
            for item in result.items
        ],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.get("/search-runs/{search_run_id}", response_model=SearchRunDetailResponse)
async def get_search_run_detail(
    search_run_id: UUID,
    db: DbSession,
) -> SearchRunDetailResponse:
    try:
        search_run = await get_search_run(db, search_run_id=search_run_id)
        counts = await get_search_run_counts(db, search_run_id=search_run_id)
    except SearchServiceError as exc:
        raise _http_error(exc) from exc

    return SearchRunDetailResponse(
        search_run=SearchRunOut.model_validate(search_run),
        counts=SearchRunCounts(
            queries=counts.queries,
            queries_completed=counts.queries_completed,
            candidates=counts.candidates,
            promoted=counts.promoted,
            rejected=counts.rejected,
            archived=counts.archived,
        ),
    )


@router.get("/search-runs/{search_run_id}/queries", response_model=SearchQueryListResponse)
async def get_search_run_queries(
    search_run_id: UUID,
    db: DbSession,
) -> SearchQueryListResponse:
    try:
        items = await list_search_queries(db, search_run_id=search_run_id)
    except SearchServiceError as exc:
        raise _http_error(exc) from exc

    return SearchQueryListResponse(
        items=[SearchQueryOut.model_validate(item) for item in items],
        total=len(items),
    )


@router.get("/search-runs/{search_run_id}/candidates", response_model=SearchCandidateListResponse)
async def get_search_run_candidates(
    search_run_id: UUID,
    db: DbSession,
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = False,
    include_rejected: bool = False,
) -> SearchCandidateListResponse:
    try:
        result = await list_search_candidates(
            db,
            search_run_id=search_run_id,
            statuses=status,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
            include_rejected=include_rejected,
        )
    except SearchServiceError as exc:
        raise _http_error(exc) from exc

    return SearchCandidateListResponse(
        items=[
            SearchCandidateListItem(
                id=item.id,
                search_run_id=item.search_run_id,
                status=item.status,
                community_id=item.community_id,
                title=item.title,
                username=item.username,
                telegram_url=item.telegram_url,
                description=item.description,
                member_count=item.member_count,
                score=item.score,
                ranking_version=item.ranking_version,
                score_components=item.score_components,
                evidence_summary=SearchCandidateEvidenceSummaryOut(
                    total=item.evidence_summary.total,
                    types=item.evidence_summary.types or [],
                    snippets=item.evidence_summary.snippets or [],
                ),
                first_seen_at=item.first_seen_at,
                last_seen_at=item.last_seen_at,
            )
            for item in result.items
        ],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.post("/search-runs/{search_run_id}/rerank-jobs", response_model=JobResponse, status_code=202)
async def post_search_rerank_job(
    search_run_id: UUID,
    db: DbSession,
) -> JobResponse:
    try:
        search_run = await get_search_run(db, search_run_id=search_run_id)
        job = enqueue_search_rank(
            search_run.id,
            requested_by=search_run.requested_by,
        )
    except SearchServiceError as exc:
        raise _http_error(exc) from exc
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.post("/search-candidates/{candidate_id}/review", response_model=SearchCandidateReviewResponse)
async def post_search_candidate_review(
    candidate_id: UUID,
    payload: SearchCandidateReviewRequest,
    db: DbSession,
) -> SearchCandidateReviewResponse:
    try:
        candidate, review = await review_search_candidate(
            db,
            candidate_id=candidate_id,
            action=payload.action,
            requested_by=payload.requested_by,
            notes=payload.notes,
        )
    except SearchServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return SearchCandidateReviewResponse(
        candidate=SearchCandidateReviewOut.model_validate(candidate),
        review=SearchReviewOut.model_validate(review),
    )


def _http_error(exc: SearchServiceError) -> HTTPException:
    status_code = 400
    if isinstance(exc, SearchNotFound):
        status_code = 404
    elif isinstance(exc, SearchValidationError):
        status_code = 400
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )


__all__ = [
    "router",
    "post_search_run",
    "get_search_runs",
    "get_search_run_detail",
    "get_search_run_queries",
    "get_search_run_candidates",
    "post_search_rerank_job",
    "post_search_candidate_review",
]
