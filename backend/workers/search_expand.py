from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import SearchExpandPayload
from backend.services.search_expansion import (
    SearchExpansionAdapter,
    SearchExpansionRepository,
    SearchExpansionSummary,
    SqlAlchemySearchExpansionRepository,
    expand_search_run,
)
from backend.services.seed_expansion import ExpansionAccountBanned, ExpansionAccountRateLimited
from backend.workers.account_manager import AccountLease, acquire_account, release_account
from backend.workers.telegram_expansion import TelethonSeedExpansionAdapter


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
ExpansionAdapterFactory = Callable[[AccountLease], SearchExpansionAdapter]
RepositoryFactory = Callable[[AsyncSession], SearchExpansionRepository]
ExpandSearchRunFn = Callable[..., Any]


async def process_search_expand(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    adapter_factory: ExpansionAdapterFactory = TelethonSeedExpansionAdapter,
    repository_factory: RepositoryFactory = SqlAlchemySearchExpansionRepository,
    expand_search_run_fn: ExpandSearchRunFn = expand_search_run,
) -> dict[str, object]:
    validated_payload = SearchExpandPayload.model_validate(payload)
    job_id = _current_job_id() or f"search.expand:{validated_payload.search_run_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        adapter: SearchExpansionAdapter | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="expansion")
            await session.commit()

            adapter = adapter_factory(lease)
            summary: SearchExpansionSummary = await expand_search_run_fn(
                repository_factory(session),
                search_run_id=validated_payload.search_run_id,
                root_search_candidate_ids=validated_payload.root_search_candidate_ids,
                seed_group_ids=validated_payload.seed_group_ids,
                depth=validated_payload.depth,
                requested_by=validated_payload.requested_by,
                max_roots=validated_payload.max_roots,
                max_neighbors_per_root=validated_payload.max_neighbors_per_root,
                max_candidates_per_adapter=validated_payload.max_candidates_per_adapter,
                adapter=adapter,
            )
            await session.commit()
        except ExpansionAccountRateLimited as exc:
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
        except ExpansionAccountBanned as exc:
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
            return summary.to_dict()
        finally:
            if adapter is not None and hasattr(adapter, "aclose"):
                await adapter.aclose()  # type: ignore[attr-defined]


def run_search_expand_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_search_expand(payload))


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)


__all__ = ["process_search_expand", "run_search_expand_job"]
