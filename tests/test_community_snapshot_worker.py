from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.services.community_snapshot import CommunitySnapshotJobSummary
from backend.workers.account_manager import AccountLease
from backend.workers.community_snapshot import process_community_snapshot


@pytest.mark.asyncio
async def test_snapshot_worker_releases_account_on_success() -> None:
    community_id = uuid4()
    account_id = uuid4()
    session = FakeSession()
    releases: list[dict[str, object]] = []

    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        assert session_arg is session
        assert purpose == "community_snapshot"
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

    async def fake_snapshot_community(*args: object, **kwargs: object) -> CommunitySnapshotJobSummary:
        assert kwargs["member_limit"] == 123
        return CommunitySnapshotJobSummary(
            community_id=community_id,
            collection_run_id=uuid4(),
            snapshot_id=uuid4(),
            members_seen=2,
            member_limit_reached=False,
            status="completed",
        )

    result = await process_community_snapshot(
        {
            "community_id": str(community_id),
            "reason": "initial",
            "requested_by": "operator",
            "window_days": 90,
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        snapshotter_factory=lambda lease: FakeSnapshotter(),
        repository_factory=lambda session_arg: object(),
        snapshot_community_fn=fake_snapshot_community,
        settings=FakeSettings(member_limit=123),
    )

    assert result["status"] == "completed"
    assert result["members_seen"] == 2
    assert session.commits == 3
    assert session.rollbacks == 0
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_snapshot_worker_records_failure_and_releases_account() -> None:
    community_id = uuid4()
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

    async def fake_snapshot_community(*args: object, **kwargs: object) -> CommunitySnapshotJobSummary:
        raise RuntimeError("snapshot exploded")

    result = await process_community_snapshot(
        {
            "community_id": str(community_id),
            "reason": "initial",
            "requested_by": "operator",
            "window_days": 90,
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        snapshotter_factory=lambda lease: FakeSnapshotter(),
        repository_factory=lambda session_arg: FakeFailureRepository(community_id),
        snapshot_community_fn=fake_snapshot_community,
        settings=FakeSettings(member_limit=10000),
    )

    assert result["status"] == "failed"
    assert result["error_message"] == "snapshot exploded"
    assert session.commits == 2
    assert session.rollbacks == 1
    assert releases[0]["outcome"] == "error"
    assert releases[0]["error_message"] == "snapshot exploded"


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


class FakeSnapshotter:
    async def aclose(self) -> None:
        return None


class FakeSettings:
    def __init__(self, *, member_limit: int) -> None:
        self.telegram_member_import_limit = member_limit


class FakeFailureRepository:
    def __init__(self, community_id: object) -> None:
        self.community_id = community_id

    async def get_community(self, community_id: object) -> object | None:
        if community_id == self.community_id:
            return type("Community", (), {"id": community_id, "brief_id": None})()
        return None

    async def add_collection_run(self, collection_run: object) -> None:
        return None

    async def flush(self) -> None:
        return None
