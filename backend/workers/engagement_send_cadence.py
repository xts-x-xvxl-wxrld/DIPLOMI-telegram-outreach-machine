from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    EngagementActionStatus,
    EngagementActionType,
    EngagementOpportunityKind,
)
from backend.db.models import EngagementAction, EngagementCandidate
from backend.services.engagement_account_behavior import (
    MAX_CONTINUATION_REPLIES_PER_OPPORTUNITY_24H,
    MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_24H,
    MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_4H,
    MIN_MINUTES_BETWEEN_CONTINUATION_REPLIES,
    MIN_MINUTES_BETWEEN_STARTED_OPPORTUNITIES,
    SAME_COMMUNITY_NEW_OPPORTUNITY_COOLDOWN_MINUTES,
)


@dataclass(frozen=True)
class SendLimitDecision:
    allowed: bool
    reason: str | None = None


async def check_opportunity_cadence(
    session: AsyncSession,
    *,
    candidate: EngagementCandidate | None,
    community_id: uuid.UUID,
    telegram_account_id: uuid.UUID,
    now: datetime,
) -> SendLimitDecision:
    if candidate is not None and candidate.opportunity_kind == EngagementOpportunityKind.CONTINUATION.value:
        return await _check_continuation_cadence(
            session,
            root_candidate_id=candidate.root_candidate_id,
            telegram_account_id=telegram_account_id,
            now=now,
        )
    return await _check_root_opportunity_cadence(
        session,
        community_id=community_id,
        telegram_account_id=telegram_account_id,
        now=now,
    )


async def _check_root_opportunity_cadence(
    session: AsyncSession,
    *,
    community_id: uuid.UUID,
    telegram_account_id: uuid.UUID,
    now: datetime,
) -> SendLimitDecision:
    if await _count_started_root_opportunities(
        session,
        telegram_account_id=telegram_account_id,
        since=now - timedelta(hours=4),
    ) >= MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_4H:
        return SendLimitDecision(False, "Account 4-hour root opportunity limit reached")
    if await _count_started_root_opportunities(
        session,
        telegram_account_id=telegram_account_id,
        since=now - timedelta(hours=24),
    ) >= MAX_STARTED_OPPORTUNITIES_PER_ACCOUNT_24H:
        return SendLimitDecision(False, "Account 24-hour root opportunity limit reached")

    latest_account_start = await _latest_started_root_opportunity(
        session,
        telegram_account_id=telegram_account_id,
    )
    if _action_started_at(latest_account_start) is not None:
        assert latest_account_start is not None
        cutoff = now - timedelta(minutes=MIN_MINUTES_BETWEEN_STARTED_OPPORTUNITIES)
        if _action_started_at(latest_account_start) > cutoff:
            return SendLimitDecision(False, "Account root opportunity spacing limit has not elapsed")

    latest_community_start = await _latest_started_root_opportunity(
        session,
        telegram_account_id=telegram_account_id,
        community_id=community_id,
    )
    if _action_started_at(latest_community_start) is not None:
        assert latest_community_start is not None
        cutoff = now - timedelta(minutes=SAME_COMMUNITY_NEW_OPPORTUNITY_COOLDOWN_MINUTES)
        if _action_started_at(latest_community_start) > cutoff:
            return SendLimitDecision(False, "Same-community root opportunity cooldown has not elapsed")
    return SendLimitDecision(True)


async def _check_continuation_cadence(
    session: AsyncSession,
    *,
    root_candidate_id: uuid.UUID | None,
    telegram_account_id: uuid.UUID,
    now: datetime,
) -> SendLimitDecision:
    if root_candidate_id is None:
        return SendLimitDecision(False, "Continuation is missing root opportunity")
    if await _count_continuation_replies(
        session,
        root_candidate_id=root_candidate_id,
        telegram_account_id=telegram_account_id,
        since=now - timedelta(hours=24),
    ) >= MAX_CONTINUATION_REPLIES_PER_OPPORTUNITY_24H:
        return SendLimitDecision(False, "Continuation 24-hour reply limit reached")
    latest_continuation = await _latest_continuation_reply(
        session,
        root_candidate_id=root_candidate_id,
        telegram_account_id=telegram_account_id,
    )
    if _action_started_at(latest_continuation) is not None:
        assert latest_continuation is not None
        cutoff = now - timedelta(minutes=MIN_MINUTES_BETWEEN_CONTINUATION_REPLIES)
        if _action_started_at(latest_continuation) > cutoff:
            return SendLimitDecision(False, "Continuation spacing limit has not elapsed")
    return SendLimitDecision(True)


async def _count_started_root_opportunities(
    session: AsyncSession,
    *,
    telegram_account_id: uuid.UUID,
    since: datetime,
) -> int:
    query = (
        select(func.count(EngagementAction.id))
        .join(EngagementCandidate, EngagementAction.candidate_id == EngagementCandidate.id)
        .where(
            EngagementAction.status.in_(
                (EngagementActionStatus.QUEUED.value, EngagementActionStatus.SENT.value)
            ),
            EngagementAction.action_type == EngagementActionType.REPLY.value,
            EngagementAction.telegram_account_id == telegram_account_id,
            EngagementCandidate.opportunity_kind == EngagementOpportunityKind.ROOT.value,
            _action_started_expression() >= since,
        )
    )
    return int(await session.scalar(query) or 0)


async def _latest_started_root_opportunity(
    session: AsyncSession,
    *,
    telegram_account_id: uuid.UUID,
    community_id: uuid.UUID | None = None,
) -> EngagementAction | None:
    query = (
        select(EngagementAction)
        .join(EngagementCandidate, EngagementAction.candidate_id == EngagementCandidate.id)
        .where(
            EngagementAction.status.in_(
                (EngagementActionStatus.QUEUED.value, EngagementActionStatus.SENT.value)
            ),
            EngagementAction.action_type == EngagementActionType.REPLY.value,
            EngagementAction.telegram_account_id == telegram_account_id,
            EngagementCandidate.opportunity_kind == EngagementOpportunityKind.ROOT.value,
        )
        .order_by(
            _action_started_expression().desc().nullslast(),
            EngagementAction.created_at.desc(),
        )
        .limit(1)
    )
    if community_id is not None:
        query = query.where(EngagementAction.community_id == community_id)
    return await session.scalar(query)


async def _count_continuation_replies(
    session: AsyncSession,
    *,
    root_candidate_id: uuid.UUID,
    telegram_account_id: uuid.UUID,
    since: datetime,
) -> int:
    query = (
        select(func.count(EngagementAction.id))
        .join(EngagementCandidate, EngagementAction.candidate_id == EngagementCandidate.id)
        .where(
            EngagementAction.status.in_(
                (EngagementActionStatus.QUEUED.value, EngagementActionStatus.SENT.value)
            ),
            EngagementAction.action_type == EngagementActionType.REPLY.value,
            EngagementAction.telegram_account_id == telegram_account_id,
            EngagementCandidate.opportunity_kind == EngagementOpportunityKind.CONTINUATION.value,
            EngagementCandidate.root_candidate_id == root_candidate_id,
            _action_started_expression() >= since,
        )
    )
    return int(await session.scalar(query) or 0)


async def _latest_continuation_reply(
    session: AsyncSession,
    *,
    root_candidate_id: uuid.UUID,
    telegram_account_id: uuid.UUID,
) -> EngagementAction | None:
    return await session.scalar(
        select(EngagementAction)
        .join(EngagementCandidate, EngagementAction.candidate_id == EngagementCandidate.id)
        .where(
            EngagementAction.status.in_(
                (EngagementActionStatus.QUEUED.value, EngagementActionStatus.SENT.value)
            ),
            EngagementAction.action_type == EngagementActionType.REPLY.value,
            EngagementAction.telegram_account_id == telegram_account_id,
            EngagementCandidate.opportunity_kind == EngagementOpportunityKind.CONTINUATION.value,
            EngagementCandidate.root_candidate_id == root_candidate_id,
        )
        .order_by(
            _action_started_expression().desc().nullslast(),
            EngagementAction.created_at.desc(),
        )
        .limit(1)
    )


def _action_started_expression() -> object:
    return func.coalesce(EngagementAction.scheduled_at, EngagementAction.sent_at, EngagementAction.created_at)


def _action_started_at(action: EngagementAction | None) -> datetime | None:
    if action is None:
        return None
    for value in (action.scheduled_at, action.sent_at, action.created_at):
        if value is not None:
            return _ensure_aware_utc(value)
    return None


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = ["SendLimitDecision", "check_opportunity_cadence"]
