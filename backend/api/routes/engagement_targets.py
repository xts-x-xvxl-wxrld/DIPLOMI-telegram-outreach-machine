# ruff: noqa: F401,F403,F405
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select

from backend.api.deps import (
    DbSession,
    OperatorCapabilitiesDep,
    require_bot_token,
    require_engagement_admin_capability,
)
from backend.api.schemas import (
    CollectionRunListResponse,
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
    EngagementCollectionJobRequest,
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
from backend.db.models import CollectionRun, Community, EngagementCandidate
from backend.queue.client import (
    QueueUnavailable,
    enqueue_community_join,
    enqueue_collection,
    enqueue_engagement_send,
    enqueue_engagement_target_resolve,
    enqueue_manual_engagement_detect,
)
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

@router.get("/operator/capabilities", response_model=OperatorCapabilitiesOut)
async def get_operator_capabilities(
    capabilities: OperatorCapabilitiesDep,
) -> OperatorCapabilitiesOut:
    return OperatorCapabilitiesOut(
        operator_user_id=capabilities.operator_user_id,
        backend_capabilities_available=capabilities.backend_capabilities_available,
        engagement_admin=capabilities.engagement_admin,
        source=capabilities.source,
    )


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


@router.get("/engagement/targets/{target_id}", response_model=EngagementTargetOut)
async def get_engagement_target_detail(
    target_id: UUID,
    db: DbSession,
) -> EngagementTargetOut:
    try:
        target = await get_engagement_target(db, target_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc

    return EngagementTargetOut.model_validate(target)


@router.post(
    "/engagement/targets",
    response_model=EngagementTargetOut,
    status_code=201,
    dependencies=[Depends(require_engagement_admin_capability)],
)
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


@router.patch(
    "/engagement/targets/{target_id}",
    response_model=EngagementTargetOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
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
    dependencies=[Depends(require_engagement_admin_capability)],
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
    "/engagement/targets/{target_id}/collection-jobs",
    response_model=JobResponse,
    status_code=202,
)
async def post_engagement_target_collection_job(
    target_id: UUID,
    payload: EngagementCollectionJobRequest,
    db: DbSession,
) -> JobResponse:
    try:
        target = await get_engagement_target(db, target_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    _ensure_target_can_collect(target)

    try:
        job = enqueue_collection(
            target.community_id,
            reason="engagement",
            requested_by=payload.requested_by or "operator",
            window_days=payload.window_days,
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


@router.get(
    "/engagement/targets/{target_id}/collection-runs",
    response_model=CollectionRunListResponse,
)
async def get_engagement_target_collection_runs(
    target_id: UUID,
    db: DbSession,
) -> CollectionRunListResponse:
    try:
        target = await get_engagement_target(db, target_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    if target.community_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "target_not_resolved", "message": "Engagement target is not resolved"},
        )

    rows = await db.scalars(
        select(CollectionRun)
        .where(CollectionRun.community_id == target.community_id)
        .order_by(desc(CollectionRun.started_at))
        .limit(20)
    )
    return CollectionRunListResponse(items=list(rows))


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


def _ensure_target_can_collect(target: object) -> None:
    if target.community_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "target_not_resolved", "message": "Engagement target is not resolved"},
        )
    if target.status != "approved":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "target_not_approved",
                "message": "Manual engagement collection requires an approved target",
            },
        )
    if not target.allow_detect:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "target_detect_not_approved",
                "message": "Engagement target must allow detection before collection",
            },
        )


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
    "get_operator_capabilities",
    "get_engagement_targets",
    "get_engagement_target_detail",
    "post_engagement_target",
    "patch_engagement_target",
    "post_engagement_target_resolve_job",
    "post_engagement_target_join_job",
    "post_engagement_target_collection_job",
    "get_engagement_target_collection_runs",
    "post_engagement_target_detect_job",
]
