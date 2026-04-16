from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import SeedExpandPayload
from backend.services.seed_expansion import (
    ExpansionAccountBanned,
    ExpansionAccountRateLimited,
    SeedExpansionAdapter,
    SeedExpansionRepository,
    SeedExpansionSummary,
    SqlAlchemySeedExpansionRepository,
    expand_seed_group,
)
from backend.workers.account_manager import AccountLease, acquire_account, release_account
from backend.workers.telegram_expansion import TelethonSeedExpansionAdapter


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
ExpansionAdapterFactory = Callable[[AccountLease], SeedExpansionAdapter]
RepositoryFactory = Callable[[AsyncSession], SeedExpansionRepository]
ExpandSeedGroupFn = Callable[..., Any]


async def process_seed_expand(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    adapter_factory: ExpansionAdapterFactory = TelethonSeedExpansionAdapter,
    repository_factory: RepositoryFactory = SqlAlchemySeedExpansionRepository,
    expand_seed_group_fn: ExpandSeedGroupFn = expand_seed_group,
) -> dict[str, object]:
    validated_payload = SeedExpandPayload.model_validate(payload)
    job_id = _current_job_id() or f"seed.expand:{validated_payload.seed_group_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        adapter: SeedExpansionAdapter | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="expansion")
            await session.commit()

            adapter = adapter_factory(lease)
            summary: SeedExpansionSummary = await expand_seed_group_fn(
                repository_factory(session),
                seed_group_id=validated_payload.seed_group_id,
                brief_id=validated_payload.brief_id,
                depth=validated_payload.depth,
                requested_by=validated_payload.requested_by,
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


def run_seed_expand_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_seed_expand(payload))


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)
