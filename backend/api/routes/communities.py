from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    AnalysisListResponse,
    CollectionJobRequest,
    CollectionRunListResponse,
    CommunityDetailResponse,
    CommunityListResponse,
    CommunityMemberListResponse,
    CommunityMemberOut,
    JobResponse,
    PatchCommunityRequest,
    PatchCommunityResponse,
    ReviewCommunityRequest,
    ReviewCommunityResponse,
)
from backend.db.enums import ActivityStatus, CommunityStatus
from backend.db.models import (
    AnalysisSummary,
    CollectionRun,
    Community,
    CommunityMember,
    CommunitySnapshot,
    User,
)
from backend.queue.client import QueueUnavailable, enqueue_analysis, enqueue_collection

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.get("/communities", response_model=CommunityListResponse)
async def list_communities(
    db: DbSession,
    brief_id: UUID | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CommunityListResponse:
    query = select(Community)
    count_query = select(func.count()).select_from(Community)
    if brief_id:
        query = query.where(Community.brief_id == brief_id)
        count_query = count_query.where(Community.brief_id == brief_id)
    if status_value:
        query = query.where(Community.status == status_value)
        count_query = count_query.where(Community.status == status_value)

    total = await db.scalar(count_query)
    rows = await db.scalars(query.order_by(desc(Community.first_seen_at)).limit(limit).offset(offset))
    return CommunityListResponse(items=list(rows), limit=limit, offset=offset, total=total or 0)


@router.get("/communities/{community_id}", response_model=CommunityDetailResponse)
async def get_community(community_id: UUID, db: DbSession) -> CommunityDetailResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Community not found"})

    latest_snapshot = await db.scalar(
        select(CommunitySnapshot)
        .where(CommunitySnapshot.community_id == community.id)
        .order_by(desc(CommunitySnapshot.collected_at))
        .limit(1)
    )
    latest_analysis = await db.scalar(
        select(AnalysisSummary)
        .where(AnalysisSummary.community_id == community.id)
        .order_by(desc(AnalysisSummary.analyzed_at))
        .limit(1)
    )
    return CommunityDetailResponse(
        community=community,
        latest_snapshot=_model_dict(latest_snapshot),
        latest_analysis=_model_dict(latest_analysis),
    )


@router.post("/communities/{community_id}/review", response_model=ReviewCommunityResponse)
async def review_community(
    community_id: UUID,
    payload: ReviewCommunityRequest,
    db: DbSession,
) -> ReviewCommunityResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Community not found"})

    decision = payload.decision.lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_decision", "message": "Decision must be approve or reject"},
        )

    job = None
    community.reviewed_at = datetime.now(timezone.utc)
    community.store_messages = payload.store_messages
    if decision == "approve":
        community.status = CommunityStatus.MONITORING.value
        try:
            job = enqueue_collection(community.id, reason="initial", requested_by="operator")
        except QueueUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    else:
        community.status = CommunityStatus.REJECTED.value

    await db.commit()
    await db.refresh(community)
    return ReviewCommunityResponse(community=community, job=job)


@router.patch("/communities/{community_id}", response_model=PatchCommunityResponse)
async def patch_community(
    community_id: UUID,
    payload: PatchCommunityRequest,
    db: DbSession,
) -> PatchCommunityResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Community not found"})

    if payload.status is not None:
        community.status = payload.status.value
    if payload.store_messages is not None:
        community.store_messages = payload.store_messages

    await db.commit()
    await db.refresh(community)
    return PatchCommunityResponse(community=community)


@router.post("/communities/{community_id}/collection-jobs", response_model=JobResponse, status_code=202)
async def start_collection(
    community_id: UUID,
    payload: CollectionJobRequest,
    db: DbSession,
) -> JobResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Community not found"})

    try:
        job = enqueue_collection(
            community.id,
            reason="manual",
            requested_by="operator",
            window_days=payload.window_days,
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.get("/communities/{community_id}/collection-runs", response_model=CollectionRunListResponse)
async def list_collection_runs(community_id: UUID, db: DbSession) -> CollectionRunListResponse:
    rows = await db.scalars(
        select(CollectionRun)
        .where(CollectionRun.community_id == community_id)
        .order_by(desc(CollectionRun.started_at))
        .limit(20)
    )
    return CollectionRunListResponse(items=list(rows))


@router.get("/communities/{community_id}/members", response_model=CommunityMemberListResponse)
async def list_community_members(
    community_id: UUID,
    db: DbSession,
    username_present: bool | None = None,
    has_public_username: bool | None = None,
    activity_status: str | None = None,
    limit: int = Query(default=20, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> CommunityMemberListResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Community not found"})

    username_filter = _resolve_username_filter(
        username_present=username_present,
        has_public_username=has_public_username,
    )
    if activity_status is not None and activity_status not in {status.value for status in ActivityStatus}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_activity_status",
                "message": "activity_status must be inactive, passive, or active",
            },
        )

    query = _community_members_query(
        community_id=community_id,
        username_present=username_filter,
        activity_status=activity_status,
    )
    total = await db.scalar(
        select(func.count()).select_from(
            query.order_by(None).limit(None).offset(None).subquery()
        )
    )
    rows = (
        await db.execute(
            query.order_by(desc(CommunityMember.last_updated_at), User.tg_user_id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return CommunityMemberListResponse(
        items=[_member_row_to_out(member, user) for member, user in rows],
        limit=limit,
        offset=offset,
        total=total or 0,
    )


@router.post("/collection-runs/{collection_run_id}/analysis-jobs", response_model=JobResponse, status_code=202)
async def start_analysis(collection_run_id: UUID, db: DbSession) -> JobResponse:
    collection_run = await db.get(CollectionRun, collection_run_id)
    if collection_run is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Collection run not found"})

    try:
        job = enqueue_analysis(collection_run.id, requested_by="operator")
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.get("/communities/{community_id}/analysis", response_model=AnalysisListResponse)
async def list_analysis(community_id: UUID, db: DbSession) -> AnalysisListResponse:
    rows = await db.scalars(
        select(AnalysisSummary)
        .where(AnalysisSummary.community_id == community_id)
        .order_by(desc(AnalysisSummary.analyzed_at))
        .limit(20)
    )
    return AnalysisListResponse(items=list(rows))


def _model_dict(model: object | None) -> dict | None:
    if model is None:
        return None
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}  # type: ignore[attr-defined]


def _resolve_username_filter(
    *,
    username_present: bool | None,
    has_public_username: bool | None,
) -> bool | None:
    if username_present is not None and has_public_username is not None:
        if username_present != has_public_username:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "conflicting_username_filters",
                    "message": "username_present and has_public_username must match when both are supplied",
                },
            )
    if username_present is not None:
        return username_present
    return has_public_username


def _community_members_query(
    *,
    community_id: UUID,
    username_present: bool | None,
    activity_status: str | None,
):
    query = (
        select(CommunityMember, User)
        .join(User, User.id == CommunityMember.user_id)
        .where(CommunityMember.community_id == community_id)
    )
    if username_present is True:
        query = query.where(User.username.is_not(None), User.username != "")
    elif username_present is False:
        query = query.where(or_(User.username.is_(None), User.username == ""))
    if activity_status is not None:
        query = query.where(CommunityMember.activity_status == activity_status)
    return query


def _member_row_to_out(member: CommunityMember, user: User) -> CommunityMemberOut:
    return CommunityMemberOut(
        tg_user_id=user.tg_user_id,
        username=user.username,
        first_name=user.first_name,
        membership_status="member",
        activity_status=member.activity_status,
        first_seen_at=member.first_seen_at,
        last_updated_at=member.last_updated_at,
        last_active_at=member.last_active_at,
    )
