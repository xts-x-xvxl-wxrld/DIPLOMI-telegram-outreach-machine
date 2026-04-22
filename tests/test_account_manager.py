from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.db.enums import AccountPool, AccountStatus
from backend.workers.account_manager import (
    ACCOUNT_PURPOSES,
    account_pool_for_purpose,
    mask_phone,
    release_updates,
    validate_account_purpose,
)


def test_account_purposes_match_worker_contract() -> None:
    assert ACCOUNT_PURPOSES == (
        "expansion",
        "community_snapshot",
        "collection",
        "entity_intake",
        "search_retrieve",
        "engagement_target_resolve",
        "engagement_join",
        "engagement_send",
    )


def test_validate_account_purpose_accepts_engagement_purposes() -> None:
    assert validate_account_purpose("engagement_target_resolve") == "engagement_target_resolve"
    assert validate_account_purpose("engagement_join") == "engagement_join"
    assert validate_account_purpose("engagement_send") == "engagement_send"


def test_validate_account_purpose_rejects_unknown_purpose() -> None:
    with pytest.raises(ValueError, match="purpose must be one of"):
        validate_account_purpose("engagement_detect")


@pytest.mark.parametrize(
    ("purpose", "expected_pool"),
    [
        ("expansion", AccountPool.SEARCH),
        ("community_snapshot", AccountPool.SEARCH),
        ("collection", AccountPool.SEARCH),
        ("entity_intake", AccountPool.SEARCH),
        ("search_retrieve", AccountPool.SEARCH),
        ("engagement_target_resolve", AccountPool.SEARCH),
        ("engagement_join", AccountPool.ENGAGEMENT),
        ("engagement_send", AccountPool.ENGAGEMENT),
    ],
)
def test_account_purpose_maps_to_required_pool(purpose: str, expected_pool: AccountPool) -> None:
    assert account_pool_for_purpose(purpose) == expected_pool


def test_no_account_purpose_maps_to_disabled_pool() -> None:
    assert {account_pool_for_purpose(purpose) for purpose in ACCOUNT_PURPOSES} == {
        AccountPool.SEARCH,
        AccountPool.ENGAGEMENT,
    }


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


def test_release_banned_marks_account_unusable() -> None:
    updates = release_updates(outcome="banned", error_message="session revoked")

    assert updates["status"] == AccountStatus.BANNED.value
    assert updates["lease_owner"] is None
    assert updates["lease_expires_at"] is None
    assert updates["last_error"] == "session revoked"


def test_mask_phone_hides_middle_digits() -> None:
    assert mask_phone("+123456789") == "+123****89"
    assert mask_phone("1234") == "****"
