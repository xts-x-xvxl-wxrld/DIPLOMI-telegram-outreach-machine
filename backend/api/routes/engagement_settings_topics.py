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
    dependencies=[Depends(require_engagement_admin_capability)],
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


@router.get("/engagement/topics/{topic_id}", response_model=EngagementTopicOut)
async def get_engagement_topic_detail(
    topic_id: UUID,
    db: DbSession,
) -> EngagementTopicOut:
    try:
        topic = await get_topic(db, topic_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementTopicOut.model_validate(topic)


@router.post(
    "/engagement/topics",
    response_model=EngagementTopicOut,
    status_code=201,
    dependencies=[Depends(require_engagement_admin_capability)],
)
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


@router.patch(
    "/engagement/topics/{topic_id}",
    response_model=EngagementTopicOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
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
    "/engagement/topics/{topic_id}/examples",
    response_model=EngagementTopicOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def post_engagement_topic_example(
    topic_id: UUID,
    payload: EngagementTopicExampleCreateRequest,
    db: DbSession,
) -> EngagementTopicOut:
    try:
        topic = await add_topic_example(
            db,
            topic_id=topic_id,
            example_type=payload.example_type,
            example=payload.example,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementTopicOut.model_validate(topic)


@router.delete(
    "/engagement/topics/{topic_id}/examples/{example_type}/{index}",
    response_model=EngagementTopicOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def delete_engagement_topic_example(
    topic_id: UUID,
    example_type: str,
    index: int,
    db: DbSession,
) -> EngagementTopicOut:
    try:
        topic = await remove_topic_example(
            db,
            topic_id=topic_id,
            example_type=example_type,
            index=index,
        )
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
    "get_community_engagement_settings",
    "put_community_engagement_settings",
    "get_engagement_topics",
    "get_engagement_topic_detail",
    "post_engagement_topic",
    "patch_engagement_topic",
    "post_engagement_topic_example",
    "delete_engagement_topic_example",
    "post_community_join_job",
    "post_community_engagement_detect_job",
]
