# ruff: noqa: F401,F403,F405
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    CockpitApprovalQueueResponse,
    CockpitEngagementDetailResponse,
    CockpitEngagementListResponse,
    CockpitHomeResponse,
    CockpitIssueQueueResponse,
    CockpitSentFeedResponse,
)
from backend.services.task_first_engagement_cockpit import (
    get_cockpit_approvals,
    get_cockpit_engagement_detail,
    get_cockpit_home,
    get_cockpit_issues,
    list_cockpit_engagements,
    list_cockpit_sent,
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


__all__ = [
    "get_engagement_cockpit_approvals",
    "get_engagement_cockpit_engagement_detail",
    "get_engagement_cockpit_engagements",
    "get_engagement_cockpit_home",
    "get_engagement_cockpit_issues",
    "get_engagement_cockpit_scoped_approvals",
    "get_engagement_cockpit_scoped_issues",
    "get_engagement_cockpit_sent",
    "router",
]
