from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.db.enums import AccountPool, AccountStatus
from backend.db.models import TelegramAccount
from backend.workers.account_health_refresh import (
    account_health_refresh_skip_reason,
    apply_account_health_refresh_outcome,
)


def test_account_health_refresh_skips_disabled_pool() -> None:
    account = _account(account_pool=AccountPool.DISABLED.value)

    assert account_health_refresh_skip_reason(account, now=_now()) == "disabled"


def test_account_health_refresh_skips_active_lease() -> None:
    account = _account(
        status=AccountStatus.IN_USE.value,
        lease_owner="collection:1",
        lease_expires_at=_now() + timedelta(minutes=5),
    )

    assert account_health_refresh_skip_reason(account, now=_now()) == "in_use"


def test_account_health_refresh_allows_expired_lease_after_recovery() -> None:
    account = _account(
        status=AccountStatus.AVAILABLE.value,
        lease_owner="collection:1",
        lease_expires_at=_now() - timedelta(minutes=1),
    )

    assert account_health_refresh_skip_reason(account, now=_now()) is None


def test_healthy_refresh_makes_elapsed_rate_limited_account_available() -> None:
    account = _account(
        status=AccountStatus.RATE_LIMITED.value,
        flood_wait_until=_now() - timedelta(minutes=1),
        last_error="old flood wait",
    )

    apply_account_health_refresh_outcome(account, outcome="healthy", now=_now())

    assert account.status == AccountStatus.AVAILABLE.value
    assert account.flood_wait_until is None
    assert account.last_error is None


def test_flood_wait_refresh_maps_account_to_rate_limited() -> None:
    now = _now()
    account = _account()

    apply_account_health_refresh_outcome(
        account,
        outcome="rate_limited",
        now=now,
        flood_wait_seconds=120,
        error_message="wait",
    )

    assert account.status == AccountStatus.RATE_LIMITED.value
    assert account.flood_wait_until == now + timedelta(seconds=120)
    assert account.last_error == "wait"


def test_flood_wait_refresh_requires_wait_seconds() -> None:
    with pytest.raises(ValueError, match="flood_wait_seconds is required"):
        apply_account_health_refresh_outcome(_account(), outcome="rate_limited", now=_now())


def test_banned_refresh_marks_account_unusable() -> None:
    account = _account(flood_wait_until=_now() + timedelta(hours=1))

    apply_account_health_refresh_outcome(
        account,
        outcome="banned",
        now=_now(),
        error_message="session revoked",
    )

    assert account.status == AccountStatus.BANNED.value
    assert account.flood_wait_until is None
    assert account.last_error == "session revoked"


def test_generic_refresh_error_preserves_existing_status() -> None:
    account = _account(status=AccountStatus.BANNED.value)

    apply_account_health_refresh_outcome(
        account,
        outcome="error",
        now=_now(),
        error_message="temporary network failure",
    )

    assert account.status == AccountStatus.BANNED.value
    assert account.last_error == "temporary network failure"


def _account(
    *,
    status: str = AccountStatus.AVAILABLE.value,
    account_pool: str = AccountPool.ENGAGEMENT.value,
    flood_wait_until: datetime | None = None,
    lease_owner: str | None = None,
    lease_expires_at: datetime | None = None,
    last_error: str | None = None,
) -> TelegramAccount:
    return TelegramAccount(
        id=uuid4(),
        phone="+10000000000",
        session_file_path="engagement.session",
        account_pool=account_pool,
        status=status,
        flood_wait_until=flood_wait_until,
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        last_error=last_error,
    )


def _now() -> datetime:
    return datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
