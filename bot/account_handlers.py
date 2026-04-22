from __future__ import annotations

from typing import Any

from bot.account_onboarding import (
    build_onboarding_command,
    safe_session_file_name,
    validate_onboarding_account_pool,
)
from bot.formatting import (
    format_account_onboarding_command,
    format_account_onboarding_usage,
)
from bot.runtime import _reply
from bot.ui import accounts_cockpit_markup


async def add_account_command(update: Any, context: Any) -> None:
    args = [str(arg).strip() for arg in getattr(context, "args", []) if str(arg).strip()]
    if len(args) < 2:
        await _reply(
            update,
            format_account_onboarding_usage(),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    account_pool, phone = args[0], args[1]
    session_name = args[2] if len(args) >= 3 else None
    notes = " ".join(args[3:]).strip() or None

    try:
        normalized_pool = validate_onboarding_account_pool(account_pool)
        session_file_name = safe_session_file_name(session_name or phone)
        command = build_onboarding_command(
            account_pool=normalized_pool,
            phone=phone,
            session_name=session_file_name,
            notes=notes,
        )
    except ValueError as exc:
        await _reply(
            update,
            format_account_onboarding_usage(str(exc)),
            reply_markup=accounts_cockpit_markup(),
        )
        return

    await _reply(
        update,
        format_account_onboarding_command(
            account_pool=normalized_pool,
            command=command,
            session_file_name=session_file_name,
        ),
        reply_markup=accounts_cockpit_markup(),
    )


__all__ = ["add_account_command"]
