from __future__ import annotations

from pathlib import Path

import pytest

from backend.db.enums import AccountPool, AccountStatus
from backend.services.account_onboarding import build_onboarding_command
from scripts.onboard_telegram_account import (
    account_values,
    resolve_session_path,
    safe_session_file_name,
)


def test_safe_session_file_name_normalizes_phone_and_adds_extension() -> None:
    assert safe_session_file_name("+36 20 123 4567") == "36_20_123_4567.session"


@pytest.mark.parametrize("raw_value", ["../escape", "..\\escape", ""])
def test_safe_session_file_name_rejects_path_traversal(raw_value: str) -> None:
    with pytest.raises(ValueError):
        safe_session_file_name(raw_value)


def test_resolve_session_path_stays_inside_sessions_dir() -> None:
    sessions_dir = "sessions"
    path = resolve_session_path(sessions_dir, "account.session")

    assert path == (Path.cwd() / sessions_dir / "account.session").resolve()


def test_account_values_registers_available_account_without_leases() -> None:
    values = account_values(session_file_path="account.session", notes="operator-owned")

    assert values["account_pool"] == AccountPool.SEARCH.value
    assert values["status"] == AccountStatus.AVAILABLE.value
    assert values["session_file_path"] == "account.session"
    assert values["lease_owner"] is None
    assert values["last_error"] is None
    assert values["notes"] == "operator-owned"


def test_account_values_accepts_engagement_pool() -> None:
    values = account_values(
        session_file_path="engagement.session",
        account_pool=AccountPool.ENGAGEMENT.value,
        notes=None,
    )

    assert values["account_pool"] == AccountPool.ENGAGEMENT.value


def test_account_values_rejects_disabled_pool_for_onboarding() -> None:
    with pytest.raises(ValueError, match="account_pool must be search or engagement"):
        account_values(
            session_file_path="disabled.session",
            account_pool=AccountPool.DISABLED.value,
            notes=None,
        )


def test_build_onboarding_command_includes_pool_phone_and_safe_session_name() -> None:
    command = build_onboarding_command(
        account_pool=AccountPool.ENGAGEMENT.value,
        phone="+36 20 123 4567",
        session_name="engagement account",
        notes="public replies",
    )

    assert "--account-pool engagement" in command
    assert "--phone '+36 20 123 4567'" in command
    assert "--session-name engagement_account.session" in command
    assert "--notes 'public replies'" in command
