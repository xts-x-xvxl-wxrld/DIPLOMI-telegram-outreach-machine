# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from typing import Any, Awaitable, Callable

from .runtime import *
from .engagement_wizard_state import wizard_state
from .formatting_engagement_home import format_cockpit_home
from .ui_engagement_home import cockpit_home_markup
from .ui_engagement_wizard import engagement_wizard_cancel_confirm_markup


async def show_wizard_cancel_prompt(
    update: Any,
    engagement_id: str,
) -> None:
    await _edit_callback_message(
        update,
        "Cancel this engagement wizard? No data will be deleted.",
        reply_markup=engagement_wizard_cancel_confirm_markup(engagement_id),
    )


async def show_wizard_cancel_home(update: Any, context: Any) -> None:
    client = _api_client(context)
    try:
        payload = await client.get_engagement_cockpit_home()
    except BotApiError as exc:
        await _edit_callback_message(
            update,
            f"Setup cancelled, but the Engagements home could not load: {exc.message}",
        )
        return
    await _edit_callback_message(
        update,
        format_cockpit_home(payload),
        reply_markup=cockpit_home_markup(payload),
    )


async def handle_wizard_cancel_back(
    update: Any,
    context: Any,
    operator_id: int,
    show_step: Callable[[Any, Any, dict[str, Any]], Awaitable[None]],
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Setup expired. Return to Engagements and start again.")
        return
    await show_step(update, context, wizard_state(pending))


__all__ = [
    "handle_wizard_cancel_back",
    "show_wizard_cancel_home",
    "show_wizard_cancel_prompt",
]
