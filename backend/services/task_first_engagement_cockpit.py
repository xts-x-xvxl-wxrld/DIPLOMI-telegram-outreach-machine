from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    Engagement,
    EngagementAction,
    EngagementCandidate,
    EngagementDraftUpdateRequest,
    EngagementSettings,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)
from backend.services.task_first_engagement_issues import list_task_first_issues

_DEFAULT_PAGE_LIMIT = 20
_MAX_PAGE_LIMIT = 100


@dataclass(frozen=True)
class CockpitHomeDraftPreviewView:
    draft_id: UUID
    engagement_id: UUID
    text_preview: str
    target_label: str
    why: str
    updated: bool


@dataclass(frozen=True)
class CockpitHomeIssuePreviewView:
    issue_id: UUID
    engagement_id: UUID
    issue_type: str
    issue_label: str
    badge: str | None
    created_at: datetime


@dataclass(frozen=True)
class CockpitHomeView:
    state: str
    draft_count: int
    issue_count: int
    active_engagement_count: int
    has_sent_messages: bool
    next_draft_preview: CockpitHomeDraftPreviewView | None
    latest_issue_preview: CockpitHomeIssuePreviewView | None


@dataclass(frozen=True)
class CockpitApprovalPlaceholderView:
    slot: int
    label: str


@dataclass(frozen=True)
class CockpitApprovalItemView:
    draft_id: UUID
    engagement_id: UUID
    target_label: str
    text: str
    why: str
    badge: str | None


@dataclass(frozen=True)
class CockpitApprovalQueueView:
    queue_count: int
    updating_count: int
    offset: int
    empty_state: str
    placeholders: list[CockpitApprovalPlaceholderView]
    current: CockpitApprovalItemView | None


@dataclass(frozen=True)
class CockpitIssueActionView:
    action_key: str
    label: str
    callback_family: str


@dataclass(frozen=True)
class CockpitIssueItemView:
    issue_id: UUID
    engagement_id: UUID
    issue_type: str
    issue_label: str
    badge: str | None
    created_at: datetime
    target_label: str
    context: str | None
    fix_actions: list[CockpitIssueActionView]
    candidate_id: UUID | None = None
    target_id: UUID | None = None
    community_id: UUID | None = None
    assigned_account_id: UUID | None = None


@dataclass(frozen=True)
class CockpitIssueQueueView:
    queue_count: int
    offset: int
    empty_state: str
    current: CockpitIssueItemView | None


@dataclass(frozen=True)
class CockpitPendingTaskView:
    task_kind: str
    label: str
    count: int
    resume_callback: str | None = None


@dataclass(frozen=True)
class CockpitEngagementListItemView:
    engagement_id: UUID
    primary_label: str
    community_label: str
    sending_mode_label: str
    issue_count: int
    pending_task: CockpitPendingTaskView | None
    created_at: datetime


@dataclass(frozen=True)
class CockpitEngagementListView:
    items: list[CockpitEngagementListItemView]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class CockpitEngagementDetailView:
    engagement_id: UUID
    target_label: str
    topic_label: str | None
    account_label: str | None
    sending_mode_label: str
    approval_count: int
    issue_count: int
    pending_task: CockpitPendingTaskView | None


@dataclass(frozen=True)
class CockpitSentItemView:
    action_id: UUID
    message_text: str
    community_label: str
    sent_at: datetime


@dataclass(frozen=True)
class CockpitSentFeedView:
    items: list[CockpitSentItemView]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class _ApprovalRecord:
    candidate: EngagementCandidate
    engagement: Engagement
    badge: str | None = None


@dataclass
class _CockpitData:
    engagements: list[Engagement] = field(default_factory=list)
    settings_by_engagement_id: dict[UUID, EngagementSettings] = field(default_factory=dict)
    targets_by_id: dict[UUID, EngagementTarget] = field(default_factory=dict)
    topics_by_id: dict[UUID, EngagementTopic] = field(default_factory=dict)
    accounts_by_id: dict[UUID, TelegramAccount] = field(default_factory=dict)
    memberships_by_key: dict[tuple[UUID, UUID], CommunityAccountMembership] = field(default_factory=dict)
    candidates: list[EngagementCandidate] = field(default_factory=list)
    draft_update_requests: list[EngagementDraftUpdateRequest] = field(default_factory=list)
    sent_actions: list[EngagementAction] = field(default_factory=list)
    communities_by_id: dict[UUID, Community] = field(default_factory=dict)


async def get_cockpit_home(db: AsyncSession) -> CockpitHomeView:
    data = await _load_cockpit_data(db)
    approvals = _approval_records(data)
    issues = await list_task_first_issues(db)
    finished_engagements = _visible_engagements(data.engagements)

    if not finished_engagements:
        state = "first_run"
    elif approvals:
        state = "approvals"
    elif issues:
        state = "issues"
    else:
        state = "clear"

    next_draft_preview = None
    if approvals:
        current = approvals[0]
        next_draft_preview = CockpitHomeDraftPreviewView(
            draft_id=current.candidate.id,
            engagement_id=current.engagement.id,
            text_preview=_trim_text(_draft_text(current.candidate), 160),
            target_label=_engagement_target_label(current.engagement, data),
            why=_candidate_why(current.candidate),
            updated=bool(current.badge),
        )

    latest_issue_preview = None
    if issues:
        issue = issues[0]
        latest_issue_preview = CockpitHomeIssuePreviewView(
            issue_id=issue.issue_id,
            engagement_id=issue.engagement_id,
            issue_type=issue.issue_type,
            issue_label=issue.issue_label,
            badge=None,
            created_at=issue.created_at,
        )

    return CockpitHomeView(
        state=state,
        draft_count=len(approvals),
        issue_count=len(issues),
        active_engagement_count=len(finished_engagements),
        has_sent_messages=bool(data.sent_actions),
        next_draft_preview=next_draft_preview,
        latest_issue_preview=latest_issue_preview,
    )


async def get_cockpit_approvals(
    db: AsyncSession,
    *,
    engagement_id: UUID | None = None,
    offset: int = 0,
    draft_id: UUID | None = None,
) -> CockpitApprovalQueueView:
    data = await _load_cockpit_data(db)
    approvals = _approval_records(data, engagement_id=engagement_id)
    placeholders = _approval_update_placeholders(data, engagement_id=engagement_id)

    empty_state = "none"
    current = None
    current_offset = 0
    if approvals:
        current_offset = _selected_offset(
            items=approvals,
            offset=offset,
            selected_id=draft_id,
            id_getter=lambda record: record.candidate.id,
        )
        first = approvals[current_offset]
        current = CockpitApprovalItemView(
            draft_id=first.candidate.id,
            engagement_id=first.engagement.id,
            target_label=_engagement_target_label(first.engagement, data),
            text=_draft_text(first.candidate),
            why=_candidate_why(first.candidate),
            badge=first.badge,
        )
    elif placeholders:
        empty_state = "waiting_for_updates"
    else:
        empty_state = "no_drafts"

    return CockpitApprovalQueueView(
        queue_count=len(approvals),
        updating_count=len(placeholders),
        offset=current_offset,
        empty_state=empty_state,
        placeholders=placeholders,
        current=current,
    )


async def get_cockpit_issues(
    db: AsyncSession,
    *,
    engagement_id: UUID | None = None,
    offset: int = 0,
    issue_id: UUID | None = None,
) -> CockpitIssueQueueView:
    issues = await list_task_first_issues(db, engagement_id=engagement_id)
    current = None
    current_offset = 0
    if issues:
        current_offset = _selected_offset(
            items=issues,
            offset=offset,
            selected_id=issue_id,
            id_getter=lambda record: record.issue_id,
        )
        issue = issues[current_offset]
        current = CockpitIssueItemView(
            issue_id=issue.issue_id,
            engagement_id=issue.engagement_id,
            issue_type=issue.issue_type,
            issue_label=issue.issue_label,
            badge=None,
            created_at=issue.created_at,
            target_label=issue.target_label,
            context=issue.context,
            fix_actions=[
                CockpitIssueActionView(
                    action_key=action.action_key,
                    label=action.label,
                    callback_family=action.callback_family,
                )
                for action in issue.fix_actions
            ],
            candidate_id=issue.candidate_id,
            target_id=issue.target_id,
            community_id=issue.community_id,
            assigned_account_id=issue.assigned_account_id,
        )

    return CockpitIssueQueueView(
        queue_count=len(issues),
        offset=current_offset,
        empty_state="none" if current is not None else "no_issues",
        current=current,
    )


async def list_cockpit_engagements(
    db: AsyncSession,
    *,
    limit: int = _DEFAULT_PAGE_LIMIT,
    offset: int = 0,
) -> CockpitEngagementListView:
    data = await _load_cockpit_data(db)
    issue_counts = _issue_counts_by_engagement(await list_task_first_issues(db))
    items = [
        CockpitEngagementListItemView(
            engagement_id=engagement.id,
            primary_label=_engagement_primary_label(engagement, data),
            community_label=_community_label(_engagement_community(engagement, data)),
            sending_mode_label=_sending_mode_label(engagement, data),
            issue_count=issue_counts.get(engagement.id, 0),
            pending_task=_pending_task_for_engagement(
                engagement.id,
                data,
                include_resume_callback=False,
                issue_count=issue_counts.get(engagement.id, 0),
            ),
            created_at=engagement.created_at,
        )
        for engagement in _visible_engagements(data.engagements)
    ]
    items.sort(key=lambda item: item.created_at, reverse=True)
    safe_limit, safe_offset = _page_window(total=len(items), limit=limit, offset=offset)
    return CockpitEngagementListView(
        items=items[safe_offset : safe_offset + safe_limit],
        total=len(items),
        offset=safe_offset,
        limit=safe_limit,
    )


async def get_cockpit_engagement_detail(
    db: AsyncSession,
    *,
    engagement_id: UUID,
) -> CockpitEngagementDetailView | None:
    data = await _load_cockpit_data(db)
    engagement = _engagement_by_id(data.engagements, engagement_id)
    if engagement is None:
        return None
    issues = await list_task_first_issues(db, engagement_id=engagement_id)

    settings = data.settings_by_engagement_id.get(engagement.id) or getattr(engagement, "settings", None)
    topic = data.topics_by_id.get(engagement.topic_id) if engagement.topic_id is not None else None
    account = (
        data.accounts_by_id.get(settings.assigned_account_id)
        if settings is not None and settings.assigned_account_id is not None
        else None
    )

    return CockpitEngagementDetailView(
        engagement_id=engagement.id,
        target_label=_community_label(_engagement_community(engagement, data)),
        topic_label=None if topic is None else topic.name,
        account_label=None if account is None else account.phone,
        sending_mode_label=_sending_mode_label(engagement, data),
        approval_count=len(_approval_records(data, engagement_id=engagement.id)),
        issue_count=len(issues),
        pending_task=_pending_task_for_engagement(
            engagement.id,
            data,
            include_resume_callback=True,
            issue_count=len(issues),
        ),
    )


async def list_cockpit_sent(
    db: AsyncSession,
    *,
    limit: int = _DEFAULT_PAGE_LIMIT,
    offset: int = 0,
) -> CockpitSentFeedView:
    data = await _load_cockpit_data(db)
    items = [
        CockpitSentItemView(
            action_id=action.id,
            message_text=action.outbound_text or _sent_fallback_text(action),
            community_label=_community_label(_sent_action_community(action, data)),
            sent_at=action.sent_at or action.created_at,
        )
        for action in data.sent_actions
    ]
    items.sort(key=lambda item: item.sent_at, reverse=True)
    safe_limit, safe_offset = _page_window(total=len(items), limit=limit, offset=offset)
    return CockpitSentFeedView(
        items=items[safe_offset : safe_offset + safe_limit],
        total=len(items),
        offset=safe_offset,
        limit=safe_limit,
    )


async def _load_cockpit_data(db: AsyncSession) -> _CockpitData:
    engagements = list(
        await db.scalars(
            select(Engagement)
            .options(
                joinedload(Engagement.community),
                joinedload(Engagement.target).joinedload(EngagementTarget.community),
                joinedload(Engagement.topic),
                joinedload(Engagement.settings),
            )
            .order_by(Engagement.created_at.desc())
        )
    )
    settings = list(await db.scalars(select(EngagementSettings)))
    targets = list(await db.scalars(select(EngagementTarget).options(joinedload(EngagementTarget.community))))
    topics = list(await db.scalars(select(EngagementTopic)))
    accounts = list(await db.scalars(select(TelegramAccount)))
    memberships = list(await db.scalars(select(CommunityAccountMembership)))
    draft_update_requests = list(await db.scalars(select(EngagementDraftUpdateRequest)))
    candidates = list(
        await db.scalars(
            select(EngagementCandidate)
            .options(joinedload(EngagementCandidate.topic))
            .where(EngagementCandidate.status == EngagementCandidateStatus.NEEDS_REVIEW.value)
            .order_by(EngagementCandidate.created_at.desc())
        )
    )
    sent_actions = [
        action
        for action in await db.scalars(
            select(EngagementAction)
            .options(
                joinedload(EngagementAction.community),
                joinedload(EngagementAction.candidate).joinedload(EngagementCandidate.community),
            )
            .where(EngagementAction.status == EngagementActionStatus.SENT.value)
            .where(EngagementAction.action_type == EngagementActionType.REPLY.value)
            .order_by(EngagementAction.sent_at.desc(), EngagementAction.created_at.desc())
        )
        if action.action_type == EngagementActionType.REPLY.value
        and (action.sent_at is not None or action.outbound_text)
    ]
    communities = {
        community.id: community
        for community in _iter_communities(
            engagements=engagements,
            targets=targets,
            candidates=candidates,
            actions=sent_actions,
        )
    }
    return _CockpitData(
        engagements=engagements,
        settings_by_engagement_id={setting.engagement_id: setting for setting in settings},
        targets_by_id={target.id: target for target in targets},
        topics_by_id={topic.id: topic for topic in topics},
        accounts_by_id={account.id: account for account in accounts},
        memberships_by_key={
            (membership.community_id, membership.telegram_account_id): membership
            for membership in memberships
        },
        candidates=candidates,
        draft_update_requests=draft_update_requests,
        sent_actions=sent_actions,
        communities_by_id=communities,
    )


def _visible_engagements(engagements: Iterable[Engagement]) -> list[Engagement]:
    return [
        engagement
        for engagement in engagements
        if engagement.status in {EngagementStatus.ACTIVE.value, EngagementStatus.PAUSED.value}
    ]


def _approval_records(data: _CockpitData, *, engagement_id: UUID | None = None) -> list[_ApprovalRecord]:
    engagements_by_key = {
        (eng.community_id, eng.topic_id): eng
        for eng in _visible_engagements(data.engagements)
        if eng.topic_id is not None and (engagement_id is None or eng.id == engagement_id)
    }
    hidden_source_candidate_ids = {
        request.source_candidate_id
        for request in data.draft_update_requests
    }
    updated_candidate_ids = {
        request.replacement_candidate_id
        for request in data.draft_update_requests
        if request.status == "completed" and request.replacement_candidate_id is not None
    }
    approvals: list[_ApprovalRecord] = []
    for candidate in data.candidates:
        if candidate.status != EngagementCandidateStatus.NEEDS_REVIEW.value:
            continue
        if candidate.id in hidden_source_candidate_ids:
            continue
        engagement = engagements_by_key.get((candidate.community_id, candidate.topic_id))
        if engagement is None:
            continue
        approvals.append(
            _ApprovalRecord(
                candidate=candidate,
                engagement=engagement,
                badge="Updated draft" if candidate.id in updated_candidate_ids else None,
            )
        )
    approvals.sort(key=lambda record: record.candidate.created_at, reverse=True)
    return approvals


def _pending_task_for_engagement(
    engagement_id: UUID,
    data: _CockpitData,
    *,
    include_resume_callback: bool,
    issue_count: int,
) -> CockpitPendingTaskView | None:
    approval_count = len(_approval_records(data, engagement_id=engagement_id))
    approval_update_count = len(_approval_update_placeholders(data, engagement_id=engagement_id))

    if approval_count > 0:
        return CockpitPendingTaskView(
            task_kind="approvals",
            label="Approve draft",
            count=approval_count,
            resume_callback=f"eng:appr:eng:{engagement_id}" if include_resume_callback else None,
        )
    if approval_update_count > 0:
        return CockpitPendingTaskView(
            task_kind="approval_updates",
            label="Approve draft",
            count=approval_update_count,
            resume_callback=f"eng:appr:eng:{engagement_id}" if include_resume_callback else None,
        )
    if issue_count > 0:
        return CockpitPendingTaskView(
            task_kind="issues",
            label="Top issues",
            count=issue_count,
            resume_callback=f"eng:iss:eng:{engagement_id}" if include_resume_callback else None,
        )
    return None


def _issue_counts_by_engagement(issues) -> dict[UUID, int]:
    counts: dict[UUID, int] = {}
    for issue in issues:
        counts[issue.engagement_id] = counts.get(issue.engagement_id, 0) + 1
    return counts


def _engagement_by_id(engagements: Iterable[Engagement], engagement_id: UUID) -> Engagement | None:
    for engagement in engagements:
        if engagement.id == engagement_id:
            return engagement
    return None


def _engagement_primary_label(engagement: Engagement, data: _CockpitData) -> str:
    if engagement.name:
        return engagement.name
    topic = data.topics_by_id.get(engagement.topic_id) if engagement.topic_id is not None else getattr(engagement, "topic", None)
    if topic is not None and topic.name:
        return topic.name
    community = _engagement_community(engagement, data)
    if community is not None and community.title:
        return community.title
    return str(engagement.id)


def _engagement_target_label(engagement: Engagement, data: _CockpitData) -> str:
    community_label = _community_label(_engagement_community(engagement, data))
    primary_label = _engagement_primary_label(engagement, data)
    return community_label if primary_label == community_label else f"{primary_label} · {community_label}"


def _engagement_community(engagement: Engagement, data: _CockpitData) -> Community | None:
    return (
        getattr(engagement, "community", None)
        or data.communities_by_id.get(engagement.community_id)
        or getattr(data.targets_by_id.get(engagement.target_id), "community", None)
    )


def _community_label(community: Community | None) -> str:
    if community is None:
        return "Unknown community"
    if community.username:
        return f"@{community.username}"
    if community.title:
        return community.title
    return str(community.id)


def _sending_mode_label(engagement: Engagement, data: _CockpitData) -> str:
    settings = data.settings_by_engagement_id.get(engagement.id) or getattr(engagement, "settings", None)
    mode = None if settings is None else settings.mode
    if mode == EngagementMode.AUTO_LIMITED.value:
        return "Auto send"
    if mode in {EngagementMode.SUGGEST.value, EngagementMode.REQUIRE_APPROVAL.value}:
        return "Draft"
    return "Disabled"


def _draft_text(candidate: EngagementCandidate) -> str:
    return candidate.final_reply or candidate.suggested_reply or ""


def _candidate_why(candidate: EngagementCandidate) -> str:
    if candidate.detected_reason:
        return _trim_text(candidate.detected_reason, 160)
    if getattr(candidate, "topic", None) is not None:
        return f"Matched topic: {candidate.topic.name}"
    return "Matched engagement topic"


def _approval_update_placeholders(
    data: _CockpitData,
    *,
    engagement_id: UUID | None = None,
) -> list[CockpitApprovalPlaceholderView]:
    requests = [
        request
        for request in data.draft_update_requests
        if request.status == "pending" and (engagement_id is None or request.engagement_id == engagement_id)
    ]
    requests.sort(key=lambda request: request.source_queue_created_at, reverse=True)
    return [
        CockpitApprovalPlaceholderView(slot=index, label="Updating draft")
        for index, request in enumerate(requests)
    ]


def _page_window(*, total: int, limit: int, offset: int) -> tuple[int, int]:
    safe_limit = max(1, min(int(limit), _MAX_PAGE_LIMIT))
    safe_limit = _DEFAULT_PAGE_LIMIT if safe_limit <= 0 else safe_limit
    safe_offset = max(int(offset), 0)
    if total == 0:
        return safe_limit, 0
    if safe_offset >= total:
        safe_offset = ((total - 1) // safe_limit) * safe_limit
    return safe_limit, safe_offset


def _selected_offset(
    *,
    items: list[object],
    offset: int,
    selected_id: UUID | None,
    id_getter,
) -> int:
    if not items:
        return 0
    if selected_id is not None:
        for index, item in enumerate(items):
            if id_getter(item) == selected_id:
                return index
    return max(0, min(int(offset), len(items) - 1))


def _sent_action_community(action: EngagementAction, data: _CockpitData) -> Community | None:
    return getattr(action, "community", None) or data.communities_by_id.get(action.community_id)


def _sent_fallback_text(action: EngagementAction) -> str:
    candidate = getattr(action, "candidate", None)
    if candidate is not None:
        return _draft_text(candidate)
    return ""


def _trim_text(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(limit - 1, 1)].rstrip() + "…"


def _iter_communities(
    *,
    engagements: Iterable[Engagement],
    targets: Iterable[EngagementTarget],
    candidates: Iterable[EngagementCandidate],
    actions: Iterable[EngagementAction],
) -> Iterable[Community]:
    for engagement in engagements:
        community = getattr(engagement, "community", None)
        if community is not None:
            yield community
        target = getattr(engagement, "target", None)
        if target is not None and getattr(target, "community", None) is not None:
            yield target.community
    for target in targets:
        community = getattr(target, "community", None)
        if community is not None:
            yield community
    for candidate in candidates:
        community = getattr(candidate, "community", None)
        if community is not None:
            yield community
    for action in actions:
        community = getattr(action, "community", None)
        if community is not None:
            yield community


__all__ = [
    "CockpitApprovalItemView",
    "CockpitApprovalPlaceholderView",
    "CockpitApprovalQueueView",
    "CockpitEngagementDetailView",
    "CockpitEngagementListItemView",
    "CockpitEngagementListView",
    "CockpitHomeDraftPreviewView",
    "CockpitHomeIssuePreviewView",
    "CockpitHomeView",
    "CockpitIssueActionView",
    "CockpitIssueItemView",
    "CockpitIssueQueueView",
    "CockpitPendingTaskView",
    "CockpitSentFeedView",
    "CockpitSentItemView",
    "get_cockpit_approvals",
    "get_cockpit_engagement_detail",
    "get_cockpit_home",
    "get_cockpit_issues",
    "list_cockpit_engagements",
    "list_cockpit_sent",
]
