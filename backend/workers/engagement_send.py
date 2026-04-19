from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.enums import (
    EngagementActionStatus,
    EngagementActionType,
    EngagementCandidateStatus,
    EngagementMode,
)
from backend.db.models import CommunityAccountMembership, EngagementAction, EngagementCandidate
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import EngagementSendPayload
from backend.services.community_engagement import (
    EngagementValidationError,
    get_engagement_settings,
    get_joined_membership_for_send,
    has_engagement_target_permission,
    validate_suggested_reply,
)
from backend.workers.account_manager import (
    AccountLease,
    acquire_account_by_id,
    release_account,
)
from backend.workers.telegram_engagement import (
    EngagementAccountBanned,
    EngagementAccountRateLimited,
    EngagementCommunityInaccessible,
    EngagementMessageNotReplyable,
    SendResult,
    TelegramEngagementAdapter,
    TelethonTelegramEngagementAdapter,
)


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountByIdFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
EngagementAdapterFactory = Callable[[AccountLease], TelegramEngagementAdapter]


@dataclass(frozen=True)
class SendLimitDecision:
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True)
class ActionReservation:
    action: EngagementAction
    created: bool


async def process_engagement_send(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_by_id_fn: AcquireAccountByIdFn = acquire_account_by_id,
    release_account_fn: ReleaseAccountFn = release_account,
    adapter_factory: EngagementAdapterFactory = TelethonTelegramEngagementAdapter,
    rate_limit_checker: Callable[..., Any] = None,  # type: ignore[assignment]
) -> dict[str, object]:
    validated_payload = EngagementSendPayload.model_validate(payload)
    job_id = _current_job_id() or f"engagement.send:{validated_payload.candidate_id}"
    idempotency_key = _send_idempotency_key(validated_payload.candidate_id)
    rate_limit_checker = rate_limit_checker or check_send_limits

    async with session_factory() as session:
        lease: AccountLease | None = None
        adapter: TelegramEngagementAdapter | None = None
        candidate: EngagementCandidate | None = None
        membership: CommunityAccountMembership | None = None
        try:
            candidate = await _load_candidate(session, validated_payload.candidate_id)
            if candidate is None:
                return _skipped("candidate_not_found", validated_payload.candidate_id)

            existing_sent_action = await _load_action_by_idempotency(session, idempotency_key)
            if existing_sent_action is not None and existing_sent_action.status == EngagementActionStatus.SENT.value:
                await _mark_candidate_sent(session, candidate)
                await session.commit()
                return _send_summary(validated_payload, existing_sent_action)

            if candidate.status == EngagementCandidateStatus.SENT.value:
                return _skipped("candidate_already_sent", candidate.id)
            if candidate.status != EngagementCandidateStatus.APPROVED.value:
                return _skipped("candidate_not_approved", candidate.id)

            now = _utcnow()
            if _is_expired(candidate, now):
                candidate.status = EngagementCandidateStatus.EXPIRED.value
                candidate.updated_at = now
                await session.commit()
                return _skipped("candidate_expired", candidate.id)

            settings = await get_engagement_settings(session, candidate.community_id)
            if settings.mode == EngagementMode.DISABLED.value or not settings.allow_post:
                return _skipped("posting_not_allowed", candidate.id)
            if not await has_engagement_target_permission(
                session,
                community_id=candidate.community_id,
                permission="post",
            ):
                return _skipped("engagement_target_post_not_approved", candidate.id)
            if not settings.require_approval:
                return _skipped("approval_required", candidate.id)
            if settings.reply_only and candidate.source_tg_message_id is None:
                return _skipped("reply_target_required", candidate.id)

            membership = await get_joined_membership_for_send(
                session,
                community_id=candidate.community_id,
            )
            if membership is None:
                return _skipped("no_joined_membership", candidate.id)

            final_reply = candidate.final_reply
            try:
                outbound_text = validate_suggested_reply(final_reply)
            except EngagementValidationError as exc:
                action = await _reserve_action(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                    outbound_text=final_reply or "",
                    now=now,
                )
                await _mark_action_skipped(
                    action.action,
                    error_message=exc.message,
                    candidate_status=EngagementCandidateStatus.FAILED.value,
                    candidate=candidate,
                )
                await session.commit()
                return _send_summary(validated_payload, action.action)
            if outbound_text is None:
                action = await _reserve_action(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                    outbound_text="",
                    now=now,
                )
                await _mark_action_skipped(
                    action.action,
                    error_message="Approved candidate has no final reply",
                    candidate_status=EngagementCandidateStatus.FAILED.value,
                    candidate=candidate,
                )
                await session.commit()
                return _send_summary(validated_payload, action.action)

            limit_decision = await rate_limit_checker(
                session,
                community_id=candidate.community_id,
                telegram_account_id=membership.telegram_account_id,
                max_posts_per_day=settings.max_posts_per_day,
                min_minutes_between_posts=settings.min_minutes_between_posts,
                now=now,
            )
            if not limit_decision.allowed:
                action = await _reserve_action(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                    outbound_text=outbound_text,
                    now=now,
                )
                await _mark_action_skipped(
                    action.action,
                    error_message=limit_decision.reason or "Send limit would be exceeded",
                    candidate_status=EngagementCandidateStatus.APPROVED.value,
                    candidate=candidate,
                )
                await session.commit()
                return _send_summary(validated_payload, action.action)

            reservation = await _reserve_action(
                session,
                candidate=candidate,
                membership=membership,
                idempotency_key=idempotency_key,
                outbound_text=outbound_text,
                now=now,
            )
            action = reservation.action
            if not reservation.created:
                if action.status == EngagementActionStatus.SENT.value:
                    await _mark_candidate_sent(session, candidate)
                    await session.commit()
                    return _send_summary(validated_payload, action)
                if action.status in {
                    EngagementActionStatus.FAILED.value,
                    EngagementActionStatus.SKIPPED.value,
                }:
                    return _send_summary(validated_payload, action)
                await _mark_action_failed(
                    action,
                    error_message=(
                        "Existing queued send action cannot be safely retried without "
                        "Telegram confirmation"
                    ),
                    candidate_status=EngagementCandidateStatus.APPROVED.value,
                    candidate=candidate,
                )
                await session.commit()
                return _send_summary(validated_payload, action)

            lease = await acquire_account_by_id_fn(
                session,
                account_id=membership.telegram_account_id,
                job_id=job_id,
                purpose="engagement_send",
            )
            await session.commit()

            adapter = adapter_factory(lease)
            assert candidate.community is not None
            assert candidate.source_tg_message_id is not None
            result = await adapter.send_public_reply(
                session_file_path=lease.session_file_path,
                community=candidate.community,
                reply_to_tg_message_id=candidate.source_tg_message_id,
                text=outbound_text,
            )
            await _record_send_success(session, action=action, candidate=candidate, result=result)
            await release_account_fn(
                session,
                account_id=lease.account_id,
                job_id=job_id,
                outcome="success",
            )
            await session.commit()
            return _send_summary(validated_payload, action)
        except EngagementAccountRateLimited as exc:
            await session.rollback()
            if candidate is not None and membership is not None and lease is not None:
                action = await _ensure_action_for_error(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                )
                await _mark_action_failed(
                    action,
                    error_message=str(exc),
                    candidate_status=EngagementCandidateStatus.APPROVED.value,
                    candidate=candidate,
                )
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="rate_limited",
                    flood_wait_seconds=exc.flood_wait_seconds,
                    error_message=str(exc),
                )
                await session.commit()
            raise
        except EngagementAccountBanned as exc:
            await session.rollback()
            if candidate is not None and membership is not None and lease is not None:
                action = await _ensure_action_for_error(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                )
                await _mark_action_failed(
                    action,
                    error_message=str(exc),
                    candidate_status=EngagementCandidateStatus.FAILED.value,
                    candidate=candidate,
                )
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="banned",
                    error_message=str(exc),
                )
                await session.commit()
            raise
        except EngagementCommunityInaccessible as exc:
            await session.rollback()
            if candidate is not None and membership is not None and lease is not None:
                action = await _ensure_action_for_error(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                )
                await _mark_action_skipped(
                    action,
                    error_message=str(exc),
                    candidate_status=EngagementCandidateStatus.APPROVED.value,
                    candidate=candidate,
                )
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="success",
                )
                await session.commit()
                return _send_summary(validated_payload, action)
            raise
        except EngagementMessageNotReplyable as exc:
            await session.rollback()
            if candidate is not None and membership is not None and lease is not None:
                action = await _ensure_action_for_error(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                )
                await _mark_action_skipped(
                    action,
                    error_message=str(exc),
                    candidate_status=EngagementCandidateStatus.EXPIRED.value,
                    candidate=candidate,
                )
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="success",
                )
                await session.commit()
                return _send_summary(validated_payload, action)
            raise
        except Exception as exc:
            await session.rollback()
            if candidate is not None and membership is not None and lease is not None:
                action = await _ensure_action_for_error(
                    session,
                    candidate=candidate,
                    membership=membership,
                    idempotency_key=idempotency_key,
                )
                await _mark_action_failed(
                    action,
                    error_message=str(exc),
                    candidate_status=EngagementCandidateStatus.APPROVED.value,
                    candidate=candidate,
                )
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="error",
                    error_message=str(exc),
                )
                await session.commit()
            raise
        finally:
            if adapter is not None and hasattr(adapter, "aclose"):
                await adapter.aclose()  # type: ignore[attr-defined]


async def check_send_limits(
    session: AsyncSession,
    *,
    community_id: uuid.UUID,
    telegram_account_id: uuid.UUID,
    max_posts_per_day: int,
    min_minutes_between_posts: int,
    now: datetime | None = None,
) -> SendLimitDecision:
    current_time = now or _utcnow()
    if max_posts_per_day <= 0:
        return SendLimitDecision(False, "Community max_posts_per_day is 0")

    cutoff = current_time - timedelta(hours=24)
    community_count = await _count_sent_replies(
        session,
        community_id=community_id,
        since=cutoff,
    )
    if community_count >= max_posts_per_day:
        return SendLimitDecision(False, "Community daily send limit reached")

    account_count = await _count_sent_replies(
        session,
        telegram_account_id=telegram_account_id,
        since=cutoff,
    )
    if account_count >= max_posts_per_day:
        return SendLimitDecision(False, "Account daily send limit reached")

    spacing_cutoff = current_time - timedelta(minutes=min_minutes_between_posts)
    latest_community_action = await _latest_sent_reply(session, community_id=community_id)
    if _action_sent_at(latest_community_action) is not None:
        assert latest_community_action is not None
        if _action_sent_at(latest_community_action) > spacing_cutoff:
            return SendLimitDecision(False, "Community spacing limit has not elapsed")

    latest_account_action = await _latest_sent_reply(
        session,
        telegram_account_id=telegram_account_id,
    )
    if _action_sent_at(latest_account_action) is not None:
        assert latest_account_action is not None
        if _action_sent_at(latest_account_action) > spacing_cutoff:
            return SendLimitDecision(False, "Account spacing limit has not elapsed")

    return SendLimitDecision(True)


def run_engagement_send_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_engagement_send(payload))


async def _load_candidate(
    session: AsyncSession,
    candidate_id: uuid.UUID,
) -> EngagementCandidate | None:
    return await session.scalar(
        select(EngagementCandidate)
        .options(
            joinedload(EngagementCandidate.community),
            joinedload(EngagementCandidate.topic),
        )
        .where(EngagementCandidate.id == candidate_id)
        .limit(1)
    )


async def _load_action_by_idempotency(
    session: AsyncSession,
    idempotency_key: str,
) -> EngagementAction | None:
    return await session.scalar(
        select(EngagementAction)
        .where(EngagementAction.idempotency_key == idempotency_key)
        .limit(1)
    )


async def _reserve_action(
    session: AsyncSession,
    *,
    candidate: EngagementCandidate,
    membership: CommunityAccountMembership,
    idempotency_key: str,
    outbound_text: str,
    now: datetime,
) -> ActionReservation:
    existing = await _load_action_by_idempotency(session, idempotency_key)
    if existing is not None:
        return ActionReservation(action=existing, created=False)

    action = EngagementAction(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        community_id=candidate.community_id,
        telegram_account_id=membership.telegram_account_id,
        action_type=EngagementActionType.REPLY.value,
        status=EngagementActionStatus.QUEUED.value,
        idempotency_key=idempotency_key,
        outbound_text=outbound_text,
        reply_to_tg_message_id=candidate.source_tg_message_id,
        scheduled_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(action)
    await session.flush()
    return ActionReservation(action=action, created=True)


async def _ensure_action_for_error(
    session: AsyncSession,
    *,
    candidate: EngagementCandidate,
    membership: CommunityAccountMembership,
    idempotency_key: str,
) -> EngagementAction:
    reservation = await _reserve_action(
        session,
        candidate=candidate,
        membership=membership,
        idempotency_key=idempotency_key,
        outbound_text=candidate.final_reply or "",
        now=_utcnow(),
    )
    return reservation.action


async def _record_send_success(
    session: AsyncSession,
    *,
    action: EngagementAction,
    candidate: EngagementCandidate,
    result: SendResult,
) -> None:
    now = _utcnow()
    action.status = EngagementActionStatus.SENT.value
    action.sent_tg_message_id = result.sent_tg_message_id
    action.sent_at = result.sent_at
    action.error_message = None
    action.updated_at = now
    await _mark_candidate_sent(session, candidate, now=now)


async def _mark_candidate_sent(
    session: AsyncSession,
    candidate: EngagementCandidate,
    *,
    now: datetime | None = None,
) -> None:
    candidate.status = EngagementCandidateStatus.SENT.value
    candidate.updated_at = now or _utcnow()
    await session.flush()


async def _mark_action_skipped(
    action: EngagementAction,
    *,
    error_message: str,
    candidate_status: str,
    candidate: EngagementCandidate,
) -> None:
    now = _utcnow()
    action.status = EngagementActionStatus.SKIPPED.value
    action.error_message = error_message
    action.updated_at = now
    candidate.status = candidate_status
    candidate.updated_at = now


async def _mark_action_failed(
    action: EngagementAction,
    *,
    error_message: str,
    candidate_status: str,
    candidate: EngagementCandidate,
) -> None:
    now = _utcnow()
    action.status = EngagementActionStatus.FAILED.value
    action.error_message = error_message
    action.updated_at = now
    candidate.status = candidate_status
    candidate.updated_at = now


async def _count_sent_replies(
    session: AsyncSession,
    *,
    since: datetime,
    community_id: uuid.UUID | None = None,
    telegram_account_id: uuid.UUID | None = None,
) -> int:
    query = select(func.count(EngagementAction.id)).where(
        EngagementAction.status == EngagementActionStatus.SENT.value,
        EngagementAction.action_type == EngagementActionType.REPLY.value,
        EngagementAction.sent_at >= since,
    )
    if community_id is not None:
        query = query.where(EngagementAction.community_id == community_id)
    if telegram_account_id is not None:
        query = query.where(EngagementAction.telegram_account_id == telegram_account_id)
    return int(await session.scalar(query) or 0)


async def _latest_sent_reply(
    session: AsyncSession,
    *,
    community_id: uuid.UUID | None = None,
    telegram_account_id: uuid.UUID | None = None,
) -> EngagementAction | None:
    query = (
        select(EngagementAction)
        .where(
            EngagementAction.status == EngagementActionStatus.SENT.value,
            EngagementAction.action_type == EngagementActionType.REPLY.value,
        )
        .order_by(EngagementAction.sent_at.desc().nullslast(), EngagementAction.created_at.desc())
        .limit(1)
    )
    if community_id is not None:
        query = query.where(EngagementAction.community_id == community_id)
    if telegram_account_id is not None:
        query = query.where(EngagementAction.telegram_account_id == telegram_account_id)
    return await session.scalar(query)


def _action_sent_at(action: EngagementAction | None) -> datetime | None:
    if action is None or action.sent_at is None:
        return None
    return _ensure_aware_utc(action.sent_at)


def _is_expired(candidate: EngagementCandidate, now: datetime) -> bool:
    return _ensure_aware_utc(candidate.expires_at) <= _ensure_aware_utc(now)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _send_idempotency_key(candidate_id: uuid.UUID) -> str:
    return f"engagement.send:{candidate_id}"


def _send_summary(payload: EngagementSendPayload, action: EngagementAction) -> dict[str, object]:
    status = "processed"
    if action.status == EngagementActionStatus.SKIPPED.value:
        status = "skipped"
    elif action.status == EngagementActionStatus.FAILED.value:
        status = "failed"
    return {
        "status": status,
        "job_type": "engagement.send",
        "candidate_id": str(payload.candidate_id),
        "community_id": str(action.community_id),
        "telegram_account_id": str(action.telegram_account_id),
        "action_id": str(action.id),
        "action_status": action.status,
        "sent_tg_message_id": action.sent_tg_message_id,
        "reason": action.error_message,
    }


def _skipped(reason: str, candidate_id: object) -> dict[str, object]:
    return {
        "status": "skipped",
        "job_type": "engagement.send",
        "candidate_id": str(candidate_id),
        "reason": reason,
    }


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
