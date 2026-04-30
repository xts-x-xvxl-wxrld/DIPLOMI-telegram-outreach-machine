from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.enums import (
    CommunityAccountMembershipStatus,
    CommunityStatus,
    EngagementActionStatus,
    EngagementActionType,
    EngagementMode,
)
from backend.db.models import Community, EngagementAction
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import CommunityJoinPayload
from backend.queue.client import enqueue_manual_engagement_detect
from backend.services.community_engagement import (
    get_engagement_settings,
    get_joined_membership_for_send,
    has_engagement_target_permission,
    mark_join_requested,
    mark_join_result,
)
from backend.workers.account_manager import (
    AccountLease,
    acquire_account,
    acquire_account_by_id,
    release_account,
)
from backend.workers.telegram_engagement import (
    EngagementAccountBanned,
    EngagementAccountRateLimited,
    JoinResult,
    TelegramEngagementAdapter,
    TelethonTelegramEngagementAdapter,
)


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
EngagementAdapterFactory = Callable[[AccountLease], TelegramEngagementAdapter]
LOGGER = logging.getLogger(__name__)


async def process_community_join(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    acquire_account_by_id_fn: AcquireAccountFn = acquire_account_by_id,
    release_account_fn: ReleaseAccountFn = release_account,
    adapter_factory: EngagementAdapterFactory = TelethonTelegramEngagementAdapter,
    enqueue_detect_fn: Callable[..., Any] = enqueue_manual_engagement_detect,
) -> dict[str, object]:
    validated_payload = CommunityJoinPayload.model_validate(payload)
    job_id = _current_job_id() or f"community.join:{validated_payload.community_id}"
    LOGGER.info(
        "Starting community join",
        extra={
            "job_id": job_id,
            "community_id": str(validated_payload.community_id),
            "telegram_account_id": None
            if validated_payload.telegram_account_id is None
            else str(validated_payload.telegram_account_id),
        },
    )

    async with session_factory() as session:
        lease: AccountLease | None = None
        adapter: TelegramEngagementAdapter | None = None
        action: EngagementAction | None = None
        community: Community | None = None
        try:
            community = await session.get(Community, validated_payload.community_id)
            if community is None:
                LOGGER.warning(
                    "Skipping community join because community was not found",
                    extra={"job_id": job_id, "community_id": str(validated_payload.community_id)},
                )
                return _skipped("community_not_found", validated_payload.community_id)

            settings = await get_engagement_settings(session, validated_payload.community_id)
            if validated_payload.telegram_account_id is None:
                if settings.mode == EngagementMode.DISABLED.value or not settings.allow_join:
                    LOGGER.info(
                        "Skipping community join because joins are not allowed",
                        extra={"job_id": job_id, "community_id": str(validated_payload.community_id)},
                    )
                    return _skipped("join_not_allowed", validated_payload.community_id)
            if not await has_engagement_target_permission(
                session,
                community_id=validated_payload.community_id,
                permission="join",
            ):
                LOGGER.info(
                    "Skipping community join because target approval is missing",
                    extra={"job_id": job_id, "community_id": str(validated_payload.community_id)},
                )
                return _skipped("engagement_target_join_not_approved", validated_payload.community_id)
            if community.status not in {CommunityStatus.APPROVED.value, CommunityStatus.MONITORING.value}:
                LOGGER.info(
                    "Skipping community join because community is not approved",
                    extra={"job_id": job_id, "community_id": str(validated_payload.community_id)},
                )
                return _skipped("community_not_approved", validated_payload.community_id)

            preferred_account_id = await _preferred_account_id(
                session,
                payload_account_id=validated_payload.telegram_account_id,
                settings_account_id=settings.assigned_account_id,
                community_id=validated_payload.community_id,
            )
            if preferred_account_id is None:
                lease = await acquire_account_fn(
                    session,
                    job_id=job_id,
                    purpose="engagement_join",
                )
            else:
                lease = await acquire_account_by_id_fn(
                    session,
                    account_id=preferred_account_id,
                    job_id=job_id,
                    purpose="engagement_join",
                )
            await session.commit()
            LOGGER.info(
                "Acquired account for community join",
                extra={
                    "job_id": job_id,
                    "community_id": str(validated_payload.community_id),
                    "telegram_account_id": str(lease.account_id),
                },
            )

            await mark_join_requested(
                session,
                community_id=validated_payload.community_id,
                telegram_account_id=lease.account_id,
            )
            action = _new_join_action(
                community_id=validated_payload.community_id,
                telegram_account_id=lease.account_id,
            )
            session.add(action)
            await session.commit()

            adapter = adapter_factory(lease)
            result = await adapter.join_community(
                session_file_path=lease.session_file_path,
                community=community,
            )
            LOGGER.info(
                "Completed community join attempt",
                extra={
                    "job_id": job_id,
                    "community_id": str(validated_payload.community_id),
                    "telegram_account_id": str(lease.account_id),
                    "join_status": result.status,
                    "join_error": result.error_message,
                },
            )
            if result.status in {"joined", "already_joined"}:
                await adapter.read_recent_messages_after_join(
                    session_file_path=lease.session_file_path,
                    community=community,
                )
            await _record_join_result(
                session,
                payload=validated_payload,
                lease=lease,
                action=action,
                result=result,
            )
            await session.commit()
            if result.status in {"joined", "already_joined"}:
                enqueue_detect_fn(
                    validated_payload.community_id,
                    window_minutes=60,
                    requested_by=validated_payload.requested_by,
                )
        except EngagementAccountRateLimited as exc:
            LOGGER.warning(
                "Community join hit a rate limit",
                extra={
                    "job_id": job_id,
                    "community_id": str(validated_payload.community_id),
                    "telegram_account_id": None if lease is None else str(lease.account_id),
                    "error": str(exc),
                },
            )
            await session.rollback()
            if lease is not None:
                await _record_failed_join(
                    session,
                    community_id=validated_payload.community_id,
                    account_id=lease.account_id,
                    action=action,
                    membership_status=CommunityAccountMembershipStatus.FAILED.value,
                    error_message=str(exc),
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
            LOGGER.warning(
                "Community join found a banned or unauthorized account",
                extra={
                    "job_id": job_id,
                    "community_id": str(validated_payload.community_id),
                    "telegram_account_id": None if lease is None else str(lease.account_id),
                    "error": str(exc),
                },
            )
            await session.rollback()
            if lease is not None:
                await _record_failed_join(
                    session,
                    community_id=validated_payload.community_id,
                    account_id=lease.account_id,
                    action=action,
                    membership_status=CommunityAccountMembershipStatus.BANNED.value,
                    error_message=str(exc),
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
        except Exception as exc:
            LOGGER.exception(
                "Community join failed unexpectedly",
                extra={
                    "job_id": job_id,
                    "community_id": str(validated_payload.community_id),
                    "telegram_account_id": None if lease is None else str(lease.account_id),
                },
            )
            await session.rollback()
            if lease is not None:
                await _record_failed_join(
                    session,
                    community_id=validated_payload.community_id,
                    account_id=lease.account_id,
                    action=action,
                    membership_status=CommunityAccountMembershipStatus.FAILED.value,
                    error_message=str(exc),
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
        else:
            if lease is not None:
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="success",
                )
                await session.commit()
            LOGGER.info(
                "Finished community join job",
                extra={
                    "job_id": job_id,
                    "community_id": str(validated_payload.community_id),
                    "telegram_account_id": None if lease is None else str(lease.account_id),
                    "action_status": None if action is None else action.status,
                },
            )
            return _join_summary(validated_payload, lease, action)
        finally:
            if adapter is not None and hasattr(adapter, "aclose"):
                await adapter.aclose()  # type: ignore[attr-defined]


def run_community_join_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_community_join(payload))


async def _preferred_account_id(
    session: AsyncSession,
    *,
    payload_account_id: uuid.UUID | None,
    settings_account_id: uuid.UUID | None,
    community_id: uuid.UUID,
) -> uuid.UUID | None:
    if payload_account_id is not None:
        return payload_account_id
    if settings_account_id is not None:
        return settings_account_id
    joined_membership = await get_joined_membership_for_send(session, community_id=community_id)
    if joined_membership is not None:
        return joined_membership.telegram_account_id
    return None


async def _record_join_result(
    session: AsyncSession,
    *,
    payload: CommunityJoinPayload,
    lease: AccountLease,
    action: EngagementAction,
    result: JoinResult,
) -> None:
    if result.status in {"joined", "already_joined"}:
        await mark_join_result(
            session,
            community_id=payload.community_id,
            telegram_account_id=lease.account_id,
            status=CommunityAccountMembershipStatus.JOINED.value,
            joined_at=result.joined_at or _utcnow(),
            error_message=None,
        )
        action.status = EngagementActionStatus.SENT.value
        action.sent_at = result.joined_at or _utcnow()
        action.error_message = None
    else:
        await mark_join_result(
            session,
            community_id=payload.community_id,
            telegram_account_id=lease.account_id,
            status=CommunityAccountMembershipStatus.FAILED.value,
            joined_at=None,
            error_message=result.error_message,
        )
        action.status = EngagementActionStatus.SKIPPED.value
        action.error_message = result.error_message or "Community is inaccessible"
    action.updated_at = _utcnow()


async def _record_failed_join(
    session: AsyncSession,
    *,
    community_id: uuid.UUID,
    account_id: uuid.UUID,
    action: EngagementAction | None,
    membership_status: str,
    error_message: str,
) -> None:
    await mark_join_result(
        session,
        community_id=community_id,
        telegram_account_id=account_id,
        status=membership_status,
        joined_at=None,
        error_message=error_message,
    )
    if action is not None:
        action.status = EngagementActionStatus.FAILED.value
        action.error_message = error_message
        action.updated_at = _utcnow()


def _new_join_action(
    *,
    community_id: uuid.UUID,
    telegram_account_id: uuid.UUID,
) -> EngagementAction:
    now = _utcnow()
    return EngagementAction(
        id=uuid.uuid4(),
        community_id=community_id,
        telegram_account_id=telegram_account_id,
        action_type=EngagementActionType.JOIN.value,
        status=EngagementActionStatus.QUEUED.value,
        scheduled_at=now,
        created_at=now,
        updated_at=now,
    )


def _join_summary(
    payload: CommunityJoinPayload,
    lease: AccountLease | None,
    action: EngagementAction | None,
) -> dict[str, object]:
    action_status = action.status if action is not None else EngagementActionStatus.SKIPPED.value
    status = "processed"
    if action_status == EngagementActionStatus.SKIPPED.value:
        status = "skipped"
    return {
        "status": status,
        "job_type": "community.join",
        "community_id": str(payload.community_id),
        "telegram_account_id": str(lease.account_id) if lease is not None else None,
        "action_status": action_status,
    }


def _skipped(reason: str, community_id: uuid.UUID) -> dict[str, object]:
    return {
        "status": "skipped",
        "job_type": "community.join",
        "community_id": str(community_id),
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
