"""
Engagement detail flow handlers.

Handles:
  eng:mine:list:<offset>        -- paginated My Engagements list
  eng:mine:open:<engagement_id> -- brief engagement preview
  eng:det:open:<engagement_id>  -- full engagement detail
  eng:det:resume:<engagement_id>-- follow pending_task.resume_callback from backend
  eng:sent:list:<offset>        -- paginated Sent Messages feed (read-only)
"""
from __future__ import annotations

from typing import Any

from bot.api_client import BotApiClient, BotApiError
from bot.formatting_engagement_detail import (
    format_engagement_list,
    format_engagement_row,
    format_engagement_detail,
    format_sent_messages,
    format_sent_message_row,
)
from bot.ui_engagement_detail import (
    engagement_list_markup,
    engagement_preview_markup,
    engagement_detail_markup,
    sent_messages_markup,
)

_PAGE_SIZE = 20


async def _edit_or_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    elif update.message is not None:
        await update.message.reply_text(text, reply_markup=reply_markup)


def _get_client(context: Any) -> BotApiClient:
    return context.application.bot_data["api_client"]


async def show_engagement_list(update: Any, context: Any, *, offset: int = 0) -> None:
    client = _get_client(context)
    try:
        payload = await client.list_engagement_cockpit_engagements(
            limit=_PAGE_SIZE,
            offset=offset,
        )
    except BotApiError as exc:
        await _edit_or_reply(update, f"Couldn't load engagements: {exc.message}")
        return

    items = payload.get("items") or []
    total = int(payload.get("total", len(items)))
    text = format_engagement_list(payload)

    if items:
        rows_text = "\n\n".join(format_engagement_row(e) for e in items)
        text = f"{text}\n\n{rows_text}"

    markup = engagement_list_markup(
        items,
        offset=offset,
        total=total,
        page_size=_PAGE_SIZE,
    )
    await _edit_or_reply(update, text, reply_markup=markup)


async def show_engagement_preview(update: Any, context: Any, *, engagement_id: str) -> None:
    client = _get_client(context)
    try:
        payload = await client.get_engagement_cockpit_engagement(engagement_id)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Couldn't load engagement: {exc.message}")
        return

    text = format_engagement_detail(payload)
    markup = engagement_preview_markup(engagement_id)
    await _edit_or_reply(update, text, reply_markup=markup)


async def show_engagement_detail(update: Any, context: Any, *, engagement_id: str) -> None:
    client = _get_client(context)
    try:
        payload = await client.get_engagement_cockpit_engagement(engagement_id)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Couldn't load engagement: {exc.message}")
        return

    text = format_engagement_detail(payload)
    pending_task = payload.get("pending_task")
    markup = engagement_detail_markup(engagement_id, pending_task=pending_task)
    await _edit_or_reply(update, text, reply_markup=markup)


async def handle_engagement_resume(update: Any, context: Any, *, engagement_id: str) -> None:
    """
    Fetch the latest detail to get the current pending_task.resume_callback
    and dispatch to that callback directly.
    """
    client = _get_client(context)
    try:
        payload = await client.get_engagement_cockpit_engagement(engagement_id)
    except BotApiError as exc:
        await _edit_or_reply(update, f"Couldn't resume task: {exc.message}")
        return

    pending_task = payload.get("pending_task")
    if not pending_task:
        # No pending task any more — refresh the detail view
        await show_engagement_detail(update, context, engagement_id=engagement_id)
        return

    resume_callback = pending_task.get("resume_callback")
    if not resume_callback:
        await show_engagement_detail(update, context, engagement_id=engagement_id)
        return

    # Store the resume callback so the outer dispatch layer can re-route.
    # The callback_handlers router is responsible for wiring; this handler
    # only needs to surface the resume target.
    query = getattr(update, "callback_query", None)
    if query is not None:
        context.user_data["_resume_callback"] = resume_callback
        try:
            await query.answer()
        except Exception:
            pass

    # Attempt inline dispatch without importing callback_handlers directly
    # (avoids circular import at module load time).  If dispatch is available
    # via a registered hook it will be called; otherwise fall through.
    _dispatch = getattr(context, "_dispatch_callback", None)
    if _dispatch is not None:
        try:
            await _dispatch(update, context, data=resume_callback)
            return
        except Exception:
            pass

    # Fallback: just show the detail with the pending task info
    text = format_engagement_detail(payload)
    markup = engagement_detail_markup(engagement_id, pending_task=pending_task)
    await _edit_or_reply(update, text, reply_markup=markup)


async def show_sent_messages(update: Any, context: Any, *, offset: int = 0) -> None:
    client = _get_client(context)
    try:
        payload = await client.list_engagement_cockpit_sent(
            limit=_PAGE_SIZE,
            offset=offset,
        )
    except BotApiError as exc:
        await _edit_or_reply(update, f"Couldn't load sent messages: {exc.message}")
        return

    items = payload.get("items") or []
    total = int(payload.get("total", len(items)))
    text = format_sent_messages(payload)

    if items:
        rows_text = "\n\n---\n\n".join(format_sent_message_row(m) for m in items)
        text = f"{text}\n\n{rows_text}"

    markup = sent_messages_markup(
        offset=offset,
        total=total,
        page_size=_PAGE_SIZE,
    )
    await _edit_or_reply(update, text, reply_markup=markup)
