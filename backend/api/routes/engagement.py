from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    EngagementCandidateApproveRequest,
    EngagementCandidateListResponse,
    EngagementCandidateOut,
    EngagementCandidateRejectRequest,
    EngagementSettingsOut,
    EngagementSettingsUpdate,
    EngagementTopicCreate,
    EngagementTopicListResponse,
    EngagementTopicOut,
    EngagementTopicUpdate,
)
from backend.services.community_engagement import (
    EngagementConflict,
    EngagementNotFound,
    EngagementServiceError,
    approve_candidate,
    create_topic,
    get_engagement_settings,
    list_engagement_candidates,
    list_topics,
    reject_candidate,
    update_topic,
    upsert_engagement_settings,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])


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


@router.get("/engagement/candidates", response_model=EngagementCandidateListResponse)
async def get_engagement_candidates(
    db: DbSession,
    status: str | None = Query(default="needs_review"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EngagementCandidateListResponse:
    try:
        result = await list_engagement_candidates(
            db,
            status=status,
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
