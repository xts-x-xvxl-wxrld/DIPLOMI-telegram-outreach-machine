from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import CollectionPayload
from backend.services.community_collection import (
    CollectorAccountBanned,
    CollectorAccountRateLimited,
    CommunityCollectionRepository,
    CommunityCollectionSummary,
    SqlAlchemyCommunityCollectionRepository,
    TelegramCommunityCollector,
    collect_community,
    record_collection_failure,
)
from backend.workers.account_manager import AccountLease, acquire_account, release_account
from backend.workers.telegram_collection import TelethonCommunityCollector


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
CollectorFactory = Callable[[AccountLease], TelegramCommunityCollector]
RepositoryFactory = Callable[[AsyncSession], CommunityCollectionRepository]
CollectCommunityFn = Callable[..., Any]


async def process_collection(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    collector_factory: CollectorFactory = TelethonCommunityCollector,
    repository_factory: RepositoryFactory = SqlAlchemyCommunityCollectionRepository,
    collect_community_fn: CollectCommunityFn = collect_community,
    settings: Settings | None = None,
) -> dict[str, object]:
    validated_payload = CollectionPayload.model_validate(payload)
    runtime_settings = settings or get_settings()
    job_id = _current_job_id() or f"collection:{validated_payload.community_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        collector: TelegramCommunityCollector | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="collection")
            await session.commit()

            collector = collector_factory(lease)
            summary: CommunityCollectionSummary = await collect_community_fn(
                repository_factory(session),
                community_id=validated_payload.community_id,
                collector=collector,
                window_days=validated_payload.window_days,
                member_limit=runtime_settings.telegram_member_import_limit,
            )
            await session.commit()
        except CollectorAccountRateLimited as exc:
            await session.rollback()
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
            raise
        except CollectorAccountBanned as exc:
            await session.rollback()
            if lease is not None:
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
            await session.rollback()
            failure_summary = await record_collection_failure(
                repository_factory(session),
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
            return summary.to_dict()
        finally:
            if collector is not None and hasattr(collector, "aclose"):
                await collector.aclose()  # type: ignore[attr-defined]


def run_collection_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_collection(payload))


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)
