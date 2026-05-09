from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from bot.api_client import BotApiClient
from bot.engagement_approval_notifications import (
    approval_draft_markup,
    mark_approval_draft_notified,
)
from bot.display_policy import hide_slash_commands
from bot.formatting_engagement_approval import (
    format_approval_queue_empty,
    format_approval_placeholder_only,
    format_approve_confirm,
    format_approval_result,
    format_draft_card,
    format_edit_request_prompt,
    format_edit_submitted,
    format_reject_confirm,
    format_approval_queue_header,
)
from bot.formatting_engagement_home import format_cockpit_home
from bot.ui_engagement_home import cockpit_home_markup
from bot.ui_common import (
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_APPROVAL_QUEUE,
    _button,
    _inline_markup,
)

LOGGER = logging.getLogger(__name__)

# Store key for pending approval edits (separate from config edit store)
APPROVAL_EDIT_STORE_KEY = "approval_edit_store"
APPROVAL_EDIT_POLL_ATTEMPTS_KEY = "approval_edit_poll_attempts"
APPROVAL_EDIT_POLL_INTERVAL_SECONDS_KEY = "approval_edit_poll_interval_seconds"
APPROVAL_UPDATE_WATCHERS_KEY = "approval_update_watchers"
APPROVAL_UPDATE_NOTIFY_POLL_ATTEMPTS_KEY = "approval_update_notify_poll_attempts"
APPROVAL_UPDATE_NOTIFY_POLL_INTERVAL_SECONDS_KEY = "approval_update_notify_poll_interval_seconds"
DEFAULT_APPROVAL_EDIT_POLL_ATTEMPTS = 5
DEFAULT_APPROVAL_EDIT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_APPROVAL_UPDATE_NOTIFY_POLL_ATTEMPTS = 45
DEFAULT_APPROVAL_UPDATE_NOTIFY_POLL_INTERVAL_SECONDS = 2.0

# Sub-action suffixes
_LIST = "list"
_ENG = "eng"
_OPEN = "open"
_OK = "ok"
_OKC = "okc"
_NO = "no"
_NOC = "noc"
_EDIT = "edit"


# ---------------------------------------------------------------------------
# Markup helpers
# ---------------------------------------------------------------------------

def _engagement_markup(
    rows: list[list[Any]],
    *,
    back_action: str | None = None,
    back_parts: tuple[str, ...] = (),
) -> Any:
    footer: list[Any] = []
    if back_action is not None:
        footer.append(_button("Back", back_action, *back_parts))
    footer.append(_button("<< Engagements", ACTION_ENGAGEMENT_HOME))
    return _inline_markup([*rows, footer])


def _draft_card_markup(draft_id: str) -> Any:
    rows = [
        [
            _button("✅ Approve", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _OK, draft_id),
            _button("❌ Reject", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _NO, draft_id),
        ],
        [
            _button("✏ Request edit", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _EDIT, draft_id),
        ],
    ]
    return _engagement_markup(
        rows,
        back_action=ACTION_ENGAGEMENT_APPROVAL_QUEUE,
        back_parts=(_LIST, "0"),
    )


def _approve_confirm_markup(draft_id: str) -> Any:
    rows = [
        [
            _button("Confirm approve", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _OKC, draft_id),
            _button("Cancel", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _OPEN, draft_id),
        ],
    ]
    return _inline_markup(rows)


def _reject_confirm_markup(draft_id: str) -> Any:
    rows = [
        [
            _button("Confirm reject", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _NOC, draft_id),
            _button("Cancel", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _OPEN, draft_id),
        ],
    ]
    return _inline_markup(rows)


def _queue_list_markup(*, has_current: bool, draft_id: str | None = None) -> Any:
    rows: list[list[Any]] = []
    if has_current and draft_id:
        rows.append([
            _button("Open next draft", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _OPEN, draft_id),
        ])
    return _engagement_markup(rows)


def _empty_queue_markup() -> Any:
    return _engagement_markup([])


def _draft_card_markup(draft_id: str) -> Any:
    return approval_draft_markup(draft_id)


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def _approval_edit_store(context: Any) -> dict[int, dict[str, Any]]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None) or {}
    store = bot_data.get(APPROVAL_EDIT_STORE_KEY)
    if store is None:
        store = {}
        if isinstance(bot_data, dict):
            bot_data[APPROVAL_EDIT_STORE_KEY] = store
    return store


def _approval_update_watchers(context: Any) -> dict[int, asyncio.Task[Any]]:
    bot_data = _bot_data(context)
    store = bot_data.get(APPROVAL_UPDATE_WATCHERS_KEY)
    if store is None:
        store = {}
        bot_data[APPROVAL_UPDATE_WATCHERS_KEY] = store
    return store if isinstance(store, dict) else {}


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data["api_client"]


def _bot_data(context: Any) -> dict[str, Any]:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    return bot_data if isinstance(bot_data, dict) else {}


def _approval_edit_poll_attempts(context: Any) -> int:
    raw_value = _bot_data(context).get(APPROVAL_EDIT_POLL_ATTEMPTS_KEY)
    try:
        attempts = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_APPROVAL_EDIT_POLL_ATTEMPTS
    return max(1, attempts)


def _approval_edit_poll_interval_seconds(context: Any) -> float:
    raw_value = _bot_data(context).get(APPROVAL_EDIT_POLL_INTERVAL_SECONDS_KEY)
    try:
        seconds = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_APPROVAL_EDIT_POLL_INTERVAL_SECONDS
    return max(0.0, seconds)


def _approval_update_notify_poll_attempts(context: Any) -> int:
    raw_value = _bot_data(context).get(APPROVAL_UPDATE_NOTIFY_POLL_ATTEMPTS_KEY)
    try:
        attempts = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_APPROVAL_UPDATE_NOTIFY_POLL_ATTEMPTS
    return max(1, attempts)


def _approval_update_notify_poll_interval_seconds(context: Any) -> float:
    raw_value = _bot_data(context).get(APPROVAL_UPDATE_NOTIFY_POLL_INTERVAL_SECONDS_KEY)
    try:
        seconds = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_APPROVAL_UPDATE_NOTIFY_POLL_INTERVAL_SECONDS
    return max(0.0, seconds)


def _telegram_user_id(update: Any) -> int | None:
    # Try effective_user first (most reliable)
    effective_user = getattr(update, "effective_user", None)
    if effective_user is not None:
        try:
            uid = int(effective_user.id)
            return uid
        except (TypeError, ValueError):
            pass

    query = getattr(update, "callback_query", None)
    if query is not None:
        user = getattr(query, "from_user", None)
        if user is not None:
            try:
                return int(user.id)
            except (TypeError, ValueError):
                return None

    message = getattr(update, "message", None)
    user = getattr(message, "from_user", None) if message else None
    if user is not None:
        try:
            return int(user.id)
        except (TypeError, ValueError):
            return None

    return None


def _telegram_chat_id(update: Any) -> int | None:
    effective_chat = getattr(update, "effective_chat", None)
    if effective_chat is not None:
        try:
            return int(effective_chat.id)
        except (TypeError, ValueError):
            pass

    query = getattr(update, "callback_query", None)
    query_message = getattr(query, "message", None) if query is not None else None
    chat = getattr(query_message, "chat", None)
    if chat is not None:
        try:
            return int(chat.id)
        except (TypeError, ValueError):
            pass
    chat_id = getattr(query_message, "chat_id", None)
    if chat_id is not None:
        try:
            return int(chat_id)
        except (TypeError, ValueError):
            return None

    message = getattr(update, "message", None)
    message_chat = getattr(message, "chat", None)
    if message_chat is not None:
        try:
            return int(message_chat.id)
        except (TypeError, ValueError):
            pass
    message_chat_id = getattr(message, "chat_id", None)
    try:
        return int(message_chat_id) if message_chat_id is not None else None
    except (TypeError, ValueError):
        return None


async def _callback_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    text = hide_slash_commands(text)
    query = getattr(update, "callback_query", None)
    if query is not None and query.message is not None:
        await query.message.reply_text(text, reply_markup=reply_markup)
        return
    message = getattr(update, "message", None)
    if message is not None:
        await message.reply_text(text, reply_markup=reply_markup)


async def _edit_callback_message(update: Any, text: str, reply_markup: Any | None = None) -> None:
    text = hide_slash_commands(text)
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.edit_message_text(text=text, reply_markup=reply_markup)


async def _reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    text = hide_slash_commands(text)
    message = getattr(update, "message", None)
    if message is not None:
        await message.reply_text(text, reply_markup=reply_markup)


async def _send_message(context: Any, *, chat_id: int, text: str, reply_markup: Any | None = None) -> None:
    text = hide_slash_commands(text)
    application = getattr(context, "application", None)
    bot = getattr(application, "bot", None)
    if bot is None:
        return
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


def _mark_draft_visible_to_operator(update: Any, context: Any, *, draft_id: str | None) -> None:
    if not draft_id:
        return
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return
    application = getattr(context, "application", None)
    if application is None:
        return
    mark_approval_draft_notified(application, operator_id=operator_id, draft_id=draft_id)


async def _send_cockpit_home(update: Any, context: Any) -> None:
    client = _api_client(context)
    payload = await client.get_engagement_cockpit_home()
    query = getattr(update, "callback_query", None)
    if query is not None:
        await _edit_callback_message(
            update,
            format_cockpit_home(payload),
            reply_markup=cockpit_home_markup(payload),
        )
        return
    await _reply(
        update,
        format_cockpit_home(payload),
        reply_markup=cockpit_home_markup(payload),
    )


def _is_all_placeholder(data: dict[str, Any]) -> bool:
    """Return True if queue has items but they are ALL placeholder/updating drafts."""
    queue_count = int(data.get("queue_count") or 0)
    updating_count = int(data.get("updating_count") or 0)
    current = data.get("current")
    if queue_count == 0 and updating_count > 0:
        return True
    if updating_count > 0 and current is None and queue_count == updating_count:
        return True
    return False


def _is_updated_replacement_draft(current: dict[str, Any] | None, *, original_draft_id: str) -> bool:
    if current is None:
        return False
    badge = str(current.get("badge") or "").strip()
    current_draft_id = str(current.get("draft_id") or "")
    return badge == "Updated draft" and current_draft_id not in {"", original_draft_id}


async def _wait_for_updated_replacement_draft(
    context: Any,
    *,
    engagement_id: str | None,
    original_draft_id: str,
) -> dict[str, Any] | None:
    if not engagement_id:
        return None

    client = _api_client(context)
    attempts = _approval_edit_poll_attempts(context)
    delay_seconds = _approval_edit_poll_interval_seconds(context)
    return await _poll_for_updated_replacement_draft(
        client,
        engagement_id=engagement_id,
        original_draft_id=original_draft_id,
        attempts=attempts,
        delay_seconds=delay_seconds,
    )


async def _poll_for_updated_replacement_draft(
    client: BotApiClient,
    *,
    engagement_id: str | None,
    original_draft_id: str,
    attempts: int,
    delay_seconds: float,
) -> dict[str, Any] | None:
    if not engagement_id:
        return None

    for attempt_index in range(attempts):
        data = await client.get_engagement_cockpit_approvals_for_engagement(engagement_id)
        current = data.get("current")
        if _is_updated_replacement_draft(current, original_draft_id=original_draft_id):
            return current
        if attempt_index + 1 >= attempts:
            break
        await asyncio.sleep(delay_seconds)
    return None


async def _watch_for_updated_replacement_draft(
    context: Any,
    *,
    operator_id: int,
    chat_id: int,
    engagement_id: str,
    original_draft_id: str,
) -> None:
    client = _api_client(context)
    revised_draft = await _poll_for_updated_replacement_draft(
        client,
        engagement_id=engagement_id,
        original_draft_id=original_draft_id,
        attempts=_approval_update_notify_poll_attempts(context),
        delay_seconds=_approval_update_notify_poll_interval_seconds(context),
    )
    if revised_draft is None:
        return

    draft_id = str(revised_draft.get("draft_id") or "")
    if not draft_id:
        return

    await _send_message(
        context,
        chat_id=chat_id,
        text=f"Updated draft ready\n\n{format_draft_card(revised_draft)}",
        reply_markup=_draft_card_markup(draft_id),
    )
    application = getattr(context, "application", None)
    if application is not None:
        mark_approval_draft_notified(application, operator_id=operator_id, draft_id=draft_id)
    LOGGER.info(
        "Sent delayed approval update notification operator_id=%s chat_id=%s engagement_id=%s draft_id=%s",
        operator_id,
        chat_id,
        engagement_id,
        draft_id,
    )


def _clear_finished_approval_update_watcher(
    context: Any,
    *,
    operator_id: int,
    task: asyncio.Task[Any],
) -> None:
    watchers = _approval_update_watchers(context)
    if watchers.get(operator_id) is task:
        watchers.pop(operator_id, None)
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        LOGGER.exception("Approval update watcher failed operator_id=%s", operator_id)


def _start_approval_update_watcher(
    context: Any,
    *,
    operator_id: int | None,
    chat_id: int | None,
    engagement_id: str | None,
    original_draft_id: str,
) -> None:
    if operator_id is None or chat_id is None or not engagement_id:
        return

    watchers = _approval_update_watchers(context)
    existing = watchers.get(operator_id)
    if existing is not None and not existing.done():
        existing.cancel()

    task = asyncio.create_task(
        _watch_for_updated_replacement_draft(
            context,
            operator_id=operator_id,
            chat_id=chat_id,
            engagement_id=engagement_id,
            original_draft_id=original_draft_id,
        )
    )
    watchers[operator_id] = task
    task.add_done_callback(
        lambda finished_task: _clear_finished_approval_update_watcher(
            context,
            operator_id=operator_id,
            task=finished_task,
        )
    )


# ---------------------------------------------------------------------------
# Public handlers
# ---------------------------------------------------------------------------

async def show_global_approval_queue(
    update: Any,
    context: Any,
    *,
    offset: int = 0,
    return_home_on_empty: bool = False,
) -> None:
    client = _api_client(context)
    if offset:
        data = await client.get_engagement_cockpit_approvals(offset=offset)
    else:
        data = await client.get_engagement_cockpit_approvals()

    queue_count = int(data.get("queue_count") or 0)
    updating_count = int(data.get("updating_count") or 0)
    current = data.get("current")

    # All-placeholder state: don't kick out, render waiting message
    if _is_all_placeholder(data):
        await _callback_reply(
            update,
            format_approval_placeholder_only(),
            reply_markup=_empty_queue_markup(),
        )
        return

    if queue_count == 0 and updating_count == 0:
        if return_home_on_empty:
            await _send_cockpit_home(update, context)
            return
        await _callback_reply(
            update,
            format_approval_queue_empty(scoped=False),
            reply_markup=_empty_queue_markup(),
        )
        return

    draft_id = str(current["draft_id"]) if current else None
    queue_offset = int(data.get("offset") or offset)
    header = format_approval_queue_header(data, scoped=False, offset=queue_offset)
    markup = _queue_list_markup(has_current=current is not None, draft_id=draft_id)
    await _callback_reply(update, header, reply_markup=markup)

    if current and draft_id:
        _mark_draft_visible_to_operator(update, context, draft_id=draft_id)
        await _callback_reply(
            update,
            format_draft_card(current, index=queue_offset + 1),
            reply_markup=_draft_card_markup(draft_id),
        )


async def show_scoped_approval_queue(update: Any, context: Any, *, engagement_id: str, offset: int = 0) -> None:
    client = _api_client(context)
    if offset:
        data = await client.get_engagement_cockpit_approvals_for_engagement(
            engagement_id,
            offset=offset,
        )
    else:
        data = await client.get_engagement_cockpit_approvals_for_engagement(engagement_id)

    queue_count = int(data.get("queue_count") or 0)
    updating_count = int(data.get("updating_count") or 0)
    current = data.get("current")

    # All-placeholder: show waiting state, don't navigate away
    if _is_all_placeholder(data):
        await _callback_reply(
            update,
            format_approval_placeholder_only(),
            reply_markup=_empty_queue_markup(),
        )
        return

    if queue_count == 0 and updating_count == 0:
        # Empty scoped queue: caller can navigate to engagement detail
        # Signal via context user_data for the caller to navigate
        _store_scoped_engagement_id(context, engagement_id)
        await _callback_reply(
            update,
            format_approval_queue_empty(scoped=True),
            reply_markup=_empty_queue_markup(),
        )
        return

    draft_id = str(current["draft_id"]) if current else None
    queue_offset = int(data.get("offset") or offset)
    header = format_approval_queue_header(data, scoped=True, offset=queue_offset)
    markup = _queue_list_markup(has_current=current is not None, draft_id=draft_id)
    await _callback_reply(update, header, reply_markup=markup)

    if current and draft_id:
        _mark_draft_visible_to_operator(update, context, draft_id=draft_id)
        await _callback_reply(
            update,
            format_draft_card(current, index=queue_offset + 1),
            reply_markup=_draft_card_markup(draft_id),
        )


def _store_scoped_engagement_id(context: Any, engagement_id: str) -> None:
    """Store the scoped engagement_id for the caller to navigate back."""
    user_data = getattr(context, "user_data", None)
    if isinstance(user_data, dict):
        user_data["last_scoped_engagement_id"] = engagement_id


def scoped_queue_empty_callback(engagement_id: str) -> str:
    """Return the callback string for navigating to engagement detail when scoped queue is empty."""
    return f"eng:det:open:{engagement_id}"


async def show_draft_card(update: Any, context: Any, *, draft_id: str) -> None:
    """Open a specific draft card by finding it in the global approvals queue."""
    client = _api_client(context)
    # Load the global queue to find the current draft
    data = await client.get_engagement_cockpit_approvals(draft_id=draft_id)
    current = data.get("current")

    if current and str(current.get("draft_id", "")) == draft_id:
        draft_data = current
    else:
        # Draft might not be current — render with minimal info we know
        draft_data = {"draft_id": draft_id, "target_label": "Draft", "text": "", "why": ""}

    await _callback_reply(
        update,
        format_draft_card(draft_data),
        reply_markup=_draft_card_markup(draft_id),
    )
    _mark_draft_visible_to_operator(update, context, draft_id=draft_id)


async def handle_approve_confirm(update: Any, context: Any, *, draft_id: str) -> None:
    """Show the approval confirmation step (local only, no backend call yet)."""
    client = _api_client(context)
    data = await client.get_engagement_cockpit_approvals()
    current = data.get("current")

    if current and str(current.get("draft_id", "")) == draft_id:
        draft_data = current
    else:
        draft_data = {"draft_id": draft_id, "target_label": "Draft", "text": "", "why": ""}

    await _callback_reply(
        update,
        format_approve_confirm(draft_id, draft_data),
        reply_markup=_approve_confirm_markup(draft_id),
    )
    _mark_draft_visible_to_operator(update, context, draft_id=draft_id)


async def handle_approve_confirmed(update: Any, context: Any, *, draft_id: str) -> None:
    """Confirmed approve — call the backend."""
    client = _api_client(context)
    result = await client.approve_engagement_cockpit_draft(draft_id)
    status = str(result.get("result") or "")
    if status == "approved":
        await show_global_approval_queue(update, context, offset=0, return_home_on_empty=True)
        return
    if status == "stale":
        await show_global_approval_queue(update, context, offset=0, return_home_on_empty=True)
        return
    await _callback_reply(
        update,
        format_approval_result(result, draft_id=draft_id, action="approved"),
        reply_markup=_empty_queue_markup(),
    )


async def handle_reject_confirm(update: Any, context: Any, *, draft_id: str) -> None:
    """Show the rejection confirmation step (local only, no backend call yet)."""
    client = _api_client(context)
    data = await client.get_engagement_cockpit_approvals()
    current = data.get("current")

    if current and str(current.get("draft_id", "")) == draft_id:
        draft_data = current
    else:
        draft_data = {"draft_id": draft_id, "target_label": "Draft", "text": "", "why": ""}

    await _callback_reply(
        update,
        format_reject_confirm(draft_id, draft_data),
        reply_markup=_reject_confirm_markup(draft_id),
    )
    _mark_draft_visible_to_operator(update, context, draft_id=draft_id)


async def handle_reject_confirmed(update: Any, context: Any, *, draft_id: str) -> None:
    """Confirmed reject — call the backend."""
    client = _api_client(context)
    result = await client.reject_engagement_cockpit_draft(draft_id)
    status = str(result.get("result") or "")
    if status == "rejected":
        await show_global_approval_queue(update, context, offset=0, return_home_on_empty=True)
        return
    if status == "stale":
        await show_global_approval_queue(update, context, offset=0, return_home_on_empty=True)
        return
    await _callback_reply(
        update,
        format_approval_result(result, draft_id=draft_id, action="rejected"),
        reply_markup=_empty_queue_markup(),
    )


async def handle_edit_request_start(update: Any, context: Any, *, draft_id: str) -> None:
    """Capture operator's free-text edit request — show prompt and store pending state."""
    await resume_edit_request(update, context, draft_id=draft_id)


async def resume_edit_request(update: Any, context: Any, *, draft_id: str | None = None) -> None:
    """Restore or start the approval-edit prompt for a current draft."""
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    client = _api_client(context)
    pending = get_pending_approval_edit(context, operator_id)
    requested_draft_id = draft_id or (None if pending is None else str(pending.get("draft_id") or ""))
    if requested_draft_id:
        data = await client.get_engagement_cockpit_approvals(draft_id=requested_draft_id)
    else:
        data = await client.get_engagement_cockpit_approvals()
    current = data.get("current")

    if current and str(current.get("draft_id", "")):
        draft_data = current
        resolved_draft_id = str(current.get("draft_id", ""))
    else:
        if requested_draft_id:
            await _callback_reply(
                update,
                "That draft is no longer available in the approval queue. Open it again from Approvals first.",
            )
            return
        await _callback_reply(update, "No draft is waiting for review right now.")
        return

    # Store the pending edit in our approval store
    store = _approval_edit_store(context)
    store[operator_id] = {
        "draft_id": resolved_draft_id,
        "started_at": datetime.now(UTC).isoformat(),
    }

    await _callback_reply(update, format_edit_request_prompt(resolved_draft_id, draft_data))
    _mark_draft_visible_to_operator(update, context, draft_id=resolved_draft_id)


async def handle_edit_request_text(update: Any, context: Any, *, text: str, draft_id: str) -> None:
    """Process the operator's free-text edit request and call the backend."""
    client = _api_client(context)

    result = await client.edit_engagement_cockpit_draft(draft_id, edit_request=text)

    # Clear the pending edit from the store
    operator_id = _telegram_user_id(update)
    chat_id = _telegram_chat_id(update)
    if operator_id is not None:
        store = _approval_edit_store(context)
        store.pop(operator_id, None)

    status = str(result.get("result") or "")
    if status == "queued_update":
        revised_draft = await _wait_for_updated_replacement_draft(
            context,
            engagement_id=None if result.get("engagement_id") is None else str(result["engagement_id"]),
            original_draft_id=draft_id,
        )
        if revised_draft is not None:
            revised_draft_id = str(revised_draft.get("draft_id") or "")
            _mark_draft_visible_to_operator(update, context, draft_id=revised_draft_id)
            await _reply(
                update,
                format_draft_card(revised_draft),
                reply_markup=_draft_card_markup(revised_draft_id),
            )
            return
        _start_approval_update_watcher(
            context,
            operator_id=operator_id,
            chat_id=chat_id,
            engagement_id=None if result.get("engagement_id") is None else str(result["engagement_id"]),
            original_draft_id=draft_id,
        )

    if status in {"queued_update", "approved", "rejected", "stale"}:
        await show_global_approval_queue(update, context, offset=0, return_home_on_empty=True)
        return

    await _reply(update, format_edit_submitted(draft_id, result), reply_markup=_empty_queue_markup())


def get_pending_approval_edit(context: Any, operator_id: int) -> dict[str, Any] | None:
    """Return any pending approval edit for this operator, or None."""
    store = _approval_edit_store(context)
    return store.get(operator_id)


def cancel_pending_approval_edit(context: Any, operator_id: int) -> dict[str, Any] | None:
    """Cancel and return any pending approval edit for this operator."""
    store = _approval_edit_store(context)
    return store.pop(operator_id, None)
