from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import EngagementCandidateStatus, EngagementMode, EngagementStatus, EngagementTargetStatus
from backend.db.models import (
    Engagement,
    EngagementCandidate,
    EngagementDraftUpdateRequest,
    EngagementSettings,
    EngagementTarget,
)
from backend.services.community_engagement import (
    EngagementConflict,
    EngagementNotFound,
    EngagementServiceError,
    EngagementValidationError,
    approve_candidate,
    retry_candidate,
)
from backend.services.community_engagement_targets import update_engagement_target
from backend.services.task_first_engagement_draft_updates import (
    get_draft_update_request_by_source_candidate,
    has_active_draft_update_request,
)
from backend.services.task_first_engagement_issues import get_task_first_issue, list_task_first_issues


@dataclass(frozen=True)
class CockpitDraftActionResult:
    result: str
    message: str
    draft_id: UUID | None = None
    engagement_id: UUID | None = None
    next_callback: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class CockpitIssueActionResult:
    result: str
    message: str
    next_callback: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class CockpitRateLimitDetailResult:
    result: str
    message: str
    next_callback: str
    issue_id: UUID | None = None
    engagement_id: UUID | None = None
    title: str | None = None
    target_label: str | None = None
    blocked_action_label: str | None = None
    scope_label: str | None = None
    reset_at: datetime | None = None


@dataclass(frozen=True)
class CockpitQuietHoursReadResult:
    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    title: str | None = None
    target_label: str | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


@dataclass(frozen=True)
class CockpitQuietHoursWriteResult:
    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    code: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def approve_cockpit_draft(
    db: AsyncSession,
    *,
    draft_id: UUID,
    requested_by: str,
) -> CockpitDraftActionResult:
    candidate = await _get_candidate(db, draft_id)
    if candidate is None:
        return CockpitDraftActionResult(result="stale", message="Draft no longer needs approval")
    if await has_active_draft_update_request(db, source_candidate_id=candidate.id):
        return CockpitDraftActionResult(
            result="blocked",
            message="Couldn't approve draft",
            code="draft_not_reviewable",
        )
    try:
        approved = await approve_candidate(
            db,
            candidate_id=candidate.id,
            approved_by=requested_by,
        )
    except EngagementServiceError as exc:
        return _draft_action_error(exc, stale_message="Draft no longer needs approval", blocked_message="Couldn't approve draft")
    engagement = await _find_candidate_engagement(db, candidate)
    return CockpitDraftActionResult(
        result="approved",
        message="Draft approved",
        draft_id=approved.id,
        engagement_id=None if engagement is None else engagement.id,
        next_callback="eng:appr:list:0",
    )


async def reject_cockpit_draft(
    db: AsyncSession,
    *,
    draft_id: UUID,
    requested_by: str,
) -> CockpitDraftActionResult:
    candidate = await _get_candidate(db, draft_id)
    if candidate is None:
        return CockpitDraftActionResult(result="stale", message="Draft no longer needs approval")
    if candidate.status != EngagementCandidateStatus.NEEDS_REVIEW.value:
        return CockpitDraftActionResult(
            result="stale",
            message="Draft no longer needs approval",
        )
    if await has_active_draft_update_request(db, source_candidate_id=candidate.id):
        return CockpitDraftActionResult(
            result="blocked",
            message="Couldn't reject draft",
            code="draft_not_reviewable",
        )
    now = _utcnow()
    candidate.status = EngagementCandidateStatus.REJECTED.value
    candidate.reviewed_by = requested_by
    candidate.reviewed_at = now
    candidate.updated_at = now
    await db.flush()
    engagement = await _find_candidate_engagement(db, candidate)
    return CockpitDraftActionResult(
        result="rejected",
        message="Draft rejected",
        draft_id=candidate.id,
        engagement_id=None if engagement is None else engagement.id,
        next_callback="eng:appr:list:0",
    )


async def queue_cockpit_draft_update(
    db: AsyncSession,
    *,
    draft_id: UUID,
    requested_by: str,
    edit_request: str,
) -> CockpitDraftActionResult:
    candidate = await _get_candidate(db, draft_id)
    if candidate is None or candidate.status != EngagementCandidateStatus.NEEDS_REVIEW.value:
        return CockpitDraftActionResult(result="stale", message="Draft no longer needs approval")
    if await get_draft_update_request_by_source_candidate(db, source_candidate_id=candidate.id) is not None:
        return CockpitDraftActionResult(
            result="blocked",
            message="Couldn't update draft",
            code="edit_not_allowed",
        )
    engagement = await _find_candidate_engagement(db, candidate)
    if engagement is None:
        return CockpitDraftActionResult(result="stale", message="Draft no longer needs approval")

    now = _utcnow()
    db.add(
        EngagementDraftUpdateRequest(
            id=uuid.uuid4(),
            engagement_id=engagement.id,
            source_candidate_id=candidate.id,
            replacement_candidate_id=None,
            status="pending",
            edit_request=edit_request.strip(),
            requested_by=requested_by,
            source_queue_created_at=candidate.created_at,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
    )
    await db.flush()
    return CockpitDraftActionResult(
        result="queued_update",
        message="Updating draft",
        draft_id=candidate.id,
        engagement_id=engagement.id,
        next_callback="eng:appr:list:0",
    )


async def act_on_cockpit_issue(
    db: AsyncSession,
    *,
    issue_id: UUID,
    action_key: str,
    requested_by: str,
    enqueue_target_resolve,
) -> CockpitIssueActionResult:
    issue = await get_task_first_issue(db, issue_id=issue_id)
    if issue is None:
        return CockpitIssueActionResult(
            result="stale",
            message="Issue no longer needs attention",
            next_callback="eng:iss:list:0",
        )
    if action_key not in {action.action_key for action in issue.fix_actions}:
        return CockpitIssueActionResult(
            result="blocked",
            message="Couldn't resolve issue",
            code="unsupported_issue_action",
        )

    if action_key in {"chtopic", "crtopic"}:
        return CockpitIssueActionResult(
            result="next_step",
            message="Choose a topic",
            next_callback=f"eng:wz:edit:{issue.engagement_id}:topic",
        )
    if action_key in {"chacct", "swapacct"}:
        return CockpitIssueActionResult(
            result="next_step",
            message="Choose an account",
            next_callback=f"eng:wz:edit:{issue.engagement_id}:account",
        )
    if action_key == "ratelimit":
        return CockpitIssueActionResult(
            result="next_step",
            message="Open rate limit detail",
            next_callback=f"eng:rate:open:{issue.issue_id}",
        )
    if action_key == "quiet":
        return CockpitIssueActionResult(
            result="next_step",
            message="Change quiet hours",
            next_callback=f"eng:quiet:open:{issue.engagement_id}:{issue.issue_id}",
        )
    if action_key == "resume":
        return await _resume_issue_engagement(db, issue_id=issue_id, requested_by=requested_by)
    if action_key == "retry":
        return await _retry_issue_candidate(db, issue_id=issue_id, requested_by=requested_by)
    if action_key == "apptgt":
        return await _approve_issue_target(db, issue_id=issue_id, requested_by=requested_by)
    if action_key == "rsvtgt":
        if issue.target_id is None:
            return CockpitIssueActionResult(result="blocked", message="Couldn't start target resolution", code="target_not_resolved")
        enqueue_target_resolve(target_id=issue.target_id, requested_by=requested_by)
        return CockpitIssueActionResult(
            result="resolved",
            message="Target resolution started",
            next_callback="eng:iss:list:0",
        )
    if action_key == "fixperm":
        return await _fix_issue_permissions(db, issue_id=issue_id)

    return CockpitIssueActionResult(
        result="blocked",
        message="Couldn't resolve issue",
        code="unsupported_issue_action",
    )


async def get_cockpit_rate_limit_detail(
    db: AsyncSession,
    *,
    issue_id: UUID,
) -> CockpitRateLimitDetailResult:
    issue = await get_task_first_issue(db, issue_id=issue_id)
    if issue is None or issue.issue_type != "rate_limit_active":
        return CockpitRateLimitDetailResult(
            result="stale",
            message="Rate limit is no longer active",
            next_callback="eng:iss:list:0",
        )
    return CockpitRateLimitDetailResult(
        result="ready",
        message=issue.message or "Sending is paused until the limit clears.",
        next_callback=f"eng:iss:open:{issue.issue_id}",
        issue_id=issue.issue_id,
        engagement_id=issue.engagement_id,
        title=issue.issue_label,
        target_label=issue.target_label,
        blocked_action_label=issue.blocked_action_label or "Send reply",
        scope_label=issue.scope_label or "Send limit",
        reset_at=issue.reset_at,
    )


async def get_cockpit_quiet_hours(
    db: AsyncSession,
    *,
    engagement_id: UUID,
) -> CockpitQuietHoursReadResult:
    issue = await _find_quiet_hours_issue(db, engagement_id=engagement_id)
    if issue is None:
        return CockpitQuietHoursReadResult(
            result="stale",
            message="Quiet hours no longer need changes",
            next_callback="eng:iss:list:0",
        )

    engagement = await db.get(Engagement, engagement_id)
    settings = await _get_engagement_settings(db, engagement_id=engagement_id)
    if engagement is None or settings is None:
        return CockpitQuietHoursReadResult(
            result="stale",
            message="Quiet hours no longer need changes",
            next_callback="eng:iss:list:0",
        )
    enabled = settings.quiet_hours_start is not None and settings.quiet_hours_end is not None
    return CockpitQuietHoursReadResult(
        result="ready",
        message="Quiet hours are blocking the engagement right now.",
        next_callback=f"eng:iss:open:{issue.issue_id}",
        engagement_id=engagement_id,
        title="Change quiet hours",
        target_label=issue.target_label,
        quiet_hours_enabled=enabled,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
    )


async def update_cockpit_quiet_hours(
    db: AsyncSession,
    *,
    engagement_id: UUID,
    quiet_hours_enabled: bool,
    quiet_hours_start: time | None,
    quiet_hours_end: time | None,
) -> CockpitQuietHoursWriteResult:
    issue = await _find_quiet_hours_issue(db, engagement_id=engagement_id)
    if issue is None:
        return CockpitQuietHoursWriteResult(
            result="stale",
            message="Quiet hours no longer need changes",
            next_callback="eng:iss:list:0",
        )

    engagement = await db.get(Engagement, engagement_id)
    settings = await _get_engagement_settings(db, engagement_id=engagement_id)
    if engagement is None or settings is None or engagement.status == EngagementStatus.ARCHIVED.value:
        return CockpitQuietHoursWriteResult(
            result="stale",
            message="Quiet hours no longer need changes",
            next_callback="eng:iss:list:0",
        )

    if quiet_hours_enabled and (quiet_hours_start is None or quiet_hours_end is None):
        return CockpitQuietHoursWriteResult(
            result="blocked",
            message="Couldn't update quiet hours",
            next_callback=f"eng:iss:open:{issue.issue_id}",
            code="quiet_hours_invalid",
        )

    next_start = quiet_hours_start if quiet_hours_enabled else None
    next_end = quiet_hours_end if quiet_hours_enabled else None
    if settings.quiet_hours_start == next_start and settings.quiet_hours_end == next_end:
        return CockpitQuietHoursWriteResult(
            result="noop",
            message="No quiet-hours changes",
            next_callback=f"eng:iss:open:{issue.issue_id}",
            engagement_id=engagement_id,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_hours_start=next_start,
            quiet_hours_end=next_end,
        )

    settings.quiet_hours_start = next_start
    settings.quiet_hours_end = next_end
    settings.updated_at = _utcnow()
    await db.flush()
    return CockpitQuietHoursWriteResult(
        result="updated",
        message="Quiet hours updated" if quiet_hours_enabled else "Quiet hours turned off",
        next_callback="eng:iss:list:0",
        engagement_id=engagement_id,
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=next_start,
        quiet_hours_end=next_end,
    )


async def _resume_issue_engagement(
    db: AsyncSession,
    *,
    issue_id: UUID,
    requested_by: str,
) -> CockpitIssueActionResult:
    del requested_by
    issue = await get_task_first_issue(db, issue_id=issue_id)
    if issue is None or issue.issue_type != "sending_is_paused":
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")
    engagement = await db.get(Engagement, issue.engagement_id)
    settings = await _get_engagement_settings(db, engagement_id=issue.engagement_id)
    if engagement is None or settings is None:
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")

    changed = False
    now = _utcnow()
    if engagement.status != EngagementStatus.ACTIVE.value:
        engagement.status = EngagementStatus.ACTIVE.value
        engagement.updated_at = now
        changed = True
    if settings.mode == EngagementMode.DISABLED.value:
        settings.mode = EngagementMode.SUGGEST.value
        settings.allow_join = True
        settings.allow_post = False
        settings.updated_at = now
        changed = True
    if not changed:
        return CockpitIssueActionResult(result="noop", message="No sending changes", next_callback=f"eng:iss:open:{issue.issue_id}")
    await db.flush()
    return CockpitIssueActionResult(result="resolved", message="Sending resumed", next_callback="eng:iss:list:0")


async def _retry_issue_candidate(
    db: AsyncSession,
    *,
    issue_id: UUID,
    requested_by: str,
) -> CockpitIssueActionResult:
    issue = await get_task_first_issue(db, issue_id=issue_id)
    if issue is None or issue.issue_type != "reply_failed" or issue.candidate_id is None:
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")
    try:
        await retry_candidate(db, candidate_id=issue.candidate_id, retried_by=requested_by)
    except EngagementServiceError as exc:
        return _issue_action_error(exc, stale_message="Issue no longer needs attention", blocked_message="Couldn't reopen reply")
    return CockpitIssueActionResult(result="resolved", message="Reply reopened", next_callback="eng:iss:list:0")


async def _approve_issue_target(
    db: AsyncSession,
    *,
    issue_id: UUID,
    requested_by: str,
) -> CockpitIssueActionResult:
    issue = await get_task_first_issue(db, issue_id=issue_id)
    if issue is None or issue.issue_type != "target_not_approved" or issue.target_id is None:
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")
    engagement = await db.get(Engagement, issue.engagement_id)
    settings = await _get_engagement_settings(db, engagement_id=issue.engagement_id)
    if engagement is None:
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")

    try:
        payload = SimpleNamespace(
            status=EngagementTargetStatus.APPROVED.value,
            allow_join=True,
            allow_detect=True,
            allow_post=bool(settings is not None and settings.mode == EngagementMode.AUTO_LIMITED.value),
            notes=None,
            model_fields_set={"status", "allow_join", "allow_detect", "allow_post"},
        )
        await update_engagement_target(
            db,
            target_id=issue.target_id,
            payload=payload,
            updated_by=requested_by,
        )
    except (EngagementNotFound, EngagementConflict, EngagementValidationError) as exc:
        return _issue_action_error(exc, stale_message="Issue no longer needs attention", blocked_message="Couldn't approve target")
    return CockpitIssueActionResult(result="resolved", message="Target approved", next_callback="eng:iss:list:0")


async def _fix_issue_permissions(
    db: AsyncSession,
    *,
    issue_id: UUID,
) -> CockpitIssueActionResult:
    issue = await get_task_first_issue(db, issue_id=issue_id)
    if issue is None or issue.issue_type != "community_permissions_missing" or issue.target_id is None:
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")

    engagement = await db.get(Engagement, issue.engagement_id)
    target = await db.get(EngagementTarget, issue.target_id)
    settings = await _get_engagement_settings(db, engagement_id=issue.engagement_id)
    if engagement is None or target is None or settings is None:
        return CockpitIssueActionResult(result="stale", message="Issue no longer needs attention", next_callback="eng:iss:list:0")

    now = _utcnow()
    allow_post = settings.mode == EngagementMode.AUTO_LIMITED.value
    changed = False
    for attr, value in (
        ("allow_join", True),
        ("allow_post", allow_post),
    ):
        if getattr(settings, attr) != value:
            setattr(settings, attr, value)
            changed = True
    for attr, value in (
        ("allow_join", True),
        ("allow_detect", True),
        ("allow_post", allow_post),
    ):
        if getattr(target, attr) != value:
            setattr(target, attr, value)
            changed = True
    if not changed:
        return CockpitIssueActionResult(result="noop", message="No permission changes", next_callback=f"eng:iss:open:{issue.issue_id}")
    settings.updated_at = now
    target.updated_at = now
    await db.flush()
    return CockpitIssueActionResult(result="resolved", message="Permissions fixed", next_callback="eng:iss:list:0")


async def _find_quiet_hours_issue(
    db: AsyncSession,
    *,
    engagement_id: UUID,
):
    issues = await list_task_first_issues(db, engagement_id=engagement_id)
    for issue in issues:
        if issue.issue_type == "quiet_hours_active":
            return issue
    return None


async def _get_candidate(db: AsyncSession, candidate_id: UUID) -> EngagementCandidate | None:
    return await db.scalar(
        select(EngagementCandidate)
        .options(joinedload(EngagementCandidate.topic))
        .where(EngagementCandidate.id == candidate_id)
        .limit(1)
    )


async def _find_candidate_engagement(
    db: AsyncSession,
    candidate: EngagementCandidate,
) -> Engagement | None:
    return await db.scalar(
        select(Engagement)
        .where(
            Engagement.community_id == candidate.community_id,
            Engagement.topic_id == candidate.topic_id,
            Engagement.status.in_([EngagementStatus.ACTIVE.value, EngagementStatus.PAUSED.value]),
        )
        .limit(1)
    )


async def _get_engagement_settings(
    db: AsyncSession,
    *,
    engagement_id: UUID,
) -> EngagementSettings | None:
    return await db.scalar(
        select(EngagementSettings).where(EngagementSettings.engagement_id == engagement_id).limit(1)
    )


def _draft_action_error(
    exc: EngagementServiceError,
    *,
    stale_message: str,
    blocked_message: str,
) -> CockpitDraftActionResult:
    if isinstance(exc, (EngagementNotFound,)):
        return CockpitDraftActionResult(result="stale", message=stale_message)
    if isinstance(exc, EngagementConflict):
        return CockpitDraftActionResult(result="blocked", message=blocked_message, code=exc.code)
    if isinstance(exc, EngagementValidationError):
        return CockpitDraftActionResult(result="blocked", message=blocked_message, code=exc.code)
    return CockpitDraftActionResult(result="blocked", message=blocked_message)


def _issue_action_error(
    exc: EngagementServiceError,
    *,
    stale_message: str,
    blocked_message: str,
) -> CockpitIssueActionResult:
    if isinstance(exc, (EngagementNotFound,)):
        return CockpitIssueActionResult(result="stale", message=stale_message, next_callback="eng:iss:list:0")
    if isinstance(exc, EngagementConflict):
        return CockpitIssueActionResult(result="blocked", message=blocked_message, code=exc.code)
    if isinstance(exc, EngagementValidationError):
        return CockpitIssueActionResult(result="blocked", message=blocked_message, code=exc.code)
    return CockpitIssueActionResult(result="blocked", message=blocked_message)


__all__ = [
    "CockpitDraftActionResult",
    "CockpitIssueActionResult",
    "CockpitQuietHoursReadResult",
    "CockpitQuietHoursWriteResult",
    "CockpitRateLimitDetailResult",
    "act_on_cockpit_issue",
    "approve_cockpit_draft",
    "get_cockpit_quiet_hours",
    "get_cockpit_rate_limit_detail",
    "queue_cockpit_draft_update",
    "reject_cockpit_draft",
    "update_cockpit_quiet_hours",
]
