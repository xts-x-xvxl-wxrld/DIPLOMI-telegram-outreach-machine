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

@router.get("/engagement/prompt-profiles", response_model=EngagementPromptProfileListResponse)
async def get_engagement_prompt_profiles(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EngagementPromptProfileListResponse:
    result = await list_prompt_profiles(db, limit=limit, offset=offset)
    return EngagementPromptProfileListResponse(
        items=[EngagementPromptProfileOut.model_validate(item) for item in result.items],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.post(
    "/engagement/prompt-profiles",
    response_model=EngagementPromptProfileOut,
    status_code=201,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def post_engagement_prompt_profile(
    payload: EngagementPromptProfileCreateRequest,
    db: DbSession,
) -> EngagementPromptProfileOut:
    try:
        profile = await create_prompt_profile(
            db,
            payload=payload,
            created_by=payload.created_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementPromptProfileOut.model_validate(profile)


@router.get("/engagement/prompt-profiles/{profile_id}", response_model=EngagementPromptProfileOut)
async def get_engagement_prompt_profile(
    profile_id: UUID,
    db: DbSession,
) -> EngagementPromptProfileOut:
    try:
        profile = await get_prompt_profile(db, profile_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementPromptProfileOut.model_validate(profile)


@router.patch(
    "/engagement/prompt-profiles/{profile_id}",
    response_model=EngagementPromptProfileOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def patch_engagement_prompt_profile(
    profile_id: UUID,
    payload: EngagementPromptProfileUpdateRequest,
    db: DbSession,
) -> EngagementPromptProfileOut:
    try:
        profile = await update_prompt_profile(
            db,
            profile_id=profile_id,
            payload=payload,
            updated_by=payload.updated_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementPromptProfileOut.model_validate(profile)


@router.post(
    "/engagement/prompt-profiles/{profile_id}/activate",
    response_model=EngagementPromptProfileOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def post_engagement_prompt_profile_activate(
    profile_id: UUID,
    payload: EngagementPromptProfileActivateRequest,
    db: DbSession,
) -> EngagementPromptProfileOut:
    try:
        profile = await activate_prompt_profile(
            db,
            profile_id=profile_id,
            updated_by=payload.updated_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementPromptProfileOut.model_validate(profile)


@router.post(
    "/engagement/prompt-profiles/{profile_id}/duplicate",
    response_model=EngagementPromptProfileOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def post_engagement_prompt_profile_duplicate(
    profile_id: UUID,
    payload: EngagementPromptProfileDuplicateRequest,
    db: DbSession,
) -> EngagementPromptProfileOut:
    try:
        profile = await duplicate_prompt_profile(
            db,
            profile_id=profile_id,
            created_by=payload.created_by or "operator",
            name=payload.name,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementPromptProfileOut.model_validate(profile)


@router.post(
    "/engagement/prompt-profiles/{profile_id}/rollback",
    response_model=EngagementPromptProfileOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def post_engagement_prompt_profile_rollback(
    profile_id: UUID,
    payload: EngagementPromptProfileRollbackRequest,
    db: DbSession,
) -> EngagementPromptProfileOut:
    try:
        profile = await rollback_prompt_profile(
            db,
            profile_id=profile_id,
            version_id=payload.version_id,
            updated_by=payload.updated_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementPromptProfileOut.model_validate(profile)


@router.post("/engagement/prompt-profiles/{profile_id}/preview", response_model=EngagementPromptPreviewOut)
async def post_engagement_prompt_profile_preview(
    profile_id: UUID,
    payload: EngagementPromptProfilePreviewRequest,
    db: DbSession,
) -> EngagementPromptPreviewOut:
    try:
        preview = await preview_prompt_profile(
            db,
            profile_id=profile_id,
            variables=payload.variables,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementPromptPreviewOut.model_validate(preview)


@router.get(
    "/engagement/prompt-profiles/{profile_id}/versions",
    response_model=EngagementPromptProfileVersionListResponse,
)
async def get_engagement_prompt_profile_versions(
    profile_id: UUID,
    db: DbSession,
) -> EngagementPromptProfileVersionListResponse:
    try:
        versions = await list_prompt_profile_versions(db, profile_id=profile_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementPromptProfileVersionListResponse(
        items=[EngagementPromptProfileVersionOut.model_validate(version) for version in versions]
    )


@router.get("/engagement/style-rules", response_model=EngagementStyleRuleListResponse)
async def get_engagement_style_rules(
    db: DbSession,
    scope_type: str | None = None,
    scope_id: UUID | None = None,
    active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EngagementStyleRuleListResponse:
    try:
        result = await list_style_rules(
            db,
            scope_type=scope_type,
            scope_id=scope_id,
            active=active,
            limit=limit,
            offset=offset,
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementStyleRuleListResponse(
        items=[EngagementStyleRuleOut.model_validate(rule) for rule in result.items],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.get("/engagement/style-rules/{rule_id}", response_model=EngagementStyleRuleOut)
async def get_engagement_style_rule_detail(
    rule_id: UUID,
    db: DbSession,
) -> EngagementStyleRuleOut:
    try:
        rule = await get_style_rule(db, rule_id)
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    return EngagementStyleRuleOut.model_validate(rule)


@router.post(
    "/engagement/style-rules",
    response_model=EngagementStyleRuleOut,
    status_code=201,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def post_engagement_style_rule(
    payload: EngagementStyleRuleCreateRequest,
    db: DbSession,
) -> EngagementStyleRuleOut:
    try:
        rule = await create_style_rule(
            db,
            payload=payload,
            created_by=payload.created_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementStyleRuleOut.model_validate(rule)


@router.patch(
    "/engagement/style-rules/{rule_id}",
    response_model=EngagementStyleRuleOut,
    dependencies=[Depends(require_engagement_admin_capability)],
)
async def patch_engagement_style_rule(
    rule_id: UUID,
    payload: EngagementStyleRuleUpdateRequest,
    db: DbSession,
) -> EngagementStyleRuleOut:
    try:
        rule = await update_style_rule(
            db,
            rule_id=rule_id,
            payload=payload,
            updated_by=payload.updated_by or "operator",
        )
    except EngagementServiceError as exc:
        raise _http_error(exc) from exc
    await db.commit()
    return EngagementStyleRuleOut.model_validate(rule)


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
    "get_engagement_prompt_profiles",
    "post_engagement_prompt_profile",
    "get_engagement_prompt_profile",
    "patch_engagement_prompt_profile",
    "post_engagement_prompt_profile_activate",
    "post_engagement_prompt_profile_duplicate",
    "post_engagement_prompt_profile_rollback",
    "post_engagement_prompt_profile_preview",
    "get_engagement_prompt_profile_versions",
    "get_engagement_style_rules",
    "get_engagement_style_rule_detail",
    "post_engagement_style_rule",
    "patch_engagement_style_rule",
]
