from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.services.seed_resolution import SeedResolutionSummary
from backend.services.seed_resolution import SeedResolutionRowResult
from backend.workers.account_manager import AccountLease
from backend.workers.seed_resolve import process_seed_resolve


@pytest.mark.asyncio
async def test_seed_resolve_worker_releases_account_on_success() -> None:
    seed_group_id = uuid4()
    account_id = uuid4()
    session = FakeSession()
    releases: list[dict[str, object]] = []

    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        assert session_arg is session
        assert purpose == "expansion"
        return AccountLease(
            account_id=account_id,
            phone="+123456789",
            session_file_path="session",
            lease_owner=job_id,
            lease_expires_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        )

    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        assert session_arg is session
        releases.append(kwargs)

    async def fake_resolve_seed_group(*args: object, **kwargs: object) -> SeedResolutionSummary:
        return SeedResolutionSummary(seed_group_id=seed_group_id)

    result = await process_seed_resolve(
        {
            "seed_group_id": str(seed_group_id),
            "requested_by": "operator",
            "limit": 10,
            "retry_failed": False,
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        resolver_factory=lambda lease: FakeResolver(),
        repository_factory=lambda session_arg: object(),
        resolve_seed_group_fn=fake_resolve_seed_group,
        enqueue_snapshot_fn=lambda *args, **kwargs: None,
    )

    assert result["status"] == "processed"
    assert session.commits == 3
    assert session.rollbacks == 0
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_seed_resolve_worker_releases_account_on_error() -> None:
    seed_group_id = uuid4()
    account_id = uuid4()
    session = FakeSession()
    releases: list[dict[str, object]] = []

    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        return AccountLease(
            account_id=account_id,
            phone="+123456789",
            session_file_path="session",
            lease_owner=job_id,
            lease_expires_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        )

    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        releases.append(kwargs)

    async def fake_resolve_seed_group(*args: object, **kwargs: object) -> SeedResolutionSummary:
        raise RuntimeError("resolver exploded")

    with pytest.raises(RuntimeError, match="resolver exploded"):
        await process_seed_resolve(
            {
                "seed_group_id": str(seed_group_id),
                "requested_by": "operator",
                "limit": 10,
                "retry_failed": False,
            },
            session_factory=lambda: session,
            acquire_account_fn=fake_acquire,
            release_account_fn=fake_release,
            resolver_factory=lambda lease: FakeResolver(),
            repository_factory=lambda session_arg: object(),
            resolve_seed_group_fn=fake_resolve_seed_group,
            enqueue_snapshot_fn=lambda *args, **kwargs: None,
        )

    assert session.commits == 2
    assert session.rollbacks == 1
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "error"
    assert releases[0]["error_message"] == "resolver exploded"


@pytest.mark.asyncio
async def test_seed_resolve_worker_queues_snapshot_for_resolved_communities() -> None:
    seed_group_id = uuid4()
    community_id = uuid4()
    account_id = uuid4()
    session = FakeSession()
    queued: list[dict[str, object]] = []

    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        return AccountLease(
            account_id=account_id,
            phone="+123456789",
            session_file_path="session",
            lease_owner=job_id,
            lease_expires_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        )

    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        return None

    async def fake_resolve_seed_group(*args: object, **kwargs: object) -> SeedResolutionSummary:
        summary = SeedResolutionSummary(seed_group_id=seed_group_id)
        summary.results.append(
            SeedResolutionRowResult(
                seed_channel_id=uuid4(),
                username="seed",
                status="resolved",
                community_id=community_id,
            )
        )
        summary.results.append(
            SeedResolutionRowResult(
                seed_channel_id=uuid4(),
                username="seed_duplicate",
                status="resolved",
                community_id=community_id,
            )
        )
        return summary

    def fake_enqueue_snapshot(*args: object, **kwargs: object) -> object:
        queued.append({"args": args, "kwargs": kwargs})
        return type(
            "QueuedJob",
            (),
            {"id": "snapshot-1", "type": "community.snapshot", "status": "queued"},
        )()

    result = await process_seed_resolve(
        {
            "seed_group_id": str(seed_group_id),
            "requested_by": "operator",
            "limit": 10,
            "retry_failed": False,
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        resolver_factory=lambda lease: FakeResolver(),
        repository_factory=lambda session_arg: object(),
        resolve_seed_group_fn=fake_resolve_seed_group,
        enqueue_snapshot_fn=fake_enqueue_snapshot,
    )

    assert result["snapshot_jobs"] == [
        {"id": "snapshot-1", "type": "community.snapshot", "status": "queued"}
    ]
    assert len(queued) == 1
    assert queued[0]["args"] == (community_id,)
    assert queued[0]["kwargs"] == {"reason": "initial", "requested_by": "operator"}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeResolver:
    async def aclose(self) -> None:
        return None
