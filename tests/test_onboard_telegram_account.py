from __future__ import annotations

from pathlib import Path

import pytest

from backend.db.enums import AccountStatus
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


def test_resolve_session_path_stays_inside_sessions_dir(tmp_path: Path) -> None:
    path = resolve_session_path(str(tmp_path), "account.session")

    assert path == (tmp_path / "account.session").resolve()


def test_account_values_registers_available_account_without_leases() -> None:
    values = account_values(session_file_path="account.session", notes="operator-owned")

    assert values["status"] == AccountStatus.AVAILABLE.value
    assert values["session_file_path"] == "account.session"
    assert values["lease_owner"] is None
    assert values["last_error"] is None
    assert values["notes"] == "operator-owned"
