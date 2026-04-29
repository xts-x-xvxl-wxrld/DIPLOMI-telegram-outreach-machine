from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.queue.client import enqueue_engagement_detect
from backend.queue.payloads import CollectionPayload
from backend.services.community_collection import (
    CollectionAccountBanned,
    CollectionAccountRateLimited,
    CollectionJobSummary,
    TelegramEngagementCollector,
    collect_community_engagement_messages,
    record_collection_failure,
)
from backend.services.community_engagement import (
    get_engagement_settings,
    get_joined_membership_for_send,
)
from backend.workers.account_manager import (
    AccountLease,
    acquire_account,
    acquire_account_by_id,
    release_account,
)
from backend.workers.telegram_collection import TelethonEngagementCollector


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
CollectorFactory = Callable[[AccountLease], TelegramEngagementCollector]
EnqueueDetectFn = Callable[..., Any]


async def process_collection(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    acquire_account_by_id_fn: AcquireAccountFn = acquire_account_by_id,
    release_account_fn: ReleaseAccountFn = release_account,
    collector_factory: CollectorFactory = TelethonEngagementCollector,
    enqueue_detect_fn: EnqueueDetectFn = enqueue_engagement_detect,
    settings: Settings | None = None,
) -> dict[str, object]:
    validated_payload = CollectionPayload.model_validate(payload)
    runtime_settings = settings or get_settings()
    job_id = _current_job_id() or f"collection:{validated_payload.community_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        collector: TelegramEngagementCollector | None = None
        try:
            preferred_account_id = await _preferred_collection_account_id(
                session,
                community_id=validated_payload.community_id,
            )
            if preferred_account_id is None:
                lease = await acquire_account_fn(
                    session,
                    job_id=job_id,
                    purpose="engagement_collection",
                )
            else:
                lease = await acquire_account_by_id_fn(
                    session,
                    account_id=preferred_account_id,
                    job_id=job_id,
                    purpose="engagement_collection",
                )
            await session.commit()

            collector = collector_factory(lease)
            summary = await collect_community_engagement_messages(
                session,
                community_id=validated_payload.community_id,
                collector=collector,
                reason=validated_payload.reason,
                window_days=validated_payload.window_days,
            )
            await session.commit()
        except CollectionAccountRateLimited as exc:
            await session.rollback()
            failure_summary = await record_collection_failure(
                session,
                community_id=validated_payload.community_id,
                window_days=validated_payload.window_days,
                error_message=str(exc),
            )
            if lease is not None:
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="rate_limited",
                    flood_wait_seconds=exc.flood_wait_seconds,
                    error_message=str(exc),
                )
            await session.commit()
            if failure_summary is not None:
                return failure_summary.to_dict()
            raise
        except CollectionAccountBanned as exc:
            await session.rollback()
            failure_summary = await record_collection_failure(
                session,
                community_id=validated_payload.community_id,
                window_days=validated_payload.window_days,
                error_message=str(exc),
            )
            if lease is not None:
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="banned",
                    error_message=str(exc),
                )
            await session.commit()
            if failure_summary is not None:
                return failure_summary.to_dict()
            raise
        except Exception as exc:
            await session.rollback()
            failure_summary = await record_collection_failure(
                session,
                community_id=validated_payload.community_id,
                window_days=validated_payload.window_days,
                error_message=str(exc),
            )
            if lease is not None:
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="error",
                    error_message=str(exc),
                )
            await session.commit()
            if failure_summary is not None:
                return failure_summary.to_dict()
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
            return _enqueue_detection_if_needed(
                summary,
                enqueue_detect_fn=enqueue_detect_fn,
                window_minutes=runtime_settings.engagement_detection_window_minutes,
                requested_by=validated_payload.requested_by,
            )
        finally:
            if collector is not None and hasattr(collector, "aclose"):
                await collector.aclose()  # type: ignore[attr-defined]


def run_collection_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_collection(payload))


def _enqueue_detection_if_needed(
    summary: CollectionJobSummary,
    *,
    enqueue_detect_fn: EnqueueDetectFn,
    window_minutes: int,
    requested_by: str | None,
) -> dict[str, object]:
    result = summary.to_dict()
    if not summary.should_enqueue_detection:
        return result
    job = enqueue_detect_fn(
        summary.community_id,
        collection_run_id=summary.collection_run_id,
        window_minutes=window_minutes,
        requested_by=requested_by,
    )
    result["engagement_detect_job_id"] = job.id
    result["engagement_detect_job_status"] = job.status
    return result


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)


async def _preferred_collection_account_id(
    session: AsyncSession,
    *,
    community_id: object,
) -> object | None:
    settings = await get_engagement_settings(session, community_id)
    if settings.assigned_account_id is not None:
        return settings.assigned_account_id
    membership = await get_joined_membership_for_send(session, community_id=community_id)
    if membership is not None:
        return membership.telegram_account_id
    return None


__all__ = [
    "process_collection",
    "run_collection_job",
]
