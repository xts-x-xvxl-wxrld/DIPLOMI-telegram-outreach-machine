# ruff: noqa: F401,F403,F405
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import (
    DbSession,
    OperatorCapabilitiesDep,
    require_bot_token,
    require_engagement_admin_capability,
)
from backend.api.schemas import (
    EngagementActionListResponse,
    EngagementActionOut,
    EngagementCandidateApproveRequest,
    EngagementCandidateEditRequest,
    EngagementCandidateExpireRequest,
    EngagementCandidateListResponse,
    EngagementCandidateOut,
    EngagementCandidateRejectRequest,
    EngagementCandidateRetryRequest,
    EngagementCandidateRevisionListResponse,
    EngagementCandidateRevisionOut,
    EngagementDetectJobRequest,
    EngagementJoinJobRequest,
    EngagementPromptPreviewOut,
    EngagementPromptProfileActivateRequest,
    EngagementPromptProfileCreateRequest,
    EngagementPromptProfileDuplicateRequest,
    EngagementPromptProfileListResponse,
    EngagementPromptProfileOut,
    EngagementPromptProfilePreviewRequest,
    EngagementPromptProfileRollbackRequest,
    EngagementPromptProfileUpdateRequest,
    EngagementPromptProfileVersionListResponse,
    EngagementPromptProfileVersionOut,
    EngagementSendJobRequest,
    EngagementSettingsOut,
    EngagementSettingsUpdate,
    EngagementSemanticRolloutSummaryOut,
    EngagementStyleRuleCreateRequest,
    EngagementStyleRuleListResponse,
    EngagementStyleRuleOut,
    EngagementStyleRuleUpdateRequest,
    EngagementTargetCreateRequest,
    EngagementTargetListResponse,
    EngagementTargetOut,
    EngagementTargetResolveJobRequest,
    EngagementTargetUpdateRequest,
    EngagementTopicCreate,
    EngagementTopicExampleCreateRequest,
    EngagementTopicListResponse,
    EngagementTopicOut,
    EngagementTopicUpdate,
    JobResponse,
    OperatorCapabilitiesOut,
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
from backend.services.engagement_account_behavior import engagement_send_scheduled_at
from backend.workers.engagement_send import reserve_scheduled_send_action
from backend.services.community_engagement import (
    EngagementConflict,
    EngagementNotFound,
    EngagementServiceError,
    activate_prompt_profile,
    add_topic_example,
    approve_candidate,
    create_engagement_target,
    create_prompt_profile,
    create_style_rule,
    create_topic,
    duplicate_prompt_profile,
    edit_candidate_reply,
    expire_candidate,
    get_engagement_candidate,
    get_engagement_target,
    get_engagement_settings,
    get_style_rule,
    get_topic,
    list_candidate_revisions,
    get_prompt_profile,
    list_engagement_actions,
    list_engagement_candidates,
    list_engagement_targets,
    list_prompt_profile_versions,
    list_prompt_profiles,
    list_style_rules,
    list_topics,
    preview_prompt_profile,
    reject_candidate,
    remove_topic_example,
    retry_candidate,
    rollback_prompt_profile,
    summarize_semantic_rollout,
    update_prompt_profile,
    update_style_rule,
    update_engagement_target,
    update_topic,
    upsert_engagement_settings,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])

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


@router.get(
    "/engagement/candidates/{candidate_id}",
    response_model=EngagementCandidateOut,
)
async def get_engagement_candidate_detail(
    candidate_id: UUID,
    db: DbSession,
) -> EngagementCandidateOut:
    try:
        candidate = await get_engagement_candidate(db, candidate_id=candidate_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementCandidateOut.model_validate(candidate)


@router.get(
    "/engagement/candidates/{candidate_id}/revisions",
    response_model=EngagementCandidateRevisionListResponse,
)
async def get_engagement_candidate_revisions(
    candidate_id: UUID,
    db: DbSession,
) -> EngagementCandidateRevisionListResponse:
    try:
        revisions = await list_candidate_revisions(db, candidate_id=candidate_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementCandidateRevisionListResponse(
        items=[
            EngagementCandidateRevisionOut.model_validate(revision)
            for revision in revisions
        ],
        total=len(revisions),
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


@router.get(
    "/engagement/semantic-rollout",
    response_model=EngagementSemanticRolloutSummaryOut,
)
async def get_engagement_semantic_rollout(
    db: DbSession,
    window_days: int = Query(default=14, ge=1, le=90),
    community_id: UUID | None = None,
    topic_id: UUID | None = None,
) -> EngagementSemanticRolloutSummaryOut:
    try:
        summary = await summarize_semantic_rollout(
            db,
            window_days=window_days,
            community_id=community_id,
            topic_id=topic_id,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementSemanticRolloutSummaryOut.model_validate(summary)


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
    "/engagement/candidates/{candidate_id}/edit",
    response_model=EngagementCandidateOut,
)
async def post_engagement_candidate_edit(
    candidate_id: UUID,
    payload: EngagementCandidateEditRequest,
    db: DbSession,
) -> EngagementCandidateOut:
    try:
        candidate = await edit_candidate_reply(
            db,
            candidate_id=candidate_id,
            final_reply=payload.final_reply,
            edited_by=payload.edited_by or "operator",
            edit_reason=payload.edit_reason,
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
    "/engagement/candidates/{candidate_id}/expire",
    response_model=EngagementCandidateOut,
)
async def post_engagement_candidate_expire(
    candidate_id: UUID,
    payload: EngagementCandidateExpireRequest,
    db: DbSession,
) -> EngagementCandidateOut:
    try:
        candidate = await expire_candidate(
            db,
            candidate_id=candidate_id,
            expired_by=payload.expired_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    await db.commit()
    return EngagementCandidateOut.model_validate(candidate)


@router.post(
    "/engagement/candidates/{candidate_id}/retry",
    response_model=EngagementCandidateOut,
)
async def post_engagement_candidate_retry(
    candidate_id: UUID,
    payload: EngagementCandidateRetryRequest,
    db: DbSession,
) -> EngagementCandidateOut:
    try:
        candidate = await retry_candidate(
            db,
            candidate_id=candidate_id,
            retried_by=payload.retried_by or "operator",
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

    scheduled_at = engagement_send_scheduled_at(candidate.id)
    try:
        await reserve_scheduled_send_action(
            db,
            candidate_id=candidate.id,
            scheduled_at=scheduled_at,
        )
        job = enqueue_engagement_send(
            candidate.id,
            approved_by=payload.approved_by or candidate.reviewed_by or "operator",
            scheduled_at=scheduled_at,
        )
        await db.commit()
    except QueueUnavailable as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": str(exc), "message": "Candidate cannot be queued for sending"},
        ) from exc
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

__all__ = ["router",
    "get_engagement_candidates",
    "get_engagement_candidate_detail",
    "get_engagement_candidate_revisions",
    "get_engagement_actions",
    "get_engagement_semantic_rollout",
    "post_engagement_candidate_approve",
    "post_engagement_candidate_edit",
    "post_engagement_candidate_reject",
    "post_engagement_candidate_expire",
    "post_engagement_candidate_retry",
    "post_engagement_candidate_send_job",
]
