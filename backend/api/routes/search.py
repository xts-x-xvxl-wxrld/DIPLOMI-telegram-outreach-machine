from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

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
from backend.queue.client import QueueUnavailable, enqueue_search_expand, enqueue_search_plan, enqueue_search_rank
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
from backend.services.search_seed_conversion import convert_search_candidate_to_seed

router = APIRouter(dependencies=[Depends(require_bot_token)])


class SearchSeedConversionRequest(BaseModel):
    seed_group_name: str | None = Field(default=None, min_length=1, max_length=200)
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)


class SearchExpansionJobRequest(BaseModel):
    root_search_candidate_ids: list[UUID] = Field(default_factory=list)
    seed_group_ids: list[UUID] = Field(default_factory=list)
    depth: int = Field(default=1, ge=1, le=3)
    requested_by: str | None = Field(default=None, min_length=1, max_length=200)
    max_roots: int = Field(default=5, ge=1, le=25)
    max_neighbors_per_root: int = Field(default=50, ge=1, le=500)
    max_candidates_per_adapter: int = Field(default=50, ge=1, le=200)


class SearchSeedGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    normalized_name: str
    created_by: str | None = None


class SearchSeedChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_group_id: UUID
    raw_value: str
    normalized_key: str
    username: str | None = None
    telegram_url: str | None = None
    title: str | None = None
    notes: str | None = None
    status: str
    community_id: UUID | None = None


class SearchSeedConversionResponse(BaseModel):
    seed_group: SearchSeedGroupOut
    seed_channel: SearchSeedChannelOut
    candidate: SearchCandidateReviewOut
    review: SearchReviewOut


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
        queued_at = datetime.now(timezone.utc)
        search_run.ranking_metadata = {
            **dict(search_run.ranking_metadata or {}),
            "last_rerank_job": {
                "job_id": job.id,
                "status": job.status,
                "queued_at": queued_at.isoformat(),
                "requested_by": search_run.requested_by,
                "ranking_version_before": search_run.ranking_version,
            },
        }
        search_run.updated_at = queued_at
    except SearchServiceError as exc:
        raise _http_error(exc) from exc
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await db.commit()
    return JobResponse(job=job)


@router.post("/search-runs/{search_run_id}/expansion-jobs", response_model=JobResponse, status_code=202)
async def post_search_expansion_job(
    search_run_id: UUID,
    payload: SearchExpansionJobRequest,
    db: DbSession,
) -> JobResponse:
    try:
        search_run = await get_search_run(db, search_run_id=search_run_id)
        requested_by = payload.requested_by or search_run.requested_by
        job = enqueue_search_expand(
            search_run.id,
            root_search_candidate_ids=payload.root_search_candidate_ids,
            seed_group_ids=payload.seed_group_ids,
            depth=payload.depth,
            requested_by=requested_by,
            max_roots=payload.max_roots,
            max_neighbors_per_root=payload.max_neighbors_per_root,
            max_candidates_per_adapter=payload.max_candidates_per_adapter,
        )
        queued_at = datetime.now(timezone.utc)
        search_run.ranking_metadata = {
            **dict(search_run.ranking_metadata or {}),
            "last_expand_job": {
                "job_id": job.id,
                "status": job.status,
                "queued_at": queued_at.isoformat(),
                "requested_by": requested_by,
                "root_search_candidate_ids": [
                    str(candidate_id) for candidate_id in payload.root_search_candidate_ids
                ],
                "seed_group_ids": [str(seed_group_id) for seed_group_id in payload.seed_group_ids],
            },
        }
        search_run.updated_at = queued_at
    except SearchServiceError as exc:
        raise _http_error(exc) from exc
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await db.commit()
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


@router.post(
    "/search-candidates/{candidate_id}/convert-to-seed",
    response_model=SearchSeedConversionResponse,
)
async def post_search_candidate_convert_to_seed(
    candidate_id: UUID,
    payload: SearchSeedConversionRequest,
    db: DbSession,
) -> SearchSeedConversionResponse:
    try:
        result = await convert_search_candidate_to_seed(
            db,
            candidate_id=candidate_id,
            seed_group_name=payload.seed_group_name,
            requested_by=payload.requested_by,
        )
    except SearchServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return SearchSeedConversionResponse(
        seed_group=SearchSeedGroupOut.model_validate(result.seed_group),
        seed_channel=SearchSeedChannelOut.model_validate(result.seed_channel),
        candidate=SearchCandidateReviewOut.model_validate(result.candidate),
        review=SearchReviewOut.model_validate(result.review),
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
    "post_search_expansion_job",
    "post_search_candidate_review",
    "post_search_candidate_convert_to_seed",
    "SearchExpansionJobRequest",
    "SearchSeedConversionRequest",
    "SearchSeedConversionResponse",
]
