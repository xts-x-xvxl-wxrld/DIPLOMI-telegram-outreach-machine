# ruff: noqa: F401,F403,F405
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    CockpitApprovalQueueResponse,
    CockpitDraftActionResponse,
    CockpitDraftEditRequest,
    CockpitEngagementDetailResponse,
    CockpitEngagementListResponse,
    CockpitHomeResponse,
    CockpitIssueActionResponse,
    CockpitIssueQueueResponse,
    CockpitQuietHoursReadResponse,
    CockpitQuietHoursWriteRequest,
    CockpitQuietHoursWriteResponse,
    CockpitRateLimitDetailResponse,
    CockpitSentFeedResponse,
)
from backend.queue.client import enqueue_engagement_target_resolve
from backend.services.task_first_engagement_cockpit import (
    get_cockpit_approvals,
    get_cockpit_engagement_detail,
    get_cockpit_home,
    get_cockpit_issues,
    list_cockpit_engagements,
    list_cockpit_sent,
)
from backend.services.task_first_engagement_cockpit_mutations import (
    act_on_cockpit_issue,
    approve_cockpit_draft,
    get_cockpit_quiet_hours,
    get_cockpit_rate_limit_detail,
    queue_cockpit_draft_update,
    reject_cockpit_draft,
    update_cockpit_quiet_hours,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.get("/engagement/cockpit/home", response_model=CockpitHomeResponse)
async def get_engagement_cockpit_home(
    db: DbSession,
) -> CockpitHomeResponse:
    payload = await get_cockpit_home(db)
    return CockpitHomeResponse(
        state=payload.state,
        draft_count=payload.draft_count,
        issue_count=payload.issue_count,
        active_engagement_count=payload.active_engagement_count,
        has_sent_messages=payload.has_sent_messages,
        next_draft_preview=None
        if payload.next_draft_preview is None
        else payload.next_draft_preview,
        latest_issue_preview=None
        if payload.latest_issue_preview is None
        else payload.latest_issue_preview,
    )


@router.get("/engagement/cockpit/approvals", response_model=CockpitApprovalQueueResponse)
async def get_engagement_cockpit_approvals(
    db: DbSession,
) -> CockpitApprovalQueueResponse:
    payload = await get_cockpit_approvals(db)
    return CockpitApprovalQueueResponse.model_validate(payload)


@router.get(
    "/engagement/cockpit/engagements/{engagement_id}/approvals",
    response_model=CockpitApprovalQueueResponse,
)
async def get_engagement_cockpit_scoped_approvals(
    engagement_id: UUID,
    db: DbSession,
) -> CockpitApprovalQueueResponse:
    detail = await get_cockpit_engagement_detail(db, engagement_id=engagement_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "engagement_not_found", "message": "Engagement not found"})
    payload = await get_cockpit_approvals(db, engagement_id=engagement_id)
    return CockpitApprovalQueueResponse.model_validate(payload)


@router.get("/engagement/cockpit/issues", response_model=CockpitIssueQueueResponse)
async def get_engagement_cockpit_issues(
    db: DbSession,
) -> CockpitIssueQueueResponse:
    payload = await get_cockpit_issues(db)
    return CockpitIssueQueueResponse.model_validate(payload)


@router.get(
    "/engagement/cockpit/engagements/{engagement_id}/issues",
    response_model=CockpitIssueQueueResponse,
)
async def get_engagement_cockpit_scoped_issues(
    engagement_id: UUID,
    db: DbSession,
) -> CockpitIssueQueueResponse:
    detail = await get_cockpit_engagement_detail(db, engagement_id=engagement_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "engagement_not_found", "message": "Engagement not found"})
    payload = await get_cockpit_issues(db, engagement_id=engagement_id)
    return CockpitIssueQueueResponse.model_validate(payload)


@router.get("/engagement/cockpit/engagements", response_model=CockpitEngagementListResponse)
async def get_engagement_cockpit_engagements(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CockpitEngagementListResponse:
    payload = await list_cockpit_engagements(db, limit=limit, offset=offset)
    return CockpitEngagementListResponse.model_validate(payload)


@router.get(
    "/engagement/cockpit/engagements/{engagement_id}",
    response_model=CockpitEngagementDetailResponse,
)
async def get_engagement_cockpit_engagement_detail(
    engagement_id: UUID,
    db: DbSession,
) -> CockpitEngagementDetailResponse:
    payload = await get_cockpit_engagement_detail(db, engagement_id=engagement_id)
    if payload is None:
        raise HTTPException(status_code=404, detail={"code": "engagement_not_found", "message": "Engagement not found"})
    return CockpitEngagementDetailResponse.model_validate(payload)


@router.get("/engagement/cockpit/sent", response_model=CockpitSentFeedResponse)
async def get_engagement_cockpit_sent(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CockpitSentFeedResponse:
    payload = await list_cockpit_sent(db, limit=limit, offset=offset)
    return CockpitSentFeedResponse.model_validate(payload)


@router.post(
    "/engagement/cockpit/drafts/{draft_id}/approve",
    response_model=CockpitDraftActionResponse,
)
async def post_engagement_cockpit_draft_approve(
    draft_id: UUID,
    db: DbSession,
) -> CockpitDraftActionResponse:
    payload = await approve_cockpit_draft(db, draft_id=draft_id, requested_by="operator")
    if payload.result == "approved":
        await db.commit()
    return CockpitDraftActionResponse.model_validate(payload)


@router.post(
    "/engagement/cockpit/drafts/{draft_id}/reject",
    response_model=CockpitDraftActionResponse,
)
async def post_engagement_cockpit_draft_reject(
    draft_id: UUID,
    db: DbSession,
) -> CockpitDraftActionResponse:
    payload = await reject_cockpit_draft(db, draft_id=draft_id, requested_by="operator")
    if payload.result == "rejected":
        await db.commit()
    return CockpitDraftActionResponse.model_validate(payload)


@router.post(
    "/engagement/cockpit/drafts/{draft_id}/edit",
    response_model=CockpitDraftActionResponse,
)
async def post_engagement_cockpit_draft_edit(
    draft_id: UUID,
    payload: CockpitDraftEditRequest,
    db: DbSession,
) -> CockpitDraftActionResponse:
    result = await queue_cockpit_draft_update(
        db,
        draft_id=draft_id,
        requested_by=payload.requested_by or "operator",
        edit_request=payload.edit_request,
    )
    if result.result == "queued_update":
        await db.commit()
    return CockpitDraftActionResponse.model_validate(result)


@router.post(
    "/engagement/cockpit/issues/{issue_id}/actions/{action_key}",
    response_model=CockpitIssueActionResponse,
)
async def post_engagement_cockpit_issue_action(
    issue_id: UUID,
    action_key: str,
    db: DbSession,
) -> CockpitIssueActionResponse:
    payload = await act_on_cockpit_issue(
        db,
        issue_id=issue_id,
        action_key=action_key,
        requested_by="operator",
        enqueue_target_resolve=enqueue_engagement_target_resolve,
    )
    if payload.result == "resolved":
        await db.commit()
    return CockpitIssueActionResponse.model_validate(payload)


@router.get(
    "/engagement/cockpit/issues/{issue_id}/rate-limit",
    response_model=CockpitRateLimitDetailResponse,
)
async def get_engagement_cockpit_issue_rate_limit(
    issue_id: UUID,
    db: DbSession,
) -> CockpitRateLimitDetailResponse:
    payload = await get_cockpit_rate_limit_detail(db, issue_id=issue_id)
    return CockpitRateLimitDetailResponse.model_validate(payload)


@router.get(
    "/engagement/cockpit/engagements/{engagement_id}/quiet-hours",
    response_model=CockpitQuietHoursReadResponse,
)
async def get_engagement_cockpit_quiet_hours(
    engagement_id: UUID,
    db: DbSession,
) -> CockpitQuietHoursReadResponse:
    payload = await get_cockpit_quiet_hours(db, engagement_id=engagement_id)
    return CockpitQuietHoursReadResponse.model_validate(payload)


@router.put(
    "/engagement/cockpit/engagements/{engagement_id}/quiet-hours",
    response_model=CockpitQuietHoursWriteResponse,
)
async def put_engagement_cockpit_quiet_hours(
    engagement_id: UUID,
    payload: CockpitQuietHoursWriteRequest,
    db: DbSession,
) -> CockpitQuietHoursWriteResponse:
    result = await update_cockpit_quiet_hours(
        db,
        engagement_id=engagement_id,
        quiet_hours_enabled=payload.quiet_hours_enabled,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
    )
    if result.result == "updated":
        await db.commit()
    return CockpitQuietHoursWriteResponse.model_validate(result)


__all__ = [
    "get_engagement_cockpit_approvals",
    "get_engagement_cockpit_engagement_detail",
    "get_engagement_cockpit_engagements",
    "get_engagement_cockpit_home",
    "get_engagement_cockpit_issues",
    "get_engagement_cockpit_issue_rate_limit",
    "get_engagement_cockpit_quiet_hours",
    "get_engagement_cockpit_scoped_approvals",
    "get_engagement_cockpit_scoped_issues",
    "get_engagement_cockpit_sent",
    "post_engagement_cockpit_draft_approve",
    "post_engagement_cockpit_draft_edit",
    "post_engagement_cockpit_draft_reject",
    "post_engagement_cockpit_issue_action",
    "put_engagement_cockpit_quiet_hours",
    "router",
]
