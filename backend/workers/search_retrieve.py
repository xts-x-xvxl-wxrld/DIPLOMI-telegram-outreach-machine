from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import AsyncSessionLocal
from backend.queue.client import enqueue_search_rank
from backend.queue.payloads import SearchRetrievePayload
from backend.services.search_retrieval import (
    SearchRetrievalSummary,
    SqlAlchemySearchRetrievalRepository,
    TelegramEntitySearchAdapter,
    TelegramEntitySearchError,
    mark_search_query_failed,
    retrieve_search_query,
)
from backend.services.seed_resolution import ResolverAccountBanned, ResolverAccountRateLimited
from backend.workers.account_manager import AccountLease, acquire_account, release_account
from backend.workers.telegram_entity_search import TelethonTelegramEntitySearchAdapter


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
AdapterFactory = Callable[[AccountLease], TelegramEntitySearchAdapter]
RetrieveSearchQueryFn = Callable[..., Any]
MarkSearchQueryFailedFn = Callable[..., Any]


async def process_search_retrieve(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    adapter_factory: AdapterFactory = TelethonTelegramEntitySearchAdapter,
    retrieve_search_query_fn: RetrieveSearchQueryFn = retrieve_search_query,
    mark_search_query_failed_fn: MarkSearchQueryFailedFn = mark_search_query_failed,
) -> dict[str, object]:
    validated_payload = SearchRetrievePayload.model_validate(payload)
    job_id = _current_job_id() or f"search.retrieve:{validated_payload.search_run_id}:{validated_payload.search_query_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        adapter: TelegramEntitySearchAdapter | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="search_retrieve")
            await session.commit()

            adapter = adapter_factory(lease)
            summary: SearchRetrievalSummary = await retrieve_search_query_fn(
                SqlAlchemySearchRetrievalRepository(session),
                search_run_id=validated_payload.search_run_id,
                search_query_id=validated_payload.search_query_id,
                adapter=adapter,
                requested_by=validated_payload.requested_by,
                enqueue_search_rank_fn=enqueue_search_rank,
            )
            await session.commit()
        except ResolverAccountRateLimited as exc:
            await session.rollback()
            summary = await _mark_query_failed(
                session,
                validated_payload=validated_payload,
                error_message=str(exc),
                mark_search_query_failed_fn=mark_search_query_failed_fn,
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
            return summary.to_dict()
        except (ResolverAccountBanned, TelegramEntitySearchError) as exc:
            await session.rollback()
            summary = await _mark_query_failed(
                session,
                validated_payload=validated_payload,
                error_message=str(exc),
                mark_search_query_failed_fn=mark_search_query_failed_fn,
            )
            if lease is not None:
                await release_account_fn(
                    session,
                    account_id=lease.account_id,
                    job_id=job_id,
                    outcome="banned" if isinstance(exc, ResolverAccountBanned) else "error",
                    error_message=str(exc),
                )
                await session.commit()
            return summary.to_dict()
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


def run_search_retrieve_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_search_retrieve(payload))


async def _mark_query_failed(
    session: AsyncSession,
    *,
    validated_payload: SearchRetrievePayload,
    error_message: str,
    mark_search_query_failed_fn: MarkSearchQueryFailedFn,
) -> SearchRetrievalSummary:
    summary: SearchRetrievalSummary = await mark_search_query_failed_fn(
        SqlAlchemySearchRetrievalRepository(session),
        search_run_id=validated_payload.search_run_id,
        search_query_id=validated_payload.search_query_id,
        error_message=error_message,
        requested_by=validated_payload.requested_by,
        enqueue_search_rank_fn=enqueue_search_rank,
    )
    await session.commit()
    return summary


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)


__all__ = ["process_search_retrieve", "run_search_retrieve_job"]
