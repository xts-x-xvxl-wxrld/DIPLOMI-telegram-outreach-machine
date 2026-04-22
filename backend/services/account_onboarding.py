from __future__ import annotations

import re
from pathlib import Path

from backend.db.enums import AccountPool

ONBOARDABLE_ACCOUNT_POOLS = {AccountPool.SEARCH.value, AccountPool.ENGAGEMENT.value}


def validate_onboarding_account_pool(raw_value: str) -> str:
    account_pool = raw_value.strip().casefold()
    if account_pool not in ONBOARDABLE_ACCOUNT_POOLS:
        raise ValueError("account_pool must be search or engagement")
    return account_pool


def safe_session_file_name(raw_value: str) -> str:
    raw_name = raw_value.strip()
    if "/" in raw_name or "\\" in raw_name or ".." in Path(raw_name).parts:
        raise ValueError("Session name must not contain path separators")

    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name).strip("._-")
    if not stem:
        raise ValueError("Session name must contain at least one safe character")
    if not stem.endswith(".session"):
        stem = f"{stem}.session"
    return stem


def build_onboarding_command(
    *,
    account_pool: str,
    phone: str,
    session_name: str | None = None,
    notes: str | None = None,
) -> str:
    normalized_pool = validate_onboarding_account_pool(account_pool)
    safe_session_name = safe_session_file_name(session_name or phone)

    parts = [
        "docker",
        "compose",
        "run",
        "--rm",
        "worker",
        "python",
        "scripts/onboard_telegram_account.py",
        "--account-pool",
        normalized_pool,
        "--phone",
        phone.strip(),
        "--session-name",
        safe_session_name,
    ]
    if notes:
        parts.extend(["--notes", notes.strip()])
    return " ".join(_powershell_quote(part) for part in parts)


def _powershell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:+-]+", value):
        return value
    return "'" + value.replace("'", "''") + "'"
