from __future__ import annotations

import asyncio
import logging
from typing import Any

from bot.display_policy import hide_slash_commands
from bot.formatting_engagement_approval import format_draft_card
from bot.ui_common import ACTION_ENGAGEMENT_APPROVAL_QUEUE, ACTION_ENGAGEMENT_HOME, _button, _inline_markup

LOGGER = logging.getLogger(__name__)

APPROVAL_DRAFT_NOTIFIER_TASK_KEY = "approval_draft_notifier_task"
APPROVAL_DRAFT_NOTIFIED_STORE_KEY = "approval_draft_notified_store"
APPROVAL_DRAFT_NOTIFY_POLL_INTERVAL_SECONDS_KEY = "approval_draft_notify_poll_interval_seconds"
DEFAULT_APPROVAL_DRAFT_NOTIFY_POLL_INTERVAL_SECONDS = 30.0

_OK = "ok"
_NO = "no"
_EDIT = "edit"


def approval_draft_markup(draft_id: str) -> Any:
    rows = [
        [
            _button("Approve", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _OK, draft_id),
            _button("Reject", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _NO, draft_id),
        ],
        [
            _button("Request edit", ACTION_ENGAGEMENT_APPROVAL_QUEUE, _EDIT, draft_id),
        ],
        [
            _button("Open approvals", ACTION_ENGAGEMENT_APPROVAL_QUEUE, "list", "0"),
            _button("<< Engagements", ACTION_ENGAGEMENT_HOME),
        ],
    ]
    return _inline_markup(rows)


def mark_approval_draft_notified(application: Any, *, operator_id: int, draft_id: str) -> None:
    if not draft_id:
        return
    store = _approval_draft_notified_store(application)
    draft_ids = store.setdefault(operator_id, set())
    draft_ids.add(draft_id)


def approval_draft_already_notified(application: Any, *, operator_id: int, draft_id: str) -> bool:
    if not draft_id:
        return False
    store = _approval_draft_notified_store(application)
    return draft_id in store.get(operator_id, set())


def start_approval_draft_notifier(application: Any) -> None:
    operator_ids = _approval_notification_operator_ids(application)
    if not operator_ids:
        return
    existing = application.bot_data.get(APPROVAL_DRAFT_NOTIFIER_TASK_KEY)
    if isinstance(existing, asyncio.Task) and not existing.done():
        return
    task = asyncio.create_task(_approval_draft_notifier_loop(application))
    application.bot_data[APPROVAL_DRAFT_NOTIFIER_TASK_KEY] = task


async def stop_approval_draft_notifier(application: Any) -> None:
    task = application.bot_data.pop(APPROVAL_DRAFT_NOTIFIER_TASK_KEY, None)
    if not isinstance(task, asyncio.Task):
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return


async def send_new_approval_draft_notifications(application: Any) -> None:
    operator_ids = _approval_notification_operator_ids(application)
    if not operator_ids:
        return
    client = application.bot_data.get("api_client")
    bot = getattr(application, "bot", None)
    if client is None or bot is None:
        return

    drafts = await _fetch_all_approval_drafts(client)
    for draft in drafts:
        draft_id = str(draft.get("draft_id") or "")
        if not draft_id:
            continue
        text = hide_slash_commands(f"New draft ready for review\n\n{format_draft_card(draft)}")
        markup = approval_draft_markup(draft_id)
        for operator_id in operator_ids:
            if approval_draft_already_notified(application, operator_id=operator_id, draft_id=draft_id):
                continue
            try:
                await bot.send_message(chat_id=operator_id, text=text, reply_markup=markup)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception(
                    "Couldn't send ordinary approval draft notification operator_id=%s draft_id=%s",
                    operator_id,
                    draft_id,
                )
                continue
            mark_approval_draft_notified(application, operator_id=operator_id, draft_id=draft_id)
            LOGGER.info(
                "Sent ordinary approval draft notification operator_id=%s draft_id=%s",
                operator_id,
                draft_id,
            )


async def _approval_draft_notifier_loop(application: Any) -> None:
    while True:
        try:
            await send_new_approval_draft_notifications(application)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Approval draft notifier loop failed")
        await asyncio.sleep(_approval_draft_notify_poll_interval_seconds(application))


async def _fetch_all_approval_drafts(client: Any) -> list[dict[str, Any]]:
    first_page = await client.get_engagement_cockpit_approvals()
    queue_count = int(first_page.get("queue_count") or 0)
    if queue_count <= 0:
        return []

    drafts: list[dict[str, Any]] = []
    current = first_page.get("current")
    if isinstance(current, dict):
        drafts.append(dict(current))
    for offset in range(1, queue_count):
        page = await client.get_engagement_cockpit_approvals(offset=offset)
        current = page.get("current")
        if isinstance(current, dict):
            drafts.append(dict(current))
    return drafts


def _approval_notification_operator_ids(application: Any) -> tuple[int, ...]:
    settings = application.bot_data.get("settings")
    admin_ids = set(getattr(settings, "admin_user_ids", ()) or ())
    allowed_ids = set(getattr(settings, "allowed_user_ids", ()) or ())
    operator_ids = sorted(admin_ids | allowed_ids)
    return tuple(int(operator_id) for operator_id in operator_ids if int(operator_id) > 0)


def _approval_draft_notify_poll_interval_seconds(application: Any) -> float:
    raw_value = application.bot_data.get(APPROVAL_DRAFT_NOTIFY_POLL_INTERVAL_SECONDS_KEY)
    try:
        seconds = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_APPROVAL_DRAFT_NOTIFY_POLL_INTERVAL_SECONDS
    return max(1.0, seconds)


def _approval_draft_notified_store(application: Any) -> dict[int, set[str]]:
    store = application.bot_data.get(APPROVAL_DRAFT_NOTIFIED_STORE_KEY)
    if not isinstance(store, dict):
        store = {}
        application.bot_data[APPROVAL_DRAFT_NOTIFIED_STORE_KEY] = store
    return store


__all__ = [
    "APPROVAL_DRAFT_NOTIFIED_STORE_KEY",
    "APPROVAL_DRAFT_NOTIFIER_TASK_KEY",
    "APPROVAL_DRAFT_NOTIFY_POLL_INTERVAL_SECONDS_KEY",
    "approval_draft_already_notified",
    "approval_draft_markup",
    "mark_approval_draft_notified",
    "send_new_approval_draft_notifications",
    "start_approval_draft_notifier",
    "stop_approval_draft_notifier",
]
