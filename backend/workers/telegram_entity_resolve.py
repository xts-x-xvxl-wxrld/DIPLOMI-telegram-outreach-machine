from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import TelegramEntityResolvePayload
from backend.services.seed_resolution import ResolverAccountBanned, ResolverAccountRateLimited
from backend.services.telegram_entity_intake import (
    SqlAlchemyTelegramEntityIntakeRepository,
    TelegramEntityIntakeRepository,
    TelegramEntityResolveSummary,
    TelegramEntityResolverAdapter,
    resolve_telegram_entity_intake,
)
from backend.workers.account_manager import AccountLease, acquire_account, release_account
from backend.workers.telegram_entity_resolver import TelethonTelegramEntityResolver


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
ResolverFactory = Callable[[AccountLease], TelegramEntityResolverAdapter]
RepositoryFactory = Callable[[AsyncSession], TelegramEntityIntakeRepository]
ResolveTelegramEntityIntakeFn = Callable[..., Any]


async def process_telegram_entity_resolve(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    resolver_factory: ResolverFactory = TelethonTelegramEntityResolver,
    repository_factory: RepositoryFactory = SqlAlchemyTelegramEntityIntakeRepository,
    resolve_intake_fn: ResolveTelegramEntityIntakeFn = resolve_telegram_entity_intake,
) -> dict[str, object]:
    validated_payload = TelegramEntityResolvePayload.model_validate(payload)
    job_id = _current_job_id() or f"telegram_entity.resolve:{validated_payload.intake_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        resolver: TelegramEntityResolverAdapter | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="entity_intake")
            await session.commit()

            resolver = resolver_factory(lease)
            summary: TelegramEntityResolveSummary = await resolve_intake_fn(
                repository_factory(session),
                intake_id=validated_payload.intake_id,
                resolver=resolver,
            )
            await session.commit()
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
            return summary.to_dict()
        finally:
            if resolver is not None and hasattr(resolver, "aclose"):
                await resolver.aclose()  # type: ignore[attr-defined]


def run_telegram_entity_resolve_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_telegram_entity_resolve(payload))


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)
