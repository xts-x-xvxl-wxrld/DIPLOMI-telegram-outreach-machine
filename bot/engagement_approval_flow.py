from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bot.api_client import BotApiClient
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
from bot.ui_common import (
    ACTION_ENGAGEMENT_APPROVAL_QUEUE,
    _button,
    _inline_markup,
    _with_navigation,
)

# Store key for pending approval edits (separate from config edit store)
APPROVAL_EDIT_STORE_KEY = "approval_edit_store"

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
    return _inline_markup(_with_navigation(rows, back_action=ACTION_ENGAGEMENT_APPROVAL_QUEUE, back_parts=(_LIST, "0")))


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
    return _inline_markup(_with_navigation(rows))


def _empty_queue_markup() -> Any:
    return _inline_markup(_with_navigation([]))


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


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data["api_client"]


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


async def _callback_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None and query.message is not None:
        await query.message.reply_text(text, reply_markup=reply_markup)
        return
    message = getattr(update, "message", None)
    if message is not None:
        await message.reply_text(text, reply_markup=reply_markup)


async def _edit_callback_message(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.edit_message_text(text=text, reply_markup=reply_markup)


async def _reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    message = getattr(update, "message", None)
    if message is not None:
        await message.reply_text(text, reply_markup=reply_markup)


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


# ---------------------------------------------------------------------------
# Public handlers
# ---------------------------------------------------------------------------

async def show_global_approval_queue(update: Any, context: Any, *, offset: int = 0) -> None:
    client = _api_client(context)
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
        await _callback_reply(
            update,
            format_approval_queue_empty(scoped=False),
            reply_markup=_empty_queue_markup(),
        )
        return

    draft_id = str(current["draft_id"]) if current else None
    header = format_approval_queue_header(data, scoped=False, offset=offset)
    markup = _queue_list_markup(has_current=current is not None, draft_id=draft_id)
    await _callback_reply(update, header, reply_markup=markup)

    if current and draft_id:
        await _callback_reply(
            update,
            format_draft_card(current, index=1),
            reply_markup=_draft_card_markup(draft_id),
        )


async def show_scoped_approval_queue(update: Any, context: Any, *, engagement_id: str, offset: int = 0) -> None:
    client = _api_client(context)
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
    header = format_approval_queue_header(data, scoped=True, offset=offset)
    markup = _queue_list_markup(has_current=current is not None, draft_id=draft_id)
    await _callback_reply(update, header, reply_markup=markup)

    if current and draft_id:
        await _callback_reply(
            update,
            format_draft_card(current, index=1),
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
    data = await client.get_engagement_cockpit_approvals()
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


async def handle_approve_confirmed(update: Any, context: Any, *, draft_id: str) -> None:
    """Confirmed approve — call the backend."""
    client = _api_client(context)
    result = await client.approve_engagement_cockpit_draft(draft_id)
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


async def handle_reject_confirmed(update: Any, context: Any, *, draft_id: str) -> None:
    """Confirmed reject — call the backend."""
    client = _api_client(context)
    result = await client.reject_engagement_cockpit_draft(draft_id)
    await _callback_reply(
        update,
        format_approval_result(result, draft_id=draft_id, action="rejected"),
        reply_markup=_empty_queue_markup(),
    )


async def handle_edit_request_start(update: Any, context: Any, *, draft_id: str) -> None:
    """Capture operator's free-text edit request — show prompt and store pending state."""
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    client = _api_client(context)
    data = await client.get_engagement_cockpit_approvals()
    current = data.get("current")

    if current and str(current.get("draft_id", "")) == draft_id:
        draft_data = current
    else:
        draft_data = {"draft_id": draft_id, "target_label": "Draft", "text": "", "why": ""}

    # Store the pending edit in our approval store
    store = _approval_edit_store(context)
    store[operator_id] = {
        "draft_id": draft_id,
        "started_at": datetime.now(UTC).isoformat(),
    }

    await _callback_reply(update, format_edit_request_prompt(draft_id, draft_data))


async def handle_edit_request_text(update: Any, context: Any, *, text: str, draft_id: str) -> None:
    """Process the operator's free-text edit request and call the backend."""
    client = _api_client(context)

    result = await client.edit_engagement_cockpit_draft(draft_id, edit_request=text)

    # Clear the pending edit from the store
    operator_id = _telegram_user_id(update)
    if operator_id is not None:
        store = _approval_edit_store(context)
        store.pop(operator_id, None)

    await _reply(
        update,
        format_edit_submitted(draft_id, result),
        reply_markup=_empty_queue_markup(),
    )


def get_pending_approval_edit(context: Any, operator_id: int) -> dict[str, Any] | None:
    """Return any pending approval edit for this operator, or None."""
    store = _approval_edit_store(context)
    return store.get(operator_id)


def cancel_pending_approval_edit(context: Any, operator_id: int) -> dict[str, Any] | None:
    """Cancel and return any pending approval edit for this operator."""
    store = _approval_edit_store(context)
    return store.pop(operator_id, None)
