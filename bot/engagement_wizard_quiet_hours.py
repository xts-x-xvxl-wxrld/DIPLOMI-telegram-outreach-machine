from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from .runtime import (
    BotApiError,
    _api_client,
    _callback_reply,
    _config_edit_store,
    _reply,
    engagement_wizard_quiet_hours_markup,
    format_wizard_quiet_hours_prompt,
)
from .engagement_quiet_hours_timezones import (
    DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
    USER_SELECTABLE_QUIET_HOURS_TIMEZONES,
    normalize_bot_quiet_hours_timezone,
)
from .engagement_wizard_state import (
    sync_wizard_settings_state,
    wizard_quiet_hours_label,
    wizard_quiet_hours_timezone,
    wizard_quiet_hours_timezone_display,
    wizard_state,
    wizard_state_engagement_id,
)

_QUIET_HOURS_RANGE_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")


async def show_wizard_quiet_hours(update: Any, context: Any, state: dict[str, Any]) -> None:
    await _callback_reply(
        update,
        format_wizard_quiet_hours_prompt(
            current_quiet_hours=wizard_quiet_hours_label(state),
            current_timezone=wizard_quiet_hours_timezone_display(state),
        ),
        reply_markup=engagement_wizard_quiet_hours_markup(
            wizard_state_engagement_id(state),
            quiet_hours_timezone=wizard_quiet_hours_timezone(state),
        ),
    )


async def handle_wizard_quiet_hours(
    update: Any,
    context: Any,
    operator_id: int,
    action: str,
    engagement_id: str,
    *,
    show_review: Callable[[Any, Any, dict[str, Any]], Awaitable[None]],
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _callback_reply(update, "Setup expired. Return to Engagements and start again.")
        return
    state = wizard_state(pending)
    if wizard_state_engagement_id(state) != engagement_id:
        await _callback_reply(update, "Setup got out of sync. Return to Engagements and start again.")
        return

    if action == "open":
        _config_edit_store(context).set_value(
            operator_id,
            raw_value="",
            parsed_value=None,
            flow_step="quiet_hours",
            flow_state=state,
        )
        await show_wizard_quiet_hours(update, context, state)
        return

    if action.startswith("tz_"):
        timezone_code = normalize_bot_quiet_hours_timezone(
            action[3:],
            default=wizard_quiet_hours_timezone(state),
        )
        if timezone_code not in USER_SELECTABLE_QUIET_HOURS_TIMEZONES:
            timezone_code = DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE
        state["quiet_hours_timezone"] = timezone_code
        _config_edit_store(context).set_value(
            operator_id,
            raw_value="",
            parsed_value=None,
            flow_step="quiet_hours",
            flow_state=state,
        )
        await show_wizard_quiet_hours(update, context, state)
        return

    if action == "off":
        await save_wizard_quiet_hours(
            update,
            context,
            operator_id,
            engagement_id,
            "off",
            show_review=show_review,
        )
        return

    await _callback_reply(update, "Unknown quiet-hours action.")


async def save_wizard_quiet_hours(
    update: Any,
    context: Any,
    operator_id: int,
    engagement_id: str,
    raw_value: str,
    *,
    show_review: Callable[[Any, Any, dict[str, Any]], Awaitable[None]],
) -> None:
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "wizard":
        await _reply(update, "Setup expired. Return to Engagements and start again.")
        return
    state = wizard_state(pending)
    if wizard_state_engagement_id(state) != engagement_id:
        await _reply(update, "Setup got out of sync. Return to Engagements and start again.")
        return

    text = raw_value.strip()
    if text.casefold() == "off":
        quiet_hours_start = None
        quiet_hours_end = None
    else:
        parsed = _parse_quiet_hours_range(text)
        if parsed is None:
            await _reply(
                update,
                "Send quiet hours as HH:MM-HH:MM, for example 22:00-08:00, or send off.",
            )
            await show_wizard_quiet_hours(update, context, state)
            return
        quiet_hours_start, quiet_hours_end = parsed

    client = _api_client(context)
    quiet_hours_timezone = wizard_quiet_hours_timezone(state)
    try:
        result = await client.put_engagement_settings(
            engagement_id,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            quiet_hours_timezone=quiet_hours_timezone,
        )
        sync_wizard_settings_state(state, result)
    except BotApiError as exc:
        await _reply(update, f"Couldn't save quiet hours: {exc.message}")
        return

    _config_edit_store(context).set_value(
        operator_id,
        raw_value=text,
        parsed_value=None,
        flow_step="review",
        flow_state=state,
    )
    await show_review(update, context, state)


def _parse_quiet_hours_range(text: str) -> tuple[str, str] | None:
    match = _QUIET_HOURS_RANGE_RE.match(text)
    if not match:
        return None
    start_hour, start_minute, end_hour, end_minute = (int(group) for group in match.groups())
    if not (
        0 <= start_hour <= 23
        and 0 <= start_minute <= 59
        and 0 <= end_hour <= 23
        and 0 <= end_minute <= 59
    ):
        return None
    return (
        f"{start_hour:02d}:{start_minute:02d}",
        f"{end_hour:02d}:{end_minute:02d}",
    )
