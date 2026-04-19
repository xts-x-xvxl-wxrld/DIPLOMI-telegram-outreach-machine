from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    EngagementActionListResponse,
    EngagementActionOut,
    EngagementCandidateApproveRequest,
    EngagementCandidateListResponse,
    EngagementCandidateOut,
    EngagementCandidateRejectRequest,
    EngagementDetectJobRequest,
    EngagementJoinJobRequest,
    EngagementSendJobRequest,
    EngagementSettingsOut,
    EngagementSettingsUpdate,
    EngagementTargetCreateRequest,
    EngagementTargetListResponse,
    EngagementTargetOut,
    EngagementTargetResolveJobRequest,
    EngagementTargetUpdateRequest,
    EngagementTopicCreate,
    EngagementTopicListResponse,
    EngagementTopicOut,
    EngagementTopicUpdate,
    JobResponse,
)
from backend.db.enums import EngagementCandidateStatus
from backend.db.models import Community, EngagementCandidate
from backend.queue.client import (
    QueueUnavailable,
    enqueue_community_join,
    enqueue_engagement_send,
    enqueue_engagement_target_resolve,
    enqueue_manual_engagement_detect,
)
from backend.services.community_engagement import (
    EngagementConflict,
    EngagementNotFound,
    EngagementServiceError,
    approve_candidate,
    create_engagement_target,
    create_topic,
    get_engagement_target,
    get_engagement_settings,
    list_engagement_actions,
    list_engagement_candidates,
    list_engagement_targets,
    list_topics,
    reject_candidate,
    update_engagement_target,
    update_topic,
    upsert_engagement_settings,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.get("/engagement/targets", response_model=EngagementTargetListResponse)
async def get_engagement_targets(
    db: DbSession,
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EngagementTargetListResponse:
    try:
        result = await list_engagement_targets(db, status=status, limit=limit, offset=offset)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    return EngagementTargetListResponse(
        items=[EngagementTargetOut.model_validate(item) for item in result.items],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.post("/engagement/targets", response_model=EngagementTargetOut, status_code=201)
async def post_engagement_target(
    payload: EngagementTargetCreateRequest,
    db: DbSession,
) -> EngagementTargetOut:
    try:
        target = await create_engagement_target(
            db,
            target_ref=payload.target_ref,
            added_by=payload.added_by or "operator",
            notes=payload.notes,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementTargetOut.model_validate(target)


@router.patch("/engagement/targets/{target_id}", response_model=EngagementTargetOut)
async def patch_engagement_target(
    target_id: UUID,
    payload: EngagementTargetUpdateRequest,
    db: DbSession,
) -> EngagementTargetOut:
    try:
        target = await update_engagement_target(
            db,
            target_id=target_id,
            payload=payload,
            updated_by=payload.updated_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementTargetOut.model_validate(target)


@router.post(
    "/engagement/targets/{target_id}/resolve-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_engagement_target_resolve_job(
    target_id: UUID,
    payload: EngagementTargetResolveJobRequest,
    db: DbSession,
) -> JobResponse:
    try:
        await get_engagement_target(db, target_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    try:
        job = enqueue_engagement_target_resolve(
            target_id,
            requested_by=payload.requested_by or "operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.post(
    "/engagement/targets/{target_id}/join-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_engagement_target_join_job(
    target_id: UUID,
    payload: EngagementJoinJobRequest,
    db: DbSession,
) -> JobResponse:
    try:
        target = await get_engagement_target(db, target_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    if target.community_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "target_not_resolved", "message": "Engagement target is not resolved"},
        )

    try:
        job = enqueue_community_join(
            target.community_id,
            telegram_account_id=payload.telegram_account_id,
            requested_by=payload.requested_by or "operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.post(
    "/engagement/targets/{target_id}/detect-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_engagement_target_detect_job(
    target_id: UUID,
    payload: EngagementDetectJobRequest,
    db: DbSession,
) -> JobResponse:
    try:
        target = await get_engagement_target(db, target_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    if target.community_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "target_not_resolved", "message": "Engagement target is not resolved"},
        )

    try:
        job = enqueue_manual_engagement_detect(
            target.community_id,
            window_minutes=payload.window_minutes,
            requested_by=payload.requested_by or "operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.get(
    "/communities/{community_id}/engagement-settings",
    response_model=EngagementSettingsOut,
)
async def get_community_engagement_settings(
    community_id: UUID,
    db: DbSession,
) -> EngagementSettingsOut:
    try:
        settings = await get_engagement_settings(db, community_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementSettingsOut.model_validate(settings)


@router.put(
    "/communities/{community_id}/engagement-settings",
    response_model=EngagementSettingsOut,
)
async def put_community_engagement_settings(
    community_id: UUID,
    payload: EngagementSettingsUpdate,
    db: DbSession,
) -> EngagementSettingsOut:
    try:
        settings = await upsert_engagement_settings(
            db,
            community_id=community_id,
            payload=payload,
            updated_by="operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementSettingsOut.model_validate(settings)


@router.get("/engagement/topics", response_model=EngagementTopicListResponse)
async def get_engagement_topics(db: DbSession) -> EngagementTopicListResponse:
    topics = await list_topics(db)
    return EngagementTopicListResponse(
        items=[EngagementTopicOut.model_validate(topic) for topic in topics]
    )


@router.post("/engagement/topics", response_model=EngagementTopicOut, status_code=201)
async def post_engagement_topic(
    payload: EngagementTopicCreate,
    db: DbSession,
) -> EngagementTopicOut:
    try:
        topic = await create_topic(db, payload=payload)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementTopicOut.model_validate(topic)


@router.patch("/engagement/topics/{topic_id}", response_model=EngagementTopicOut)
async def patch_engagement_topic(
    topic_id: UUID,
    payload: EngagementTopicUpdate,
    db: DbSession,
) -> EngagementTopicOut:
    try:
        topic = await update_topic(db, topic_id=topic_id, payload=payload)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementTopicOut.model_validate(topic)


@router.post(
    "/communities/{community_id}/join-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_community_join_job(
    community_id: UUID,
    payload: EngagementJoinJobRequest,
    db: DbSession,
) -> JobResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Community not found"},
        )

    try:
        job = enqueue_community_join(
            community.id,
            telegram_account_id=payload.telegram_account_id,
            requested_by=payload.requested_by or "operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.post(
    "/communities/{community_id}/engagement-detect-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_community_engagement_detect_job(
    community_id: UUID,
    payload: EngagementDetectJobRequest,
    db: DbSession,
) -> JobResponse:
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Community not found"},
        )

    try:
        job = enqueue_manual_engagement_detect(
            community.id,
            window_minutes=payload.window_minutes,
            requested_by=payload.requested_by or "operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.get("/engagement/candidates", response_model=EngagementCandidateListResponse)
async def get_engagement_candidates(
    db: DbSession,
    status: str | None = Query(default="needs_review"),
    community_id: UUID | None = None,
    topic_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EngagementCandidateListResponse:
    try:
        result = await list_engagement_candidates(
            db,
            status=status,
            community_id=community_id,
            topic_id=topic_id,
            limit=limit,
            offset=offset,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    return EngagementCandidateListResponse(
        items=[EngagementCandidateOut.model_validate(item) for item in result.items],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.get("/engagement/actions", response_model=EngagementActionListResponse)
async def get_engagement_actions(
    db: DbSession,
    community_id: UUID | None = None,
    candidate_id: UUID | None = None,
    status: str | None = None,
    action_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EngagementActionListResponse:
    try:
        result = await list_engagement_actions(
            db,
            community_id=community_id,
            candidate_id=candidate_id,
            status=status,
            action_type=action_type,
            limit=limit,
            offset=offset,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    return EngagementActionListResponse(
        items=[EngagementActionOut.model_validate(item) for item in result.items],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.post(
    "/engagement/candidates/{candidate_id}/approve",
    response_model=EngagementCandidateOut,
)
async def post_engagement_candidate_approve(
    candidate_id: UUID,
    payload: EngagementCandidateApproveRequest,
    db: DbSession,
) -> EngagementCandidateOut:
    try:
        candidate = await approve_candidate(
            db,
            candidate_id=candidate_id,
            approved_by=payload.reviewed_by or "operator",
            final_reply=payload.final_reply,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementCandidateOut.model_validate(candidate)


@router.post(
    "/engagement/candidates/{candidate_id}/reject",
    response_model=EngagementCandidateOut,
)
async def post_engagement_candidate_reject(
    candidate_id: UUID,
    payload: EngagementCandidateRejectRequest,
    db: DbSession,
) -> EngagementCandidateOut:
    try:
        candidate = await reject_candidate(
            db,
            candidate_id=candidate_id,
            rejected_by=payload.reviewed_by or "operator",
            reason=payload.reason,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementCandidateOut.model_validate(candidate)


@router.post(
    "/engagement/candidates/{candidate_id}/send-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_engagement_candidate_send_job(
    candidate_id: UUID,
    payload: EngagementSendJobRequest,
    db: DbSession,
) -> JobResponse:
    candidate = await db.get(EngagementCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Engagement candidate not found"},
        )
    if candidate.status != EngagementCandidateStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "candidate_not_approved",
                "message": "Only approved engagement candidates can be sent",
            },
        )

    try:
        job = enqueue_engagement_send(
            candidate.id,
            approved_by=payload.approved_by or candidate.reviewed_by or "operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


def _http_error(exc: EngagementServiceError) -> HTTPException:
    status_code = 400
    if isinstance(exc, EngagementNotFound):
        status_code = 404
    elif isinstance(exc, EngagementConflict):
        status_code = 409
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )
