from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.services.search_expansion import SearchExpansionSummary
from backend.workers.account_manager import AccountLease
from backend.workers.search_expand import process_search_expand


@pytest.mark.asyncio
async def test_search_expand_worker_releases_account_on_success() -> None:
    search_run_id = uuid4()
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

    async def fake_expand_search_run(*args: object, **kwargs: object) -> SearchExpansionSummary:
        assert kwargs["max_neighbors_per_root"] == 25
        return SearchExpansionSummary(search_run_id=search_run_id)

    result = await process_search_expand(
        {
            "search_run_id": str(search_run_id),
            "root_search_candidate_ids": [],
            "seed_group_ids": [],
            "depth": 1,
            "requested_by": "operator",
            "max_roots": 5,
            "max_neighbors_per_root": 25,
            "max_candidates_per_adapter": 10,
        },
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        adapter_factory=lambda lease: FakeAdapter(),
        repository_factory=lambda session_arg: object(),
        expand_search_run_fn=fake_expand_search_run,
    )

    assert result["status"] == "processed"
    assert result["job_type"] == "search.expand"
    assert session.commits == 3
    assert session.rollbacks == 0
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_search_expand_worker_releases_account_on_error() -> None:
    search_run_id = uuid4()
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

    async def fake_expand_search_run(*args: object, **kwargs: object) -> SearchExpansionSummary:
        raise RuntimeError("search expansion exploded")

    with pytest.raises(RuntimeError, match="search expansion exploded"):
        await process_search_expand(
            {
                "search_run_id": str(search_run_id),
                "root_search_candidate_ids": [],
                "seed_group_ids": [],
                "depth": 1,
                "requested_by": "operator",
                "max_roots": 5,
                "max_neighbors_per_root": 25,
                "max_candidates_per_adapter": 10,
            },
            session_factory=lambda: session,
            acquire_account_fn=fake_acquire,
            release_account_fn=fake_release,
            adapter_factory=lambda lease: FakeAdapter(),
            repository_factory=lambda session_arg: object(),
            expand_search_run_fn=fake_expand_search_run,
        )

    assert session.commits == 2
    assert session.rollbacks == 1
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "error"
    assert releases[0]["error_message"] == "search expansion exploded"


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
