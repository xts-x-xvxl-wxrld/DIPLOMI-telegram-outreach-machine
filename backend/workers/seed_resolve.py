from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import AsyncSessionLocal
from backend.queue.client import QueuedJob, enqueue_collection
from backend.queue.payloads import SeedResolvePayload
from backend.services.seed_resolution import (
    ResolverAccountBanned,
    ResolverAccountRateLimited,
    SeedResolutionRepository,
    SeedResolutionSummary,
    SqlAlchemySeedResolutionRepository,
    TelegramResolverAdapter,
    resolve_seed_group,
)
from backend.workers.account_manager import (
    AccountLease,
    acquire_account,
    release_account,
)
from backend.workers.telegram_resolver import TelethonTelegramResolver


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
ResolverFactory = Callable[[AccountLease], TelegramResolverAdapter]
RepositoryFactory = Callable[[AsyncSession], SeedResolutionRepository]
ResolveSeedGroupFn = Callable[..., Any]
EnqueueCollectionFn = Callable[..., QueuedJob]


async def process_seed_resolve(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    resolver_factory: ResolverFactory = TelethonTelegramResolver,
    repository_factory: RepositoryFactory = SqlAlchemySeedResolutionRepository,
    resolve_seed_group_fn: ResolveSeedGroupFn = resolve_seed_group,
    enqueue_collection_fn: EnqueueCollectionFn = enqueue_collection,
) -> dict[str, object]:
    validated_payload = SeedResolvePayload.model_validate(payload)
    job_id = _current_job_id() or f"seed.resolve:{validated_payload.seed_group_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        resolver: TelegramResolverAdapter | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="expansion")
            await session.commit()

            resolver = resolver_factory(lease)
            summary: SeedResolutionSummary = await resolve_seed_group_fn(
                repository_factory(session),
                seed_group_id=validated_payload.seed_group_id,
                limit=validated_payload.limit,
                retry_failed=validated_payload.retry_failed,
                resolver=resolver,
            )
            await session.commit()
            collection_jobs, collection_enqueue_errors = _enqueue_collections_for_resolved_seeds(
                summary,
                requested_by=validated_payload.requested_by,
                enqueue_collection_fn=enqueue_collection_fn,
            )
        except ResolverAccountRateLimited as exc:
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
        except ResolverAccountBanned as exc:
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
            if lease is not None:
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
            result = summary.to_dict()
            result["collection_jobs"] = [
                {"id": job.id, "type": job.type, "status": job.status} for job in collection_jobs
            ]
            result["collection_enqueue_errors"] = collection_enqueue_errors
            return result
        finally:
            if resolver is not None and hasattr(resolver, "aclose"):
                await resolver.aclose()  # type: ignore[attr-defined]


def run_seed_resolve_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_seed_resolve(payload))


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)


def _enqueue_collections_for_resolved_seeds(
    summary: SeedResolutionSummary,
    *,
    requested_by: str,
    enqueue_collection_fn: EnqueueCollectionFn,
) -> tuple[list[QueuedJob], list[str]]:
    community_ids: list[UUID] = []
    seen: set[UUID] = set()
    for result in summary.results:
        if result.community_id is None or result.community_id in seen:
            continue
        seen.add(result.community_id)
        community_ids.append(result.community_id)

    jobs: list[QueuedJob] = []
    errors: list[str] = []
    for community_id in community_ids:
        try:
            jobs.append(
                enqueue_collection_fn(
                    community_id,
                    reason="initial",
                    requested_by=requested_by,
                )
            )
        except Exception as exc:
            errors.append(f"{community_id}: {exc}")
    return jobs, errors
