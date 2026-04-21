from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import DbSession, require_bot_token
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


@router.post("/engagement/topics/{topic_id}/examples", response_model=EngagementTopicOut)
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


@router.delete("/engagement/topics/{topic_id}/examples/{example_type}/{index}", response_model=EngagementTopicOut)
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


@router.post("/engagement/prompt-profiles", response_model=EngagementPromptProfileOut, status_code=201)
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


@router.patch("/engagement/prompt-profiles/{profile_id}", response_model=EngagementPromptProfileOut)
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


@router.post("/engagement/prompt-profiles/{profile_id}/activate", response_model=EngagementPromptProfileOut)
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


@router.post("/engagement/prompt-profiles/{profile_id}/duplicate", response_model=EngagementPromptProfileOut)
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


@router.post("/engagement/prompt-profiles/{profile_id}/rollback", response_model=EngagementPromptProfileOut)
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


@router.post("/engagement/style-rules", response_model=EngagementStyleRuleOut, status_code=201)
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


@router.patch("/engagement/style-rules/{rule_id}", response_model=EngagementStyleRuleOut)
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
