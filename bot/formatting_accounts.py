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
            *_action_block(["Check the result with /accounts"]),
        ]
    )


def format_account_onboarding_code_sent(
    *,
    account_pool: str,
    phone: str,
    session_file_name: str,
) -> str:
    return "\n".join(
        [
            _headline("Telegram login code sent.", icon="[account]"),
            _field("Pool", account_pool),
            _field("Phone", _mask_phone(phone)),
            _field("Session file", session_file_name),
            "",
            _section("Next", icon="->"),
            _bullet("Send the Telegram login code in this chat."),
            _bullet("I will delete the code message after reading it."),
        ]
    )


def format_account_onboarding_password_required(*, phone: str) -> str:
    return "\n".join(
        [
            _headline("2FA password required.", icon="[safe]"),
            _field("Phone", _mask_phone(phone)),
            "",
            _section("Next", icon="->"),
            _bullet("Send the Telegram 2FA password in this chat."),
            _bullet("I will delete the password message after reading it."),
        ]
    )


def format_account_onboarding_registered(
    *,
    account_pool: str,
    phone: str,
    session_file_name: str,
) -> str:
    return "\n".join(
        [
            _headline("Telegram account added.", icon="[account]"),
            _field("Pool", account_pool),
            _field("Phone", _mask_phone(phone)),
            _field("Session file", session_file_name),
            *_action_block(["Check pool capacity with /accounts"]),
        ]
    )


def format_account_onboarding_usage(
    error: str | None = None,
    *,
    account_pool: str | None = None,
) -> str:
    usage_pool = account_pool if account_pool in {"search", "engagement"} else "<search|engagement>"
    lines = [
        _headline("Add a Telegram account", icon="[account]"),
        _field("Usage", f"/add_account {usage_pool} <phone> [session_name] [notes...]"),
        "",
        _section("Examples", icon="[shell]"),
        "/add_account search +10000000000 research-1 warm spare",
        "/add_account engagement +10000000001 engagement-1 public replies",
    ]
    if error:
        lines.extend(["", _field("Error", error, icon="[!]")])
    return "\n".join(lines)


def _mask_phone(phone: str) -> str:
    digits = [character for character in phone if character.isdigit()]
    if len(digits) <= 4:
        return "***"
    return f"+***{''.join(digits[-4:])}"
