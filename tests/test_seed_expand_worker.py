from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.services.seed_expansion import SeedExpansionSummary
from backend.workers.account_manager import AccountLease
from backend.workers.seed_expand import process_seed_expand


@pytest.mark.asyncio
async def test_seed_expand_worker_releases_account_on_success() -> None:
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

    async def fake_expand_seed_group(*args: object, **kwargs: object) -> SeedExpansionSummary:
        return SeedExpansionSummary(seed_group_id=seed_group_id)

    result = await process_seed_expand(
        {
            "seed_group_id": str(seed_group_id),
            "brief_id": None,
            "depth": 1,
            "requested_by": "operator",
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        adapter_factory=lambda lease: FakeAdapter(),
        repository_factory=lambda session_arg: object(),
        expand_seed_group_fn=fake_expand_seed_group,
    )

    assert result["status"] == "processed"
    assert result["job_type"] == "seed.expand"
    assert session.commits == 3
    assert session.rollbacks == 0
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_seed_expand_worker_releases_account_on_error() -> None:
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

    async def fake_expand_seed_group(*args: object, **kwargs: object) -> SeedExpansionSummary:
        raise RuntimeError("expansion exploded")

    with pytest.raises(RuntimeError, match="expansion exploded"):
        await process_seed_expand(
            {
                "seed_group_id": str(seed_group_id),
                "brief_id": None,
                "depth": 1,
                "requested_by": "operator",
            },
            session_factory=lambda: session,
            acquire_account_fn=fake_acquire,
            release_account_fn=fake_release,
            adapter_factory=lambda lease: FakeAdapter(),
            repository_factory=lambda session_arg: object(),
            expand_seed_group_fn=fake_expand_seed_group,
        )

    assert session.commits == 2
    assert session.rollbacks == 1
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "error"
    assert releases[0]["error_message"] == "expansion exploded"


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


class FakeAdapter:
    async def aclose(self) -> None:
        return None
