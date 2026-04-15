from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.db.enums import AccountStatus
from backend.workers.account_manager import mask_phone, release_updates


def test_release_success_clears_lease_and_error() -> None:
    updates = release_updates(outcome="success", error_message="old")

    assert updates["status"] == AccountStatus.AVAILABLE.value
    assert updates["lease_owner"] is None
    assert updates["lease_expires_at"] is None
    assert updates["last_error"] is None
    assert updates["flood_wait_until"] is None


def test_release_rate_limited_requires_wait_seconds() -> None:
    with pytest.raises(ValueError):
        release_updates(outcome="rate_limited")


def test_release_rate_limited_sets_flood_wait_until() -> None:
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    updates = release_updates(outcome="rate_limited", flood_wait_seconds=60, now=now)

    assert updates["status"] == AccountStatus.RATE_LIMITED.value
    assert updates["flood_wait_until"].isoformat() == "2026-04-15T12:01:00+00:00"


def test_mask_phone_hides_middle_digits() -> None:
    assert mask_phone("+123456789") == "+123****89"
    assert mask_phone("1234") == "****"
