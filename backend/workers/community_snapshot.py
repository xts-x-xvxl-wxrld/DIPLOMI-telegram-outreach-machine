from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.queue.payloads import CommunitySnapshotPayload
from backend.services.community_snapshot import (
    CommunitySnapshotJobSummary,
    CommunitySnapshotRepository,
    SnapshotAccountBanned,
    SnapshotAccountRateLimited,
    SqlAlchemyCommunitySnapshotRepository,
    TelegramCommunitySnapshotter,
    record_snapshot_failure,
    snapshot_community,
)
from backend.workers.account_manager import AccountLease, acquire_account, release_account
from backend.workers.telegram_snapshot import TelethonCommunitySnapshotter


class AsyncSessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession:
        pass

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> object:
        pass


AcquireAccountFn = Callable[..., Any]
ReleaseAccountFn = Callable[..., Any]
SnapshotterFactory = Callable[[AccountLease], TelegramCommunitySnapshotter]
RepositoryFactory = Callable[[AsyncSession], CommunitySnapshotRepository]
SnapshotCommunityFn = Callable[..., Any]


async def process_community_snapshot(
    payload: dict[str, Any],
    *,
    session_factory: Callable[[], AsyncSessionContext] = AsyncSessionLocal,
    acquire_account_fn: AcquireAccountFn = acquire_account,
    release_account_fn: ReleaseAccountFn = release_account,
    snapshotter_factory: SnapshotterFactory = TelethonCommunitySnapshotter,
    repository_factory: RepositoryFactory = SqlAlchemyCommunitySnapshotRepository,
    snapshot_community_fn: SnapshotCommunityFn = snapshot_community,
    settings: Settings | None = None,
) -> dict[str, object]:
    validated_payload = CommunitySnapshotPayload.model_validate(payload)
    runtime_settings = settings or get_settings()
    job_id = _current_job_id() or f"community.snapshot:{validated_payload.community_id}"

    async with session_factory() as session:
        lease: AccountLease | None = None
        snapshotter: TelegramCommunitySnapshotter | None = None
        try:
            lease = await acquire_account_fn(session, job_id=job_id, purpose="community_snapshot")
            await session.commit()

            snapshotter = snapshotter_factory(lease)
            summary: CommunitySnapshotJobSummary = await snapshot_community_fn(
                repository_factory(session),
                community_id=validated_payload.community_id,
                snapshotter=snapshotter,
                window_days=validated_payload.window_days,
                member_limit=runtime_settings.telegram_member_import_limit,
            )
            await session.commit()
        except SnapshotAccountRateLimited as exc:
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
        except SnapshotAccountBanned as exc:
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
            failure_summary = await record_snapshot_failure(
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
            if snapshotter is not None and hasattr(snapshotter, "aclose"):
                await snapshotter.aclose()  # type: ignore[attr-defined]


def run_community_snapshot_job(payload: dict[str, Any]) -> dict[str, object]:
    return asyncio.run(process_community_snapshot(payload))


def _current_job_id() -> str | None:
    try:
        from rq import get_current_job
    except Exception:
        return None

    job = get_current_job()
    if job is None:
        return None
    return str(job.id)
