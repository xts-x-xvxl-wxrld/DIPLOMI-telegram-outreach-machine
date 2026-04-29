from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    AccountPool,
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementMode,
    EngagementStatus,
    EngagementTargetStatus,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    Engagement,
    EngagementSettings,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)
from backend.queue.client import enqueue_community_join

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskFirstEngagementView:
    id: UUID
    target_id: UUID
    community_id: UUID
    topic_id: UUID | None
    status: str
    name: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TaskFirstEngagementSettingsView:
    engagement_id: UUID
    assigned_account_id: UUID | None
    mode: str
    quiet_hours_start: time | None
    quiet_hours_end: time | None


@dataclass(frozen=True)
class TaskFirstEngagementCreateResult:
    result: str
    engagement: TaskFirstEngagementView


@dataclass(frozen=True)
class TaskFirstEngagementPatchResult:
    result: str
    engagement: TaskFirstEngagementView | None = None
    message: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class TaskFirstEngagementSettingsResult:
    result: str
    settings: TaskFirstEngagementSettingsView | None = None
    message: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class TaskFirstWizardConfirmResult:
    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    engagement_status: str | None = None
    target_status: str | None = None
    field: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class TaskFirstWizardRetryResult:
    result: str
    message: str
    next_callback: str
    engagement_id: UUID | None = None
    code: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _detail_callback(engagement_id: UUID) -> str:
    return f"eng:det:open:{engagement_id}"


def _wizard_edit_callback(engagement_id: UUID, field: str) -> str:
    return f"eng:wz:edit:{engagement_id}:{field}"


def _engagement_view(engagement: Engagement) -> TaskFirstEngagementView:
    return TaskFirstEngagementView(
        id=engagement.id,
        target_id=engagement.target_id,
        community_id=engagement.community_id,
        topic_id=engagement.topic_id,
        status=engagement.status,
        name=engagement.name,
        created_by=engagement.created_by,
        created_at=engagement.created_at,
        updated_at=engagement.updated_at,
    )


def _settings_view(settings: EngagementSettings) -> TaskFirstEngagementSettingsView:
    return TaskFirstEngagementSettingsView(
        engagement_id=settings.engagement_id,
        assigned_account_id=settings.assigned_account_id,
        mode=settings.mode,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
    )


async def _load_task_first_community(
    db: AsyncSession,
    *,
    community_id: UUID,
) -> Community | None:
    return await db.get(Community, community_id)


def _promote_task_first_community_for_engagement(
    community: Community,
    *,
    reviewed_at: datetime,
) -> None:
    if community.status in {
        CommunityStatus.APPROVED.value,
        CommunityStatus.MONITORING.value,
    }:
        return
    community.status = CommunityStatus.APPROVED.value
    community.reviewed_at = reviewed_at


async def _get_settings(db: AsyncSession, *, engagement_id: UUID) -> EngagementSettings | None:
    return await db.scalar(
        select(EngagementSettings).where(EngagementSettings.engagement_id == engagement_id)
    )


async def _get_membership(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership | None:
    return await db.scalar(
        select(CommunityAccountMembership).where(
            CommunityAccountMembership.community_id == community_id,
            CommunityAccountMembership.telegram_account_id == telegram_account_id,
        )
    )


async def create_task_first_engagement(
    db: AsyncSession,
    *,
    target_id: UUID,
    created_by: str,
) -> TaskFirstEngagementCreateResult:
    target = await db.get(EngagementTarget, target_id)
    if target is None:
        raise ValueError("target_not_found")
    if target.community_id is None or target.status not in {
        EngagementTargetStatus.RESOLVED.value,
        EngagementTargetStatus.APPROVED.value,
    }:
        raise RuntimeError("target_not_resolved")

    existing = await db.scalar(select(Engagement).where(Engagement.target_id == target_id))
    if existing is not None:
        return TaskFirstEngagementCreateResult(result="existing", engagement=_engagement_view(existing))

    now = _utcnow()
    engagement = Engagement(
        id=uuid.uuid4(),
        target_id=target.id,
        community_id=target.community_id,
        topic_id=None,
        status=EngagementStatus.DRAFT.value,
        name=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.add(engagement)
    await db.flush()
    return TaskFirstEngagementCreateResult(result="created", engagement=_engagement_view(engagement))


async def patch_task_first_engagement(
    db: AsyncSession,
    *,
    engagement_id: UUID,
    topic_id: UUID | None,
    name: str | None,
    fields_set: set[str],
) -> TaskFirstEngagementPatchResult:
    engagement = await db.get(Engagement, engagement_id)
    if engagement is None:
        return TaskFirstEngagementPatchResult(
            result="stale",
            message="This engagement changed. Review it again.",
            code="engagement_stale",
        )
    if engagement.status == EngagementStatus.ARCHIVED.value:
        return TaskFirstEngagementPatchResult(
            result="blocked",
            message="This engagement cannot be edited right now.",
            code="engagement_archived",
        )

    if "topic_id" in fields_set:
        if topic_id is None and engagement.status != EngagementStatus.DRAFT.value:
            return TaskFirstEngagementPatchResult(
                result="blocked",
                message="This engagement cannot clear its topic right now.",
                code="topic_edit_blocked",
            )
        if topic_id is not None:
            topic = await db.get(EngagementTopic, topic_id)
            if topic is None or not topic.active:
                return TaskFirstEngagementPatchResult(
                    result="blocked",
                    message="Choose a topic.",
                    code="topic_missing",
                )
        engagement.topic_id = topic_id

    if "name" in fields_set:
        engagement.name = name.strip() if isinstance(name, str) and name.strip() else None

    engagement.updated_at = _utcnow()
    await db.flush()
    return TaskFirstEngagementPatchResult(result="updated", engagement=_engagement_view(engagement))


async def put_task_first_engagement_settings(
    db: AsyncSession,
    *,
    engagement_id: UUID,
    assigned_account_id: UUID | None,
    mode: str | None,
    quiet_hours_start: Any,
    quiet_hours_end: Any,
    fields_set: set[str],
) -> TaskFirstEngagementSettingsResult:
    engagement = await db.get(Engagement, engagement_id)
    if engagement is None:
        return TaskFirstEngagementSettingsResult(
            result="stale",
            message="This engagement changed. Review it again.",
            code="engagement_stale",
        )
    if engagement.status == EngagementStatus.ARCHIVED.value:
        return TaskFirstEngagementSettingsResult(
            result="blocked",
            message="This engagement cannot be edited right now.",
            code="engagement_archived",
        )

    settings = await _get_settings(db, engagement_id=engagement_id)
    now = _utcnow()
    if settings is None:
        settings = EngagementSettings(
            id=uuid.uuid4(),
            engagement_id=engagement.id,
            mode=EngagementMode.DISABLED.value,
            allow_join=False,
            allow_post=False,
            reply_only=True,
            require_approval=True,
            max_posts_per_day=1,
            min_minutes_between_posts=240,
            quiet_hours_start=None,
            quiet_hours_end=None,
            assigned_account_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(settings)

    if "assigned_account_id" in fields_set and assigned_account_id is not None:
        account = await db.get(TelegramAccount, assigned_account_id)
        if account is None:
            return TaskFirstEngagementSettingsResult(
                result="blocked",
                message="This account cannot be used here.",
                code="account_missing",
            )
        if account.status == AccountStatus.BANNED.value or account.account_pool != AccountPool.ENGAGEMENT.value:
            return TaskFirstEngagementSettingsResult(
                result="blocked",
                message="This account cannot be used here.",
                code="account_unusable",
            )

    quiet_start_set = "quiet_hours_start" in fields_set
    quiet_end_set = "quiet_hours_end" in fields_set
    if quiet_start_set != quiet_end_set:
        return TaskFirstEngagementSettingsResult(
            result="blocked",
            message="Quiet hours must include both start and end times.",
            code="invalid_quiet_hours",
        )

    if "mode" in fields_set:
        if mode not in {EngagementMode.SUGGEST.value, EngagementMode.AUTO_LIMITED.value}:
            return TaskFirstEngagementSettingsResult(
                result="blocked",
                message="Choose a supported sending mode.",
                code="sending_mode_unsupported",
            )
        settings.mode = mode
        settings.allow_join = True
        settings.allow_post = mode == EngagementMode.AUTO_LIMITED.value

    if "assigned_account_id" in fields_set:
        settings.assigned_account_id = assigned_account_id

    if quiet_start_set and quiet_end_set:
        settings.quiet_hours_start = quiet_hours_start
        settings.quiet_hours_end = quiet_hours_end

    settings.updated_at = now
    await db.flush()
    return TaskFirstEngagementSettingsResult(result="updated", settings=_settings_view(settings))


async def confirm_task_first_engagement(
    db: AsyncSession,
    *,
    engagement_id: UUID,
    requested_by: str,
    enqueue_detect: Callable[..., Any],
) -> TaskFirstWizardConfirmResult:
    engagement = await db.get(Engagement, engagement_id)
    if engagement is None:
        return TaskFirstWizardConfirmResult(
            result="stale",
            message="This engagement changed. Review it again.",
            next_callback="op:add",
        )
    if engagement.status == EngagementStatus.ARCHIVED.value:
        return TaskFirstWizardConfirmResult(
            result="blocked",
            message="This engagement cannot be started right now.",
            code="engagement_archived",
            next_callback=_detail_callback(engagement.id),
        )

    target = await db.get(EngagementTarget, engagement.target_id)
    if target is None or target.community_id is None or target.status in {
        EngagementTargetStatus.PENDING.value,
        EngagementTargetStatus.FAILED.value,
    }:
        return TaskFirstWizardConfirmResult(
            result="blocked",
            message="Target is not resolved.",
            code="target_not_resolved",
            next_callback=_wizard_edit_callback(engagement.id, "target"),
        )
    if target.status in {
        EngagementTargetStatus.REJECTED.value,
        EngagementTargetStatus.ARCHIVED.value,
    }:
        return TaskFirstWizardConfirmResult(
            result="blocked",
            message="Target is not approved.",
            code="target_not_approved",
            next_callback=_wizard_edit_callback(engagement.id, "target"),
        )
    community = await _load_task_first_community(db, community_id=engagement.community_id)
    if community is None:
        return TaskFirstWizardConfirmResult(
            result="blocked",
            message="Target is not resolved.",
            code="target_not_resolved",
            next_callback=_wizard_edit_callback(engagement.id, "target"),
        )

    if engagement.topic_id is None:
        return TaskFirstWizardConfirmResult(
            result="validation_failed",
            message="Choose a topic.",
            field="topic",
            next_callback=_wizard_edit_callback(engagement.id, "topic"),
        )

    topic = await db.get(EngagementTopic, engagement.topic_id)
    if topic is None or not topic.active:
        return TaskFirstWizardConfirmResult(
            result="validation_failed",
            message="Choose a topic.",
            field="topic",
            next_callback=_wizard_edit_callback(engagement.id, "topic"),
        )

    settings = await _get_settings(db, engagement_id=engagement.id)
    if settings is None or settings.assigned_account_id is None:
        return TaskFirstWizardConfirmResult(
            result="validation_failed",
            message="Choose an account.",
            field="account",
            next_callback=_wizard_edit_callback(engagement.id, "account"),
        )
    if settings.mode not in {EngagementMode.SUGGEST.value, EngagementMode.AUTO_LIMITED.value}:
        return TaskFirstWizardConfirmResult(
            result="validation_failed",
            message="Choose a sending mode.",
            field="sending_mode",
            next_callback=_wizard_edit_callback(engagement.id, "sending_mode"),
        )

    membership = await _get_membership(
        db,
        community_id=engagement.community_id,
        telegram_account_id=settings.assigned_account_id,
    )
    need_join = membership is None or membership.status != CommunityAccountMembershipStatus.JOINED.value

    now = _utcnow()
    settings.allow_join = True
    settings.allow_post = settings.mode == EngagementMode.AUTO_LIMITED.value
    settings.updated_at = now
    target.status = EngagementTargetStatus.APPROVED.value
    target.allow_join = True
    target.allow_detect = True
    target.allow_post = settings.allow_post
    _promote_task_first_community_for_engagement(community, reviewed_at=now)
    if target.approved_at is None:
        target.approved_at = now
    if not target.approved_by:
        target.approved_by = requested_by
    target.updated_at = now
    if engagement.status == EngagementStatus.DRAFT.value:
        engagement.status = EngagementStatus.ACTIVE.value
    engagement.updated_at = now
    await db.flush()

    if need_join:
        try:
            enqueue_community_join(
                community_id=engagement.community_id,
                telegram_account_id=settings.assigned_account_id,
                requested_by=requested_by,
            )
        except Exception:
            LOGGER.exception(
                "Failed to enqueue community join during task-first confirm",
                extra={
                    "engagement_id": str(engagement.id),
                    "community_id": str(engagement.community_id),
                    "telegram_account_id": str(settings.assigned_account_id),
                    "requested_by": requested_by,
                },
            )
            return TaskFirstWizardConfirmResult(
                result="blocked",
                message="Could not start the community join right now.",
                code="join_enqueue_failed",
                next_callback=_wizard_edit_callback(engagement.id, "account"),
            )
    else:
        try:
            enqueue_detect(
                engagement.community_id,
                window_minutes=60,
                requested_by=requested_by,
            )
        except Exception:
            LOGGER.exception(
                "Failed to enqueue engagement detect during task-first confirm",
                extra={
                    "engagement_id": str(engagement.id),
                    "community_id": str(engagement.community_id),
                    "requested_by": requested_by,
                },
            )
            return TaskFirstWizardConfirmResult(
                result="blocked",
                message="Could not start engagement right now.",
                code="detect_enqueue_failed",
                next_callback=_wizard_edit_callback(engagement.id, "sending_mode"),
            )

    return TaskFirstWizardConfirmResult(
        result="confirmed",
        message="Engagement started",
        engagement_id=engagement.id,
        engagement_status=engagement.status,
        target_status=target.status,
        next_callback=_detail_callback(engagement.id),
    )


async def retry_task_first_engagement(
    db: AsyncSession,
    *,
    engagement_id: UUID,
) -> TaskFirstWizardRetryResult:
    engagement = await db.get(Engagement, engagement_id)
    if engagement is None:
        return TaskFirstWizardRetryResult(
            result="stale",
            message="This draft is no longer available.",
            next_callback="op:add",
        )
    if engagement.status == EngagementStatus.ARCHIVED.value:
        return TaskFirstWizardRetryResult(
            result="blocked",
            message="This engagement cannot be reset right now.",
            code="engagement_archived",
            engagement_id=engagement.id,
            next_callback=_detail_callback(engagement.id),
        )
    if engagement.status != EngagementStatus.DRAFT.value:
        return TaskFirstWizardRetryResult(
            result="blocked",
            message="This engagement is already active.",
            code="engagement_active",
            engagement_id=engagement.id,
            next_callback=_detail_callback(engagement.id),
        )

    settings = await _get_settings(db, engagement_id=engagement.id)
    now = _utcnow()
    engagement.topic_id = None
    engagement.updated_at = now
    if settings is not None:
        settings.assigned_account_id = None
        settings.mode = EngagementMode.DISABLED.value
        settings.allow_join = False
        settings.allow_post = False
        settings.updated_at = now
    await db.flush()

    return TaskFirstWizardRetryResult(
        result="reset",
        message="Start again",
        engagement_id=engagement.id,
        next_callback="eng:wz:start",
    )


__all__ = [
    "TaskFirstEngagementCreateResult",
    "TaskFirstEngagementPatchResult",
    "TaskFirstEngagementSettingsResult",
    "TaskFirstEngagementSettingsView",
    "TaskFirstEngagementView",
    "TaskFirstWizardConfirmResult",
    "TaskFirstWizardRetryResult",
    "confirm_task_first_engagement",
    "create_task_first_engagement",
    "patch_task_first_engagement",
    "put_task_first_engagement_settings",
    "retry_task_first_engagement",
]
