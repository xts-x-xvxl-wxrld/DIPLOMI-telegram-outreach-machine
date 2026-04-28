# ruff: noqa: F401,F403,F405
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    AccountPool,
    AccountStatus,
    CommunityAccountMembershipStatus,
    CommunitySource,
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
    EngagementStyleRuleScope,
    EngagementTargetRefType,
    EngagementTargetStatus,
    TelegramEntityIntakeStatus,
    TelegramEntityType,
)
from backend.db.models import (
    Community,
    CommunityAccountMembership,
    CommunityEngagementSettings,
    EngagementAction,
    EngagementCandidate,
    EngagementCandidateRevision,
    EngagementPromptProfile,
    EngagementPromptProfileVersion,
    EngagementStyleRule,
    EngagementTarget,
    EngagementTopic,
    TelegramAccount,
)
from backend.services.seed_import import normalize_telegram_seed
from backend.services.seed_resolution import TransientResolveError
from backend.services.telegram_entity_intake import (
    TelegramEntityInfo,
    TelegramEntityResolveOutcome,
    TelegramEntityResolverAdapter,
)
from backend.services.community_engagement_views import *

_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_SEMANTIC_ROLLOUT_BANDS = (
    ("0.90-1.00", 0.90, 1.0),
    ("0.80-0.89", 0.80, 0.90),
    ("0.70-0.79", 0.70, 0.80),
    ("0.62-0.69", 0.62, 0.70),
    ("0.00-0.61", 0.00, 0.62),
)
_ALLOWED_PROMPT_VARIABLES = {
    "community.title",
    "community.username",
    "community.description",
    "topic.name",
    "topic.description",
    "topic.stance_guidance",
    "topic.trigger_keywords",
    "topic.negative_keywords",
    "topic.example_good_replies",
    "topic.example_bad_replies",
    "style.global",
    "style.account",
    "style.community",
    "style.topic",
    "source_post.text",
    "source_post.tg_message_id",
    "source_post.message_date",
    "reply_context",
    "messages",
    "community_context.latest_summary",
    "community_context.dominant_themes",
}

async def get_engagement_settings(
    db: AsyncSession,
    community_id: UUID,
) -> EngagementSettingsView:
    community = await db.get(Community, community_id)
    if community is None:
        raise EngagementNotFound("not_found", "Community not found")

    settings = await db.scalar(
        select(CommunityEngagementSettings).where(
            CommunityEngagementSettings.community_id == community_id
        )
    )
    if settings is None:
        return _disabled_settings_view(community_id)
    return _settings_view(settings)


async def upsert_engagement_settings(
    db: AsyncSession,
    *,
    community_id: UUID,
    payload: Any,
    updated_by: str,
) -> EngagementSettingsView:
    del updated_by
    community = await db.get(Community, community_id)
    if community is None:
        raise EngagementNotFound("not_found", "Community not found")

    values = _settings_values(payload)
    await _validate_settings_values(db, community, values)

    settings = await db.scalar(
        select(CommunityEngagementSettings).where(
            CommunityEngagementSettings.community_id == community_id
        )
    )
    now = _utcnow()
    if settings is None:
        settings = CommunityEngagementSettings(
            id=uuid.uuid4(),
            community_id=community_id,
            created_at=now,
        )
        db.add(settings)

    settings.mode = values["mode"]
    settings.allow_join = values["allow_join"]
    settings.allow_post = values["allow_post"]
    settings.reply_only = values["reply_only"]
    settings.require_approval = values["require_approval"]
    settings.max_posts_per_day = values["max_posts_per_day"]
    settings.min_minutes_between_posts = values["min_minutes_between_posts"]
    settings.quiet_hours_start = values["quiet_hours_start"]
    settings.quiet_hours_end = values["quiet_hours_end"]
    settings.assigned_account_id = values["assigned_account_id"]
    settings.updated_at = now
    await db.flush()
    return _settings_view(settings)


async def mark_join_requested(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership:
    now = _utcnow()
    membership = await _get_membership(
        db,
        community_id=community_id,
        telegram_account_id=telegram_account_id,
    )
    if membership is None:
        membership = CommunityAccountMembership(
            id=uuid.uuid4(),
            community_id=community_id,
            telegram_account_id=telegram_account_id,
            created_at=now,
        )
        db.add(membership)
    elif membership.status == CommunityAccountMembershipStatus.BANNED.value:
        raise EngagementValidationError(
            "membership_banned",
            "This account is banned from the community until an operator resets it",
        )

    membership.status = CommunityAccountMembershipStatus.JOIN_REQUESTED.value
    membership.last_checked_at = now
    membership.last_error = None
    membership.updated_at = now
    await db.flush()
    return membership


async def mark_join_result(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
    status: str,
    joined_at: datetime | None,
    error_message: str | None,
) -> CommunityAccountMembership:
    allowed_statuses = {
        CommunityAccountMembershipStatus.JOINED.value,
        CommunityAccountMembershipStatus.FAILED.value,
        CommunityAccountMembershipStatus.BANNED.value,
    }
    if status not in allowed_statuses:
        raise EngagementValidationError(
            "invalid_membership_status",
            "Join result status must be joined, failed, or banned",
        )

    now = _utcnow()
    membership = await _get_membership(
        db,
        community_id=community_id,
        telegram_account_id=telegram_account_id,
    )
    if membership is None:
        membership = CommunityAccountMembership(
            id=uuid.uuid4(),
            community_id=community_id,
            telegram_account_id=telegram_account_id,
            created_at=now,
        )
        db.add(membership)

    membership.status = status
    membership.joined_at = joined_at if status == CommunityAccountMembershipStatus.JOINED.value else None
    if status == CommunityAccountMembershipStatus.JOINED.value and membership.joined_at is None:
        membership.joined_at = now
    membership.last_checked_at = now
    membership.last_error = error_message
    membership.updated_at = now
    await db.flush()
    return membership


async def get_joined_membership_for_send(
    db: AsyncSession,
    *,
    community_id: UUID,
) -> CommunityAccountMembership | None:
    return await db.scalar(
        select(CommunityAccountMembership)
        .join(TelegramAccount, CommunityAccountMembership.telegram_account_id == TelegramAccount.id)
        .where(
            CommunityAccountMembership.community_id == community_id,
            CommunityAccountMembership.status == CommunityAccountMembershipStatus.JOINED.value,
            TelegramAccount.account_pool == AccountPool.ENGAGEMENT.value,
        )
        .order_by(CommunityAccountMembership.joined_at.asc().nullslast())
        .limit(1)
    )


def _disabled_settings_view(community_id: UUID) -> EngagementSettingsView:
    return EngagementSettingsView(
        community_id=community_id,
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
        created_at=None,
        updated_at=None,
    )


def _settings_view(settings: CommunityEngagementSettings) -> EngagementSettingsView:
    return EngagementSettingsView(
        community_id=settings.community_id,
        mode=settings.mode,
        allow_join=settings.allow_join,
        allow_post=settings.allow_post,
        reply_only=settings.reply_only,
        require_approval=settings.require_approval,
        max_posts_per_day=settings.max_posts_per_day,
        min_minutes_between_posts=settings.min_minutes_between_posts,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        assigned_account_id=settings.assigned_account_id,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


def _settings_values(payload: Any) -> dict[str, Any]:
    mode = _enum_value(payload.mode)
    allow_join = bool(payload.allow_join)
    allow_post = bool(payload.allow_post)
    if mode == EngagementMode.DISABLED.value:
        allow_join = False
        allow_post = False

    return {
        "mode": mode,
        "allow_join": allow_join,
        "allow_post": allow_post,
        "reply_only": bool(payload.reply_only),
        "require_approval": bool(payload.require_approval),
        "max_posts_per_day": int(payload.max_posts_per_day),
        "min_minutes_between_posts": int(payload.min_minutes_between_posts),
        "quiet_hours_start": payload.quiet_hours_start,
        "quiet_hours_end": payload.quiet_hours_end,
        "assigned_account_id": payload.assigned_account_id,
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _validate_settings_values(
    db: AsyncSession,
    community: Community,
    values: dict[str, Any],
) -> None:
    if values["require_approval"] is False:
        raise EngagementValidationError(
            "approval_required",
            "require_approval must remain true in the MVP",
        )
    if values["reply_only"] is False:
        raise EngagementValidationError(
            "reply_only_required",
            "reply_only must remain true in the MVP",
        )
    if not 0 <= values["max_posts_per_day"] <= 3:
        raise EngagementValidationError(
            "invalid_max_posts_per_day",
            "max_posts_per_day must be between 0 and 3 in the MVP",
        )
    if values["min_minutes_between_posts"] < 60:
        raise EngagementValidationError(
            "invalid_min_minutes_between_posts",
            "min_minutes_between_posts must be at least 60 in the MVP",
        )
    quiet_start = values["quiet_hours_start"]
    quiet_end = values["quiet_hours_end"]
    if (quiet_start is None) != (quiet_end is None):
        raise EngagementValidationError(
            "invalid_quiet_hours",
            "quiet_hours_start and quiet_hours_end must be provided together",
        )
    if values["allow_join"] or values["allow_post"]:
        if community.status not in {
            CommunityStatus.APPROVED.value,
            CommunityStatus.MONITORING.value,
        }:
            raise EngagementValidationError(
                "community_not_engagement_approved",
                "Only approved or monitoring communities may enable engagement joins or posts",
            )
    if values["assigned_account_id"] is not None:
        account = await db.get(TelegramAccount, values["assigned_account_id"])
        if account is None:
            raise EngagementValidationError(
                "assigned_account_not_found",
                "assigned_account_id must reference an existing Telegram account",
            )
        if account.status == AccountStatus.BANNED.value:
            raise EngagementValidationError(
                "assigned_account_banned",
                "assigned_account_id must not reference a banned Telegram account",
            )
        if account.account_pool != AccountPool.ENGAGEMENT.value:
            raise EngagementValidationError(
                "assigned_account_wrong_pool",
                "assigned_account_id must reference an engagement Telegram account",
            )


async def _get_membership(
    db: AsyncSession,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership | None:
    return await db.scalar(
        select(CommunityAccountMembership)
        .where(
            CommunityAccountMembership.community_id == community_id,
            CommunityAccountMembership.telegram_account_id == telegram_account_id,
        )
        .limit(1)
    )


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)

__all__ = [
    "get_engagement_settings",
    "upsert_engagement_settings",
    "mark_join_requested",
    "mark_join_result",
    "get_joined_membership_for_send",
]
