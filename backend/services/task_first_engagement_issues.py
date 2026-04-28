from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    AccountPool,
    AccountStatus,
    CommunityAccountMembershipStatus,
    EngagementActionStatus,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStatus,
    EngagementTargetStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    Engagement,
    EngagementAction,
    EngagementCandidate,
    EngagementSettings,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)
from backend.workers.engagement_scheduler import is_quiet_time
from backend.workers.engagement_send import check_send_limits

_ISSUE_NAMESPACE = uuid.UUID("a507f1ca-3445-4267-a9f0-6e84ed8bd43f")
_ENABLED_ENGAGEMENT_STATUSES = {EngagementStatus.ACTIVE.value, EngagementStatus.PAUSED.value}
_APPROVAL_MODES = {
    EngagementMode.SUGGEST.value,
    EngagementMode.REQUIRE_APPROVAL.value,
}
_WIZARD_ACTION_KEYS = {"chtopic", "crtopic", "chacct", "swapacct"}

ISSUE_LABELS = {
    "topics_not_chosen": "Topics not chosen",
    "account_not_connected": "Account not connected",
    "account_connecting": "Account connecting",
    "sending_is_paused": "Sending is paused",
    "reply_expired": "Reply expired",
    "reply_failed": "Reply failed",
    "target_not_approved": "Target not approved",
    "target_not_resolved": "Target not resolved",
    "community_permissions_missing": "Community permissions missing",
    "rate_limit_active": "Rate limit active",
    "quiet_hours_active": "Quiet hours active",
    "account_restricted": "Account restricted",
}


@dataclass(frozen=True)
class TaskFirstIssueAction:
    action_key: str
    label: str
    callback_family: str


@dataclass(frozen=True)
class TaskFirstIssueRecord:
    issue_id: UUID
    engagement_id: UUID
    issue_type: str
    issue_label: str
    created_at: datetime
    target_label: str
    context: str | None
    fix_actions: list[TaskFirstIssueAction]
    candidate_id: UUID | None = None
    target_id: UUID | None = None
    community_id: UUID | None = None
    assigned_account_id: UUID | None = None
    blocked_action_label: str | None = None
    scope_label: str | None = None
    message: str | None = None
    reset_at: datetime | None = None


@dataclass
class _IssueData:
    engagements: list[Engagement] = field(default_factory=list)
    settings_by_engagement_id: dict[UUID, EngagementSettings] = field(default_factory=dict)
    targets_by_id: dict[UUID, EngagementTarget] = field(default_factory=dict)
    topics_by_id: dict[UUID, EngagementTopic] = field(default_factory=dict)
    accounts_by_id: dict[UUID, TelegramAccount] = field(default_factory=dict)
    memberships_by_key: dict[tuple[UUID, UUID], CommunityAccountMembership] = field(default_factory=dict)
    communities_by_id: dict[UUID, Community] = field(default_factory=dict)
    candidates_by_key: dict[tuple[UUID, UUID | None], list[EngagementCandidate]] = field(default_factory=dict)
    sent_actions: list[EngagementAction] = field(default_factory=list)


async def list_task_first_issues(
    db: AsyncSession,
    *,
    engagement_id: UUID | None = None,
    now: datetime | None = None,
) -> list[TaskFirstIssueRecord]:
    data = await _load_issue_data(db)
    current_time = _ensure_aware_utc(now or datetime.now(timezone.utc))
    records: list[TaskFirstIssueRecord] = []

    for engagement in _visible_engagements(data.engagements):
        if engagement_id is not None and engagement.id != engagement_id:
            continue
        records.extend(await _engagement_issues(data, engagement=engagement, now=current_time, db=db))

    records.sort(key=lambda record: record.created_at, reverse=True)
    return records


async def get_task_first_issue(
    db: AsyncSession,
    *,
    issue_id: UUID,
    now: datetime | None = None,
) -> TaskFirstIssueRecord | None:
    for issue in await list_task_first_issues(db, now=now):
        if issue.issue_id == issue_id:
            return issue
    return None


async def _load_issue_data(db: AsyncSession) -> _IssueData:
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
    candidates = list(
        await db.scalars(
            select(EngagementCandidate)
            .options(
                joinedload(EngagementCandidate.community),
                joinedload(EngagementCandidate.topic),
            )
            .where(
                EngagementCandidate.status.in_(
                    [
                        EngagementCandidateStatus.APPROVED.value,
                        EngagementCandidateStatus.EXPIRED.value,
                        EngagementCandidateStatus.FAILED.value,
                    ]
                )
            )
            .order_by(EngagementCandidate.created_at.desc())
        )
    )
    sent_actions = list(
        await db.scalars(
            select(EngagementAction)
            .options(joinedload(EngagementAction.community))
            .where(EngagementAction.status == EngagementActionStatus.SENT.value)
            .order_by(EngagementAction.sent_at.desc(), EngagementAction.created_at.desc())
        )
    )

    candidates_by_key: dict[tuple[UUID, UUID | None], list[EngagementCandidate]] = {}
    for candidate in candidates:
        candidates_by_key.setdefault((candidate.community_id, candidate.topic_id), []).append(candidate)
    for rows in candidates_by_key.values():
        rows.sort(key=lambda row: row.created_at, reverse=True)

    communities = {
        community.id: community
        for community in _iter_communities(
            engagements=engagements,
            targets=targets,
            candidates=candidates,
            actions=sent_actions,
        )
    }
    return _IssueData(
        engagements=engagements,
        settings_by_engagement_id={setting.engagement_id: setting for setting in settings},
        targets_by_id={target.id: target for target in targets},
        topics_by_id={topic.id: topic for topic in topics},
        accounts_by_id={account.id: account for account in accounts},
        memberships_by_key={
            (membership.community_id, membership.telegram_account_id): membership
            for membership in memberships
        },
        communities_by_id=communities,
        candidates_by_key=candidates_by_key,
        sent_actions=sent_actions,
    )


async def _engagement_issues(
    data: _IssueData,
    *,
    engagement: Engagement,
    now: datetime,
    db: AsyncSession,
) -> list[TaskFirstIssueRecord]:
    target = data.targets_by_id.get(engagement.target_id) or getattr(engagement, "target", None)
    settings = data.settings_by_engagement_id.get(engagement.id) or getattr(engagement, "settings", None)
    account = (
        data.accounts_by_id.get(settings.assigned_account_id)
        if settings is not None and settings.assigned_account_id is not None
        else None
    )
    membership = (
        data.memberships_by_key.get((engagement.community_id, settings.assigned_account_id))
        if settings is not None and settings.assigned_account_id is not None
        else None
    )
    scoped_candidates = data.candidates_by_key.get((engagement.community_id, engagement.topic_id), [])
    target_label = _engagement_target_label(engagement, data)
    records: list[TaskFirstIssueRecord] = []

    if target is None or target.community_id is None or target.status in {
        EngagementTargetStatus.PENDING.value,
        EngagementTargetStatus.FAILED.value,
    }:
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="target_not_resolved",
                created_at=_timestamp(target, engagement),
                target_label=target_label,
                context="Target still needs resolution",
                fix_actions=[_issue_action("rsvtgt", "Resolve target")],
                target_id=None if target is None else target.id,
                community_id=engagement.community_id,
            )
        )
    elif target.status != EngagementTargetStatus.APPROVED.value:
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="target_not_approved",
                created_at=_timestamp(target, engagement),
                target_label=target_label,
                context="Target approval is still required",
                fix_actions=[_issue_action("apptgt", "Approve target")],
                target_id=target.id,
                community_id=engagement.community_id,
            )
        )

    if engagement.topic_id is None:
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="topics_not_chosen",
                created_at=_timestamp(engagement),
                target_label=target_label,
                context="Choose or create a topic",
                fix_actions=[
                    _issue_action("chtopic", "Choose topic"),
                    _issue_action("crtopic", "Create topic"),
                ],
                target_id=engagement.target_id,
                community_id=engagement.community_id,
            )
        )

    membership_joined = membership is not None and membership.status == CommunityAccountMembershipStatus.JOINED.value
    account_is_usable = (
        account is not None
        and account.account_pool == AccountPool.ENGAGEMENT.value
        and account.status not in {AccountStatus.BANNED.value}
    )
    membership_connecting = (
        membership is not None and membership.status == CommunityAccountMembershipStatus.JOIN_REQUESTED.value
    )
    if settings is None or settings.assigned_account_id is None or not membership_joined:
        issue_type = "account_connecting" if membership_connecting else "account_not_connected"
        context = (
            "The assigned engagement account is still joining this community"
            if membership_connecting
            else "Choose a joined engagement account"
        )
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type=issue_type,
                created_at=_timestamp(settings, membership, engagement),
                target_label=target_label,
                context=context,
                fix_actions=[_issue_action("chacct", "Choose account")],
                target_id=engagement.target_id,
                community_id=engagement.community_id,
                assigned_account_id=None if settings is None else settings.assigned_account_id,
            )
        )

    if account is not None and (
        account.account_pool != AccountPool.ENGAGEMENT.value
        or account.status == AccountStatus.BANNED.value
    ):
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="account_restricted",
                created_at=_timestamp(account, settings, engagement),
                target_label=target_label,
                context="The assigned account cannot be used right now",
                fix_actions=[_issue_action("swapacct", "Choose another account")],
                target_id=engagement.target_id,
                community_id=engagement.community_id,
                assigned_account_id=account.id,
            )
        )

    target_approved = target is not None and target.status == EngagementTargetStatus.APPROVED.value
    eligible_for_send_resume = (
        target_approved
        and engagement.topic_id is not None
        and settings is not None
        and settings.assigned_account_id is not None
        and membership_joined
        and account_is_usable
    )
    if eligible_for_send_resume and (
        engagement.status == EngagementStatus.PAUSED.value
        or settings.mode == EngagementMode.DISABLED.value
    ):
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="sending_is_paused",
                created_at=_timestamp(engagement, settings),
                target_label=target_label,
                context="Resume sending for this engagement",
                fix_actions=[_issue_action("resume", "Resume sending")],
                target_id=engagement.target_id,
                community_id=engagement.community_id,
                assigned_account_id=settings.assigned_account_id,
            )
        )

    if eligible_for_send_resume and settings is not None and target is not None:
        permissions_missing = (
            not target.allow_detect
            or not settings.allow_join
            or (
                settings.mode == EngagementMode.AUTO_LIMITED.value
                and (not settings.allow_post or not target.allow_post)
            )
        )
        if permissions_missing:
            records.append(
                _issue_record(
                    engagement_id=engagement.id,
                    issue_type="community_permissions_missing",
                    created_at=_timestamp(target, settings, engagement),
                    target_label=target_label,
                    context="Permission settings do not match the current mode",
                    fix_actions=[_issue_action("fixperm", "Fix permissions")],
                    target_id=engagement.target_id,
                    community_id=engagement.community_id,
                    assigned_account_id=settings.assigned_account_id,
                )
            )

    latest_expired = _latest_candidate_with_status(scoped_candidates, EngagementCandidateStatus.EXPIRED.value)
    if latest_expired is not None:
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="reply_expired",
                created_at=_timestamp(latest_expired),
                target_label=target_label,
                context="A reply opportunity expired before review",
                fix_actions=[],
                candidate_id=latest_expired.id,
                target_id=engagement.target_id,
                community_id=engagement.community_id,
                assigned_account_id=None if settings is None else settings.assigned_account_id,
            )
        )

    latest_failed = _latest_candidate_with_status(scoped_candidates, EngagementCandidateStatus.FAILED.value)
    if latest_failed is not None:
        records.append(
            _issue_record(
                engagement_id=engagement.id,
                issue_type="reply_failed",
                created_at=_timestamp(latest_failed),
                target_label=target_label,
                context="Retry the failed reply opportunity",
                fix_actions=[_issue_action("retry", "Retry")],
                candidate_id=latest_failed.id,
                target_id=engagement.target_id,
                community_id=engagement.community_id,
                assigned_account_id=None if settings is None else settings.assigned_account_id,
            )
        )

    if eligible_for_send_resume and settings is not None and settings.mode == EngagementMode.AUTO_LIMITED.value:
        latest_approved = _latest_candidate_with_status(scoped_candidates, EngagementCandidateStatus.APPROVED.value)
        if latest_approved is not None and target is not None and target.allow_post and settings.allow_post:
            if is_quiet_time(
                now,
                quiet_hours_start=settings.quiet_hours_start,
                quiet_hours_end=settings.quiet_hours_end,
            ):
                records.append(
                    _issue_record(
                        engagement_id=engagement.id,
                        issue_type="quiet_hours_active",
                        created_at=_timestamp(settings, latest_approved, engagement),
                        target_label=target_label,
                        context="Quiet hours are blocking send right now",
                        fix_actions=[_issue_action("quiet", "Change quiet hours")],
                        candidate_id=latest_approved.id,
                        target_id=engagement.target_id,
                        community_id=engagement.community_id,
                        assigned_account_id=settings.assigned_account_id,
                    )
                )
            else:
                limit_issue = await _rate_limit_issue(
                    db,
                    engagement=engagement,
                    settings=settings,
                    account=account,
                    candidate=latest_approved,
                    target_label=target_label,
                    now=now,
                )
                if limit_issue is not None:
                    records.append(limit_issue)

    return records


async def _rate_limit_issue(
    db: AsyncSession,
    *,
    engagement: Engagement,
    settings: EngagementSettings,
    account: TelegramAccount | None,
    candidate: EngagementCandidate,
    target_label: str,
    now: datetime,
) -> TaskFirstIssueRecord | None:
    if settings.assigned_account_id is None:
        return None

    if account is not None and (
        account.status == AccountStatus.RATE_LIMITED.value
        or (
            getattr(account, "flood_wait_until", None) is not None
            and _ensure_aware_utc(account.flood_wait_until) > now
        )
    ):
        reset_at = getattr(account, "flood_wait_until", None)
        return _issue_record(
            engagement_id=engagement.id,
            issue_type="rate_limit_active",
            created_at=_timestamp(reset_at, account, candidate, settings, engagement),
            target_label=target_label,
            context="Sending is paused until the limit clears.",
            fix_actions=[_issue_action("ratelimit", "See rate limit")],
            candidate_id=candidate.id,
            target_id=engagement.target_id,
            community_id=engagement.community_id,
            assigned_account_id=settings.assigned_account_id,
            blocked_action_label="Send reply",
            scope_label="Account limit",
            message="Sending is paused until the limit clears.",
            reset_at=None if reset_at is None else _ensure_aware_utc(reset_at),
        )

    decision = await check_send_limits(
        db,
        community_id=engagement.community_id,
        telegram_account_id=settings.assigned_account_id,
        max_posts_per_day=settings.max_posts_per_day,
        min_minutes_between_posts=settings.min_minutes_between_posts,
        now=now,
    )
    if decision.allowed:
        return None

    scope_label = "Send limit"
    reason = decision.reason or "Sending is paused until the limit clears."
    lowered = reason.lower()
    if "community" in lowered:
        scope_label = "Community limit"
    elif "account" in lowered:
        scope_label = "Account limit"

    reset_at = _estimate_rate_limit_reset_at(
        sent_actions=[
            action
            for action in await db.scalars(
                select(EngagementAction)
                .where(
                    EngagementAction.status == EngagementActionStatus.SENT.value,
                    (
                        (EngagementAction.community_id == engagement.community_id)
                        | (EngagementAction.telegram_account_id == settings.assigned_account_id)
                    ),
                )
                .order_by(EngagementAction.sent_at.desc(), EngagementAction.created_at.desc())
            )
        ],
        community_id=engagement.community_id,
        telegram_account_id=settings.assigned_account_id,
        max_posts_per_day=settings.max_posts_per_day,
        min_minutes_between_posts=settings.min_minutes_between_posts,
    )
    return _issue_record(
        engagement_id=engagement.id,
        issue_type="rate_limit_active",
        created_at=_timestamp(candidate, settings, engagement),
        target_label=target_label,
        context="Sending is paused until the limit clears.",
        fix_actions=[_issue_action("ratelimit", "See rate limit")],
        candidate_id=candidate.id,
        target_id=engagement.target_id,
        community_id=engagement.community_id,
        assigned_account_id=settings.assigned_account_id,
        blocked_action_label="Send reply",
        scope_label=scope_label,
        message=reason,
        reset_at=reset_at,
    )


def _estimate_rate_limit_reset_at(
    *,
    sent_actions: Iterable[EngagementAction],
    community_id: UUID,
    telegram_account_id: UUID,
    max_posts_per_day: int,
    min_minutes_between_posts: int,
) -> datetime | None:
    times: list[datetime] = []
    community_sent: list[datetime] = []
    account_sent: list[datetime] = []
    for action in sent_actions:
        sent_at = _action_sent_at(action)
        if sent_at is None:
            continue
        if action.community_id == community_id:
            community_sent.append(sent_at)
        if action.telegram_account_id == telegram_account_id:
            account_sent.append(sent_at)

    if community_sent:
        times.append(max(community_sent) + _minutes(min_minutes_between_posts))
        if len(community_sent) >= max_posts_per_day > 0:
            times.append(sorted(community_sent, reverse=True)[max_posts_per_day - 1] + _hours(24))
    if account_sent:
        times.append(max(account_sent) + _minutes(min_minutes_between_posts))
        if len(account_sent) >= max_posts_per_day > 0:
            times.append(sorted(account_sent, reverse=True)[max_posts_per_day - 1] + _hours(24))
    return min(times) if times else None


def _hours(value: int):
    from datetime import timedelta

    return timedelta(hours=value)


def _minutes(value: int):
    from datetime import timedelta

    return timedelta(minutes=value)


def _visible_engagements(engagements: Iterable[Engagement]) -> list[Engagement]:
    return [engagement for engagement in engagements if engagement.status in _ENABLED_ENGAGEMENT_STATUSES]


def _issue_action(action_key: str, label: str) -> TaskFirstIssueAction:
    return TaskFirstIssueAction(
        action_key=action_key,
        label=label,
        callback_family="eng:wz" if action_key in _WIZARD_ACTION_KEYS else "eng:iss",
    )


def _issue_record(
    *,
    engagement_id: UUID,
    issue_type: str,
    created_at: datetime,
    target_label: str,
    context: str | None,
    fix_actions: list[TaskFirstIssueAction],
    candidate_id: UUID | None = None,
    target_id: UUID | None = None,
    community_id: UUID | None = None,
    assigned_account_id: UUID | None = None,
    blocked_action_label: str | None = None,
    scope_label: str | None = None,
    message: str | None = None,
    reset_at: datetime | None = None,
) -> TaskFirstIssueRecord:
    stamp = _ensure_aware_utc(created_at)
    identity_parts = [
        str(engagement_id),
        issue_type,
        "" if candidate_id is None else str(candidate_id),
        "" if target_id is None else str(target_id),
        "" if assigned_account_id is None else str(assigned_account_id),
        stamp.isoformat(),
    ]
    return TaskFirstIssueRecord(
        issue_id=uuid.uuid5(_ISSUE_NAMESPACE, "|".join(identity_parts)),
        engagement_id=engagement_id,
        issue_type=issue_type,
        issue_label=ISSUE_LABELS[issue_type],
        created_at=stamp,
        target_label=target_label,
        context=context,
        fix_actions=fix_actions,
        candidate_id=candidate_id,
        target_id=target_id,
        community_id=community_id,
        assigned_account_id=assigned_account_id,
        blocked_action_label=blocked_action_label,
        scope_label=scope_label,
        message=message,
        reset_at=None if reset_at is None else _ensure_aware_utc(reset_at),
    )


def _latest_candidate_with_status(
    candidates: Iterable[EngagementCandidate],
    status: str,
) -> EngagementCandidate | None:
    for candidate in candidates:
        if candidate.status == status:
            return candidate
    return None


def _engagement_primary_label(engagement: Engagement, data: _IssueData) -> str:
    if engagement.name:
        return engagement.name
    topic = (
        data.topics_by_id.get(engagement.topic_id)
        if engagement.topic_id is not None
        else getattr(engagement, "topic", None)
    )
    if topic is not None and topic.name:
        return topic.name
    community = _engagement_community(engagement, data)
    if community is not None and community.title:
        return community.title
    return str(engagement.id)


def _engagement_target_label(engagement: Engagement, data: _IssueData) -> str:
    community_label = _community_label(_engagement_community(engagement, data))
    primary_label = _engagement_primary_label(engagement, data)
    return community_label if primary_label == community_label else f"{primary_label} · {community_label}"


def _engagement_community(engagement: Engagement, data: _IssueData) -> Community | None:
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


def _action_sent_at(action: EngagementAction | None) -> datetime | None:
    if action is None:
        return None
    sent_at = action.sent_at or action.created_at
    return None if sent_at is None else _ensure_aware_utc(sent_at)


def _timestamp(*objects: object | None) -> datetime:
    for obj in objects:
        if obj is None:
            continue
        if isinstance(obj, datetime):
            return _ensure_aware_utc(obj)
        updated_at = getattr(obj, "updated_at", None)
        if updated_at is not None:
            return _ensure_aware_utc(updated_at)
        created_at = getattr(obj, "created_at", None)
        if created_at is not None:
            return _ensure_aware_utc(created_at)
    raise ValueError("timestamp source required")


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    "ISSUE_LABELS",
    "TaskFirstIssueAction",
    "TaskFirstIssueRecord",
    "get_task_first_issue",
    "list_task_first_issues",
]
