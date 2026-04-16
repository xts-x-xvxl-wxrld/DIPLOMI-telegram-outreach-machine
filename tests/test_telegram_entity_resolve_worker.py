from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.services.telegram_entity_intake import TelegramEntityResolveSummary
from backend.workers.account_manager import AccountLease
from backend.workers.telegram_entity_resolve import process_telegram_entity_resolve


@pytest.mark.asyncio
async def test_telegram_entity_resolve_worker_releases_account_on_success() -> None:
    intake_id = uuid4()
    account_id = uuid4()
    session = FakeSession()
    releases: list[dict[str, object]] = []

    async def fake_acquire(session_arg: FakeSession, *, job_id: str, purpose: str) -> AccountLease:
        assert session_arg is session
        assert purpose == "entity_intake"
        return AccountLease(
            account_id=account_id,
            phone="+123456789",
            session_file_path="session",
            lease_owner=job_id,
            lease_expires_at=datetime(2026, 4, 16, tzinfo=timezone.utc),
        )

    async def fake_release(session_arg: FakeSession, **kwargs: object) -> None:
        assert session_arg is session
        releases.append(kwargs)

    async def fake_resolve_intake(*args: object, **kwargs: object) -> TelegramEntityResolveSummary:
        return TelegramEntityResolveSummary(
            intake_id=intake_id,
            status="resolved",
            entity_type="channel",
        )

    result = await process_telegram_entity_resolve(
        {"intake_id": str(intake_id), "requested_by": "telegram_bot"},
        session_factory=lambda: session,
        acquire_account_fn=fake_acquire,
        release_account_fn=fake_release,
        resolver_factory=lambda lease: FakeResolver(),
        repository_factory=lambda session_arg: object(),
        resolve_intake_fn=fake_resolve_intake,
    )

    assert result["status"] == "resolved"
    assert result["entity_type"] == "channel"
    assert session.commits == 3
    assert session.rollbacks == 0
    assert releases[0]["account_id"] == account_id
    assert releases[0]["outcome"] == "success"


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
