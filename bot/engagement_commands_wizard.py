# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from typing import Any

from .runtime import *
from .engagement_wizard_flow import _start_engagement_wizard


async def add_engagement_target_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    target_ref = _first_arg(context)
    try:
        await _start_engagement_wizard(update, context, target_ref=target_ref)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


__all__ = [
    "add_engagement_target_command",
]
