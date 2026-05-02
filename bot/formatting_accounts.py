from __future__ import annotations

from .formatting_common import _action_block, _bullet, _field, _headline, _section


def format_account_onboarding_command(
    *,
    account_pool: str,
    command: str,
    session_file_name: str,
) -> str:
    return "\n".join(
        [
            _headline("Telegram account onboarding prepared.", icon="[account]"),
            _field("Pool", account_pool),
            _field("Session file", session_file_name),
            "",
            _section("Run locally", icon="[shell]"),
            command,
            "",
            _section("Safety", icon="[safe]"),
            _bullet("Enter Telegram login codes and 2FA only in the local shell."),
            _bullet("Use dedicated accounts; search stays read-only, engagement is public-facing."),
            *_action_block(["Return to Accounts to verify the result."]),
        ]
    )

def format_account_onboarding_code_sent(
    *,
    account_pool: str,
    phone: str,
    session_file_name: str,
) -> str:
    del account_pool, phone, session_file_name
    return "Enter the Telegram login code.\n\nExample: 12345"


def format_account_onboarding_password_required(*, phone: str) -> str:
    del phone
    return "Enter the Telegram 2FA password."


def format_account_onboarding_registered(
    *,
    account_pool: str,
    phone: str,
    session_file_name: str,
) -> str:
    del account_pool, phone, session_file_name
    return "Telegram account added."


def format_account_onboarding_usage(
    error: str | None = None,
    *,
    account_pool: str | None = None,
) -> str:
    lines = [
        _headline("Add a Telegram account", icon="[account]"),
        _bullet("Choose Add search or Add engagement below."),
        _bullet("Then send the phone number, optional account name, and optional notes when prompted."),
        "",
        _section("Flow", icon="[shell]"),
        "1. Pick the pool",
        "2. Send the phone number",
        "3. Optionally name the account",
        "4. Optionally add notes",
    ]
    if account_pool in {"search", "engagement"}:
        lines.insert(1, _field("Pool", account_pool))
    if error:
        lines.extend(["", _field("Error", error, icon="[!]")])
    return "\n".join(lines)


def format_account_health_refresh_job(data: dict[str, object]) -> str:
    job = data.get("job") or {}
    job_id = str(job.get("id") or "unknown")
    job_type = str(job.get("type") or "account.health_refresh")
    return "\n".join(
        [
            "Account health check queued.",
            "",
            f"Job: {job_id} ({job_type})",
            "Use Refresh job below to watch progress, then return to Accounts for the updated view.",
        ]
    )

def _mask_phone(phone: str) -> str:
    digits = [character for character in phone if character.isdigit()]
    if len(digits) <= 4:
        return "***"
    return f"+***{''.join(digits[-4:])}"


