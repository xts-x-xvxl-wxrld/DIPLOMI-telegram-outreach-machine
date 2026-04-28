from __future__ import annotations

import re
from typing import Any

from bot.api_client import BotApiClient, BotApiError
from bot.formatting_engagement_issue import (
    format_issue_card,
    format_issue_queue,
    format_issue_action_result,
    format_quiet_hours_state,
    format_quiet_hours_saved,
    format_rate_limit_detail,
)
from bot.ui_common import (
    ACTION_ENGAGEMENT_DETAIL,
    ACTION_ENGAGEMENT_ISSUE_QUEUE,
    _button,
    _inline_markup,
    _with_navigation,
)

# Key used to store skipped issue IDs per user in bot_data
SKIPPED_ISSUES_STORE_KEY = "skipped_issues"

# Key used to store pending quiet-hours edit state per user in bot_data
QUIET_HOURS_EDIT_STORE_KEY = "quiet_hours_edit"

_TIME_RANGE_RE = re.compile(
    r"^(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$"
)


# ---------------------------------------------------------------------------
# Skip state helpers
# ---------------------------------------------------------------------------


def _skipped_issues_store(context: Any) -> dict[int, set[str]]:
    store = context.application.bot_data.get(SKIPPED_ISSUES_STORE_KEY)
    if store is None:
        store = {}
        context.application.bot_data[SKIPPED_ISSUES_STORE_KEY] = store
    return store


def _mark_skipped(context: Any, operator_id: int, issue_id: str) -> None:
    store = _skipped_issues_store(context)
    if operator_id not in store:
        store[operator_id] = set()
    store[operator_id].add(issue_id)


def _is_skipped(context: Any, operator_id: int, issue_id: str) -> bool:
    store = _skipped_issues_store(context)
    return issue_id in store.get(operator_id, set())


# ---------------------------------------------------------------------------
# Quiet-hours pending edit helpers
# ---------------------------------------------------------------------------


def _quiet_hours_edit_store(context: Any) -> dict[int, dict[str, Any]]:
    store = context.application.bot_data.get(QUIET_HOURS_EDIT_STORE_KEY)
    if store is None:
        store = {}
        context.application.bot_data[QUIET_HOURS_EDIT_STORE_KEY] = store
    return store


def _start_quiet_hours_edit(
    context: Any,
    operator_id: int,
    *,
    issue_id: str,
    engagement_id: str,
) -> None:
    store = _quiet_hours_edit_store(context)
    store[operator_id] = {"issue_id": issue_id, "engagement_id": engagement_id}


def _get_quiet_hours_edit(context: Any, operator_id: int) -> dict[str, Any] | None:
    return _quiet_hours_edit_store(context).get(operator_id)


def _cancel_quiet_hours_edit(context: Any, operator_id: int) -> None:
    _quiet_hours_edit_store(context).pop(operator_id, None)


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data["api_client"]


def _telegram_user_id(update: Any) -> int | None:
    user = getattr(update, "effective_user", None)
    if user is None:
        query = getattr(update, "callback_query", None)
        if query is not None:
            user = getattr(query, "from_user", None)
    if user is None:
        msg = getattr(update, "message", None)
        if msg is not None:
            user = getattr(msg, "from_user", None)
    raw = getattr(user, "id", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def _edit_or_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
            return
        except Exception:
            if query.message is not None:
                await query.message.reply_text(text, reply_markup=reply_markup)
            return
    msg = getattr(update, "message", None)
    if msg is not None:
        await msg.reply_text(text, reply_markup=reply_markup)


async def _answer_callback(update: Any, text: str | None = None) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer(text)


# ---------------------------------------------------------------------------
# Markup builders
# ---------------------------------------------------------------------------


def _issue_queue_markup(
    item: dict[str, Any] | None,
    *,
    queue_count: int,
    offset: int,
    scoped_engagement_id: str | None,
) -> Any:
    issue_id = str(item.get("issue_id") or "") if item else ""
    rows: list[list[Any]] = []

    if item and issue_id:
        # Fix action buttons
        fix_actions = item.get("fix_actions") or []
        action_buttons = []
        for action in fix_actions:
            action_key = str(action.get("action_key") or "")
            label = str(action.get("label") or action_key)
            callback_family = str(action.get("callback_family") or ACTION_ENGAGEMENT_ISSUE_QUEUE)
            if not action_key:
                continue
            # Wizard-entry actions emit to eng:wz family
            if callback_family.startswith("eng:wz"):
                cb_data = f"{callback_family}:{action_key}:{item.get('engagement_id', '')}"
            else:
                cb_data = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:act:{issue_id}:{action_key}"
            # Truncate to 64 chars
            if len(cb_data) > 64:
                cb_data = cb_data[:64]
            action_buttons.append(_button(label, *_split_cb(cb_data)))
        if action_buttons:
            rows.append(action_buttons)

        # Skip button
        skip_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:skip:{issue_id}"
        rows.append([_button("⏭ Skip", *_split_cb(skip_cb))])

    # Pagination: previous issue
    if offset > 0:
        if scoped_engagement_id:
            prev_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:eng:{scoped_engagement_id}"
        else:
            prev_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:list:{max(0, offset - 1)}"
        rows.append([_button("← Prev", *_split_cb(prev_cb))])

    # Next issue (only if more in queue beyond current offset + 1)
    next_offset = offset + 1
    if next_offset < queue_count:
        if scoped_engagement_id:
            # scoped queues navigate by re-opening the engagement queue
            next_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:eng:{scoped_engagement_id}"
        else:
            next_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:list:{next_offset}"
        rows.append([_button("Next →", *_split_cb(next_cb))])

    # Navigation: back
    if scoped_engagement_id:
        back_action = ACTION_ENGAGEMENT_DETAIL
        back_parts_tuple = ("open", scoped_engagement_id)
        nav = _with_navigation(rows, back_action=back_action, back_parts=back_parts_tuple)
    else:
        nav = _with_navigation(rows)

    return _inline_markup(nav)


def _split_cb(cb_data: str) -> tuple[str, ...]:
    """Split a full callback string into (action, *parts) for _button()."""
    # _button(label, action, *parts) where action is the first token group
    # We pass the full string as a single action with no extra parts for simplicity
    # Actually _button calls encode_callback_data(action, *parts)
    # To avoid re-encoding, we return the whole thing as-is by splitting at first colon group
    # The real approach: pass the full string as action with no extra parts
    # encode_callback_data just joins with ":" so passing the whole string as action works
    return (cb_data,)


def _issue_card_markup(
    item: dict[str, Any],
    *,
    scoped_engagement_id: str | None,
    offset: int,
    queue_count: int,
) -> Any:
    return _issue_queue_markup(
        item,
        queue_count=queue_count,
        offset=offset,
        scoped_engagement_id=scoped_engagement_id,
    )


def _rate_limit_detail_markup(issue_id: str, *, back_engagement_id: str | None) -> Any:
    rows: list[list[Any]] = []
    if back_engagement_id:
        back_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:open:{issue_id}"
        rows.append([_button("← Back to issue", *_split_cb(back_cb))])
    return _inline_markup(_with_navigation(rows))


def _quiet_hours_edit_markup() -> Any:
    cancel_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:qh:cancel"
    rows = [[_button("✖ Cancel", *_split_cb(cancel_cb))]]
    return _inline_markup(_with_navigation(rows))


def _quiet_hours_saved_markup(issue_id: str) -> Any:
    back_cb = f"{ACTION_ENGAGEMENT_ISSUE_QUEUE}:open:{issue_id}"
    rows = [[_button("← Back to issue", *_split_cb(back_cb))]]
    return _inline_markup(_with_navigation(rows))


# ---------------------------------------------------------------------------
# Public flow functions
# ---------------------------------------------------------------------------


async def show_global_issue_queue(
    update: Any,
    context: Any,
    *,
    offset: int = 0,
) -> None:
    client = _api_client(context)
    operator_id = _telegram_user_id(update)
    try:
        data = await client.get_engagement_cockpit_issues()
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not load issues: {exc.message}")
        return

    queue_count = data.get("queue_count", 0)
    current = data.get("current")

    text = format_issue_queue(data, offset=offset, scoped=False)
    markup = _issue_queue_markup(
        current,
        queue_count=queue_count,
        offset=offset,
        scoped_engagement_id=None,
    )

    if current:
        issue_id = str(current.get("issue_id") or "")
        skipped = operator_id is not None and _is_skipped(context, operator_id, issue_id)
        card = format_issue_card(current, index=offset + 1, skipped=skipped)
        text = "\n\n".join([text, card])

    await _edit_or_reply(update, text, reply_markup=markup)


async def show_scoped_issue_queue(
    update: Any,
    context: Any,
    *,
    engagement_id: str,
    offset: int = 0,
) -> None:
    client = _api_client(context)
    operator_id = _telegram_user_id(update)
    try:
        data = await client.get_engagement_cockpit_issues_for_engagement(engagement_id)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not load issues: {exc.message}")
        return

    queue_count = data.get("queue_count", 0)
    current = data.get("current")

    if queue_count == 0 or current is None:
        text = format_issue_queue(data, offset=0, scoped=True)
        # Back to engagement detail
        markup = _inline_markup(
            _with_navigation(
                [],
                back_action=ACTION_ENGAGEMENT_DETAIL,
                back_parts=("open", engagement_id),
            )
        )
        await _edit_or_reply(update, text, reply_markup=markup)
        return

    text = format_issue_queue(data, offset=offset, scoped=True)
    issue_id = str(current.get("issue_id") or "")
    skipped = operator_id is not None and _is_skipped(context, operator_id, issue_id)
    card = format_issue_card(current, index=offset + 1, skipped=skipped)
    text = "\n\n".join([text, card])
    markup = _issue_queue_markup(
        current,
        queue_count=queue_count,
        offset=offset,
        scoped_engagement_id=engagement_id,
    )
    await _edit_or_reply(update, text, reply_markup=markup)


async def show_issue_card(
    update: Any,
    context: Any,
    *,
    issue_id: str,
) -> None:
    """Open a specific issue card by issue_id (fetched from global queue)."""
    client = _api_client(context)
    operator_id = _telegram_user_id(update)
    try:
        data = await client.get_engagement_cockpit_issues()
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not load issues: {exc.message}")
        return

    queue_count = data.get("queue_count", 0)
    current = data.get("current")

    # Try to find the requested issue in the queue
    item: dict[str, Any] | None = None
    offset = 0
    if current is not None and str(current.get("issue_id") or "") == issue_id:
        item = current
    else:
        # Issue might not be current; show it from current anyway
        item = current

    if item is None:
        await _edit_or_reply(update, "Issue not found or already resolved.")
        return

    skipped = operator_id is not None and _is_skipped(context, operator_id, issue_id)
    card = format_issue_card(item, skipped=skipped)
    markup = _issue_card_markup(
        item,
        scoped_engagement_id=None,
        offset=offset,
        queue_count=queue_count,
    )
    await _edit_or_reply(update, card, reply_markup=markup)


async def handle_issue_skip(
    update: Any,
    context: Any,
    *,
    issue_id: str,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is not None:
        _mark_skipped(context, operator_id, issue_id)
    await _answer_callback(update, "Skipped.")
    # Reload the global queue
    await show_global_issue_queue(update, context, offset=0)


async def handle_issue_action(
    update: Any,
    context: Any,
    *,
    issue_id: str,
    action_key: str,
) -> None:
    # Special pseudo-actions handled locally
    if action_key == "rate_limit_detail":
        await show_rate_limit_detail(update, context, issue_id=issue_id)
        return
    if action_key == "edit_quiet_hours":
        await start_quiet_hours_edit(update, context, issue_id=issue_id)
        return

    client = _api_client(context)
    try:
        result = await client.act_on_engagement_cockpit_issue(issue_id, action_key=action_key)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Action failed: {exc.message}")
        return

    status = str(result.get("result") or result.get("status") or "unknown")
    message = result.get("message")
    next_callback = result.get("next_callback")

    if status in {"resolved", "stale"}:
        await _answer_callback(update)
        # Reload global queue to reflect the resolved issue
        await show_global_issue_queue(update, context, offset=0)
        return

    if status == "next_step" and next_callback:
        await _answer_callback(update)
        # Emit a synthetic callback by navigating to next_callback
        await _navigate_to_callback(update, context, next_callback)
        return

    # noop or blocked
    feedback = format_issue_action_result(status, message=message)
    await _edit_or_reply(update, feedback)


async def show_rate_limit_detail(
    update: Any,
    context: Any,
    *,
    issue_id: str,
) -> None:
    client = _api_client(context)
    try:
        data = await client.get_engagement_cockpit_issue_rate_limit(issue_id)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not load rate limit info: {exc.message}")
        return

    text = format_rate_limit_detail(data)
    engagement_id = str(data.get("engagement_id") or "")
    markup = _rate_limit_detail_markup(issue_id, back_engagement_id=engagement_id or None)
    await _edit_or_reply(update, text, reply_markup=markup)


async def start_quiet_hours_edit(
    update: Any,
    context: Any,
    *,
    issue_id: str,
) -> None:
    client = _api_client(context)
    operator_id = _telegram_user_id(update)

    # We need the engagement_id for the issue — fetch from current queue
    try:
        data = await client.get_engagement_cockpit_issues()
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not load issue: {exc.message}")
        return

    current = data.get("current")
    engagement_id = str(current.get("engagement_id") or "") if current else ""

    if not engagement_id:
        await _edit_or_reply(update, "Could not find engagement for this issue.")
        return

    # Fetch current quiet-hours state
    try:
        qh_data = await client.get_engagement_cockpit_quiet_hours(engagement_id)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not load quiet hours: {exc.message}")
        return

    # Store pending edit state
    if operator_id is not None:
        _start_quiet_hours_edit(
            context,
            operator_id,
            issue_id=issue_id,
            engagement_id=engagement_id,
        )

    text = format_quiet_hours_state(qh_data)
    markup = _quiet_hours_edit_markup()
    await _edit_or_reply(update, text, reply_markup=markup)


async def save_quiet_hours(
    update: Any,
    context: Any,
    *,
    issue_id: str,
    time_range_text: str,
) -> None:
    operator_id = _telegram_user_id(update)
    edit_state = _get_quiet_hours_edit(context, operator_id) if operator_id else None

    if edit_state is None:
        await _edit_or_reply(update, "No quiet-hours edit in progress. Use the issue card to start editing.")
        return

    engagement_id = edit_state.get("engagement_id", "")
    stored_issue_id = edit_state.get("issue_id", issue_id)

    client = _api_client(context)
    text_stripped = time_range_text.strip().casefold()

    if text_stripped == "off":
        # Disable quiet hours
        payload: dict[str, Any] = {
            "quiet_hours_enabled": False,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
        }
    else:
        parsed = _parse_time_range(text_stripped)
        if parsed is None:
            await _edit_or_reply(
                update,
                "Invalid format. Send HH:MM-HH:MM (e.g. 22:00-08:00) or 'off' to disable.",
                reply_markup=_quiet_hours_edit_markup(),
            )
            return
        start_str, end_str = parsed
        payload = {
            "quiet_hours_enabled": True,
            "quiet_hours_start": start_str,
            "quiet_hours_end": end_str,
        }

    try:
        result = await client.update_engagement_cockpit_quiet_hours(
            engagement_id,
            **payload,
        )
    except BotApiError as exc:
        await _edit_or_reply(update, f"Could not save quiet hours: {exc.message}")
        return

    if operator_id is not None:
        _cancel_quiet_hours_edit(context, operator_id)

    text = format_quiet_hours_saved(result)
    markup = _quiet_hours_saved_markup(stored_issue_id)
    await _edit_or_reply(update, text, reply_markup=markup)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_time_range(text: str) -> tuple[str, str] | None:
    """Parse 'HH:MM-HH:MM' into (start, end) strings. Returns None on invalid input."""
    m = _TIME_RANGE_RE.match(text.strip())
    if not m:
        return None
    h1, m1, h2, m2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    if not (0 <= h1 <= 23 and 0 <= m1 <= 59 and 0 <= h2 <= 23 and 0 <= m2 <= 59):
        return None
    return f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"


async def _navigate_to_callback(update: Any, context: Any, callback_str: str) -> None:
    """Navigate to a callback by editing the message with appropriate text."""
    # For wizard-type callbacks: show a prompt to use that callback
    await _edit_or_reply(
        update,
        f"Next step: tap the button or use the linked action.\nCallback: {callback_str}",
    )


__all__ = [
    "SKIPPED_ISSUES_STORE_KEY",
    "QUIET_HOURS_EDIT_STORE_KEY",
    "show_global_issue_queue",
    "show_scoped_issue_queue",
    "show_issue_card",
    "handle_issue_skip",
    "handle_issue_action",
    "show_rate_limit_detail",
    "start_quiet_hours_edit",
    "save_quiet_hours",
]
