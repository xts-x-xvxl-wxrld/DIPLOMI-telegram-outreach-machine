from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    BriefCounts,
    BriefDetailResponse,
    CreateBriefRequest,
    CreateBriefResponse,
    DiscoveryJobRequest,
    ExpansionJobRequest,
    JobResponse,
)
from backend.db.models import AudienceBrief, Community
from backend.queue.client import QueueUnavailable, enqueue_discovery, enqueue_expansion

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.post("/briefs", response_model=CreateBriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(payload: CreateBriefRequest, db: DbSession) -> CreateBriefResponse:
    brief = AudienceBrief(
        raw_input=payload.raw_input,
        keywords=[],
        related_phrases=[],
        language_hints=[],
        geography_hints=[],
        exclusion_terms=[],
        community_types=[],
    )
    db.add(brief)
    await db.flush()

    job = None
    if payload.auto_start_discovery:
        try:
            job = enqueue_discovery(brief.id, requested_by="operator", limit=50)
        except QueueUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(brief)
    return CreateBriefResponse(brief=brief, job=job)


@router.get("/briefs/{brief_id}", response_model=BriefDetailResponse)
async def get_brief(brief_id: UUID, db: DbSession) -> BriefDetailResponse:
    brief = await db.get(AudienceBrief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Brief not found"})

    rows = await db.execute(
        select(Community.status, func.count())
        .where(Community.brief_id == brief.id)
        .group_by(Community.status)
    )
    counts = {status_value: count for status_value, count in rows.all()}
    return BriefDetailResponse(
        brief=brief,
        counts=BriefCounts(
            candidate=counts.get("candidate", 0),
            approved=counts.get("approved", 0),
            rejected=counts.get("rejected", 0),
            monitoring=counts.get("monitoring", 0),
        ),
    )


@router.post("/briefs/{brief_id}/discovery-jobs", response_model=JobResponse, status_code=202)
async def start_discovery(
    brief_id: UUID,
    payload: DiscoveryJobRequest,
    db: DbSession,
) -> JobResponse:
    brief = await db.get(AudienceBrief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Brief not found"})

    try:
        job = enqueue_discovery(
            brief.id,
            requested_by="operator",
            limit=payload.limit,
            auto_expand=payload.auto_expand,
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.post("/briefs/{brief_id}/expansion-jobs", response_model=JobResponse, status_code=202)
async def start_expansion(
    brief_id: UUID,
    payload: ExpansionJobRequest,
    db: DbSession,
) -> JobResponse:
    brief = await db.get(AudienceBrief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Brief not found"})

    try:
        job = enqueue_expansion(
            brief.id,
            payload.community_ids,
            depth=payload.depth,
            requested_by="operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)
