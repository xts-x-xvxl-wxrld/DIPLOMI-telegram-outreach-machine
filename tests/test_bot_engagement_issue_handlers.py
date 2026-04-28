from __future__ import annotations

import sys
import os
from types import SimpleNamespace
from typing import Any

import pytest

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.engagement_issue_flow import (
    QUIET_HOURS_EDIT_STORE_KEY,
    SKIPPED_ISSUES_STORE_KEY,
    handle_issue_action,
    handle_issue_skip,
    save_quiet_hours,
    show_global_issue_queue,
    show_issue_card,
    show_rate_limit_detail,
    show_scoped_issue_queue,
    start_quiet_hours_edit,
)
from bot.formatting_engagement_issue import (
    format_issue_action_result,
    format_issue_card,
    format_issue_queue,
    format_quiet_hours_saved,
    format_quiet_hours_state,
    format_rate_limit_detail,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.replies: list[dict[str, Any]] = []

    async def reply_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})


class _FakeCallbackQuery:
    def __init__(self, data: str, *, user_id: int = 123) -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=user_id, username="operator")
        self.answers: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


class _FakeApiClient:
    def __init__(self) -> None:
        self.get_issues_calls: list[dict[str, Any]] = []
        self.get_scoped_issues_calls: list[str] = []
        self.act_on_issue_calls: list[dict[str, Any]] = []
        self.get_rate_limit_calls: list[str] = []
        self.get_quiet_hours_calls: list[str] = []
        self.update_quiet_hours_calls: list[dict[str, Any]] = []

        self.issue_data: dict[str, Any] = {
            "queue_count": 2,
            "empty_state": "All clear.",
            "current": {
                "issue_id": "issue-uuid-1",
                "engagement_id": "engagement-uuid-1",
                "issue_type": "topics_not_chosen",
                "issue_label": "Topics not chosen",
                "target_label": "Open CRM · @founders",
                "context": "Choose or create a topic",
                "fix_actions": [
                    {
                        "action_key": "chtopic",
                        "label": "Choose topic",
                        "callback_family": "eng:wz",
                    },
                    {
                        "action_key": "crtopic",
                        "label": "Create topic",
                        "callback_family": "eng:wz",
                    },
                ],
                "candidate_id": None,
                "community_id": "community-uuid-1",
                "assigned_account_id": None,
            },
        }
        self.action_result: dict[str, Any] = {"result": "resolved", "message": "Issue resolved."}
        self.rate_limit_data: dict[str, Any] = {
            "result": "ok",
            "message": "Sending is paused until the limit clears.",
            "next_callback": "eng:iss:open:issue-uuid-1",
            "issue_id": "issue-uuid-1",
            "engagement_id": "engagement-uuid-1",
            "title": "Rate limit active",
            "target_label": "Open CRM · @founders",
            "blocked_action_label": "Send reply",
            "scope_label": "Account limit",
            "reset_at": None,
        }
        self.quiet_hours_data: dict[str, Any] = {
            "result": "ok",
            "message": "Current quiet hours.",
            "next_callback": "eng:iss:open:issue-uuid-1",
            "engagement_id": "engagement-uuid-1",
            "title": "Quiet hours",
            "target_label": "Open CRM · @founders",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }
        self.update_quiet_hours_result: dict[str, Any] = {
            "result": "updated",
            "message": "Quiet hours updated.",
            "next_callback": "eng:iss:open:issue-uuid-1",
            "engagement_id": "engagement-uuid-1",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }

    async def get_engagement_cockpit_issues(self) -> dict[str, Any]:
        self.get_issues_calls.append({})
        return dict(self.issue_data)

    async def get_engagement_cockpit_issues_for_engagement(
        self, engagement_id: str
    ) -> dict[str, Any]:
        self.get_scoped_issues_calls.append(engagement_id)
        return dict(self.issue_data)

    async def act_on_engagement_cockpit_issue(
        self, issue_id: str, *, action_key: str
    ) -> dict[str, Any]:
        self.act_on_issue_calls.append({"issue_id": issue_id, "action_key": action_key})
        return dict(self.action_result)

    async def get_engagement_cockpit_issue_rate_limit(self, issue_id: str) -> dict[str, Any]:
        self.get_rate_limit_calls.append(issue_id)
        return dict(self.rate_limit_data)

    async def get_engagement_cockpit_quiet_hours(self, engagement_id: str) -> dict[str, Any]:
        self.get_quiet_hours_calls.append(engagement_id)
        return dict(self.quiet_hours_data)

    async def update_engagement_cockpit_quiet_hours(
        self,
        engagement_id: str,
        *,
        quiet_hours_enabled: bool,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
    ) -> dict[str, Any]:
        self.update_quiet_hours_calls.append(
            {
                "engagement_id": engagement_id,
                "quiet_hours_enabled": quiet_hours_enabled,
                "quiet_hours_start": quiet_hours_start,
                "quiet_hours_end": quiet_hours_end,
            }
        )
        return dict(self.update_quiet_hours_result)


def _context(client: _FakeApiClient) -> SimpleNamespace:
    bot_data: dict[str, Any] = {"api_client": client}
    return SimpleNamespace(
        args=[],
        application=SimpleNamespace(bot_data=bot_data),
    )


def _message_update(text: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        message=_FakeMessage(text=text),
        callback_query=None,
        effective_user=SimpleNamespace(id=123, username="operator"),
    )


def _callback_update(data: str, *, user_id: int = 123) -> SimpleNamespace:
    query = _FakeCallbackQuery(data, user_id=user_id)
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=query.from_user,
    )


def _callback_data_values(markup: Any | None) -> list[str]:
    if markup is None:
        return []
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "callback_data", None)
    ]


def _button_labels(markup: Any | None) -> list[str]:
    if markup is None:
        return []
    return [
        button.text
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "text", None)
    ]


def _replied_text(update: SimpleNamespace) -> str:
    if update.callback_query is not None:
        edits = update.callback_query.edits
        if edits:
            return edits[-1]["text"]
        replies = update.callback_query.message.replies
        if replies:
            return replies[-1]["text"]
        return ""
    if update.message is not None:
        replies = update.message.replies
        if replies:
            return replies[-1]["text"]
    return ""


def _replied_markup(update: SimpleNamespace) -> Any | None:
    if update.callback_query is not None:
        edits = update.callback_query.edits
        if edits:
            return edits[-1]["reply_markup"]
        replies = update.callback_query.message.replies
        if replies:
            return replies[-1]["reply_markup"]
        return None
    if update.message is not None:
        replies = update.message.replies
        if replies:
            return replies[-1]["reply_markup"]
    return None


# ---------------------------------------------------------------------------
# Formatter unit tests
# ---------------------------------------------------------------------------


def test_format_issue_queue_shows_count_and_offset() -> None:
    data = {
        "queue_count": 3,
        "empty_state": "All clear.",
        "current": {"issue_id": "x", "issue_type": "topics_not_chosen"},
    }
    text = format_issue_queue(data, offset=0, scoped=False)
    assert "3 open" in text
    assert "issue" in text.lower()


def test_format_issue_queue_empty_state() -> None:
    data = {"queue_count": 0, "empty_state": "All clear.", "current": None}
    text = format_issue_queue(data, offset=0, scoped=False)
    assert "All clear." in text


def test_format_issue_queue_scoped_empty() -> None:
    data = {"queue_count": 0, "empty_state": "No issues.", "current": None}
    text = format_issue_queue(data, offset=0, scoped=True)
    assert "No issues." in text


def test_format_issue_card_shows_type_and_context() -> None:
    item = {
        "issue_id": "issue-1",
        "engagement_id": "eng-1",
        "issue_type": "topics_not_chosen",
        "issue_label": "Topics not chosen",
        "target_label": "Open CRM · @founders",
        "context": "Choose or create a topic",
        "fix_actions": [],
    }
    text = format_issue_card(item)
    assert "Topics not chosen" in text
    assert "Open CRM" in text
    assert "Choose or create a topic" in text


def test_format_issue_card_shows_skipped_badge() -> None:
    item = {
        "issue_id": "issue-1",
        "engagement_id": "eng-1",
        "issue_type": "reply_failed",
        "issue_label": "Reply failed",
        "target_label": "Builder Slack",
        "context": "Retry the failed reply",
        "fix_actions": [],
    }
    text = format_issue_card(item, skipped=True)
    assert "skipped before" in text.lower()


def test_format_issue_card_shows_index() -> None:
    item = {
        "issue_id": "issue-1",
        "engagement_id": "eng-1",
        "issue_type": "sending_is_paused",
        "issue_label": "Sending is paused",
        "target_label": "Group A",
        "context": "Resume sending",
        "fix_actions": [],
    }
    text = format_issue_card(item, index=2)
    assert "2." in text


def test_format_rate_limit_detail_fields() -> None:
    data = {
        "result": "ok",
        "message": "Sending is paused until the limit clears.",
        "next_callback": "eng:iss:open:issue-1",
        "title": "Rate limit active",
        "target_label": "Open CRM · @founders",
        "blocked_action_label": "Send reply",
        "scope_label": "Account limit",
        "reset_at": "2026-04-28T08:00:00+00:00",
    }
    text = format_rate_limit_detail(data)
    assert "Rate limit active" in text
    assert "Account limit" in text
    assert "Send reply" in text
    assert "2026-04-28" in text


def test_format_quiet_hours_state_enabled() -> None:
    data = {
        "title": "Quiet hours",
        "target_label": "Group B",
        "quiet_hours_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
    text = format_quiet_hours_state(data)
    assert "22:00" in text
    assert "08:00" in text
    assert "Enabled" in text


def test_format_quiet_hours_state_disabled() -> None:
    data = {
        "title": "Quiet hours",
        "target_label": "Group B",
        "quiet_hours_enabled": False,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
    }
    text = format_quiet_hours_state(data)
    assert "Disabled" in text


def test_format_quiet_hours_saved_enabled() -> None:
    data = {
        "result": "updated",
        "quiet_hours_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
    text = format_quiet_hours_saved(data)
    assert "updated" in text.lower()
    assert "22:00" in text


def test_format_issue_action_result_resolved() -> None:
    text = format_issue_action_result("resolved")
    assert "resolved" in text.lower()


def test_format_issue_action_result_noop() -> None:
    text = format_issue_action_result("noop")
    assert "no change" in text.lower()


def test_format_issue_action_result_blocked_with_reason() -> None:
    text = format_issue_action_result("blocked", message="Cannot do that right now.")
    assert "Cannot do that right now." in text


def test_format_issue_action_result_stale() -> None:
    text = format_issue_action_result("stale")
    assert "stale" in text.lower() or "resolved" in text.lower()


# ---------------------------------------------------------------------------
# Flow: show_global_issue_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_global_issue_queue_calls_api_and_shows_count() -> None:
    client = _FakeApiClient()
    update = _message_update()
    ctx = _context(client)

    await show_global_issue_queue(update, ctx, offset=0)

    assert len(client.get_issues_calls) == 1
    text = _replied_text(update)
    assert "2" in text  # queue_count


@pytest.mark.asyncio
async def test_show_global_issue_queue_shows_issue_card() -> None:
    client = _FakeApiClient()
    update = _message_update()
    ctx = _context(client)

    await show_global_issue_queue(update, ctx, offset=0)

    text = _replied_text(update)
    assert "Topics not chosen" in text
    assert "Open CRM" in text


@pytest.mark.asyncio
async def test_show_global_issue_queue_empty_shows_empty_state() -> None:
    client = _FakeApiClient()
    client.issue_data = {"queue_count": 0, "empty_state": "All clear.", "current": None}
    update = _message_update()
    ctx = _context(client)

    await show_global_issue_queue(update, ctx, offset=0)

    text = _replied_text(update)
    assert "All clear." in text


@pytest.mark.asyncio
async def test_show_global_issue_queue_marks_skipped_badge() -> None:
    client = _FakeApiClient()
    update = _message_update()
    ctx = _context(client)

    # Pre-mark the issue as skipped
    store = ctx.application.bot_data.setdefault(SKIPPED_ISSUES_STORE_KEY, {})
    store[123] = {"issue-uuid-1"}

    await show_global_issue_queue(update, ctx, offset=0)

    text = _replied_text(update)
    assert "skipped before" in text.lower()


@pytest.mark.asyncio
async def test_show_global_issue_queue_api_error_shows_message() -> None:
    from bot.api_client import BotApiError

    client = _FakeApiClient()

    async def _raise(*a: Any, **kw: Any) -> Any:
        raise BotApiError("Server down", status_code=500)

    client.get_engagement_cockpit_issues = _raise  # type: ignore[method-assign]
    update = _message_update()
    ctx = _context(client)

    await show_global_issue_queue(update, ctx, offset=0)

    text = _replied_text(update)
    assert "Could not load issues" in text or "Server down" in text


# ---------------------------------------------------------------------------
# Flow: show_scoped_issue_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_scoped_issue_queue_calls_scoped_api() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:eng:engagement-uuid-1")
    ctx = _context(client)

    await show_scoped_issue_queue(update, ctx, engagement_id="engagement-uuid-1")

    assert client.get_scoped_issues_calls == ["engagement-uuid-1"]
    text = _replied_text(update)
    assert "Topics not chosen" in text


@pytest.mark.asyncio
async def test_show_scoped_issue_queue_empty_has_back_to_engagement() -> None:
    client = _FakeApiClient()
    client.issue_data = {"queue_count": 0, "empty_state": "No issues here.", "current": None}
    update = _callback_update("eng:iss:eng:engagement-uuid-1")
    ctx = _context(client)

    await show_scoped_issue_queue(update, ctx, engagement_id="engagement-uuid-1")

    text = _replied_text(update)
    assert "No issues here." in text


# ---------------------------------------------------------------------------
# Flow: show_issue_card
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_issue_card_fetches_from_queue_and_renders() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:open:issue-uuid-1")
    ctx = _context(client)

    await show_issue_card(update, ctx, issue_id="issue-uuid-1")

    assert len(client.get_issues_calls) == 1
    text = _replied_text(update)
    assert "Topics not chosen" in text


@pytest.mark.asyncio
async def test_show_issue_card_shows_not_found_when_no_current() -> None:
    client = _FakeApiClient()
    client.issue_data = {"queue_count": 0, "empty_state": "All clear.", "current": None}
    update = _callback_update("eng:iss:open:issue-uuid-1")
    ctx = _context(client)

    await show_issue_card(update, ctx, issue_id="issue-uuid-1")

    text = _replied_text(update)
    assert "not found" in text.lower() or "resolved" in text.lower()


# ---------------------------------------------------------------------------
# Flow: handle_issue_skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_issue_skip_marks_issue_skipped() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:skip:issue-uuid-1")
    ctx = _context(client)

    await handle_issue_skip(update, ctx, issue_id="issue-uuid-1")

    store = ctx.application.bot_data.get(SKIPPED_ISSUES_STORE_KEY) or {}
    assert "issue-uuid-1" in store.get(123, set())


@pytest.mark.asyncio
async def test_handle_issue_skip_answers_callback() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:skip:issue-uuid-1")
    ctx = _context(client)

    await handle_issue_skip(update, ctx, issue_id="issue-uuid-1")

    assert len(update.callback_query.answers) >= 1


@pytest.mark.asyncio
async def test_handle_issue_skip_then_queue_shows_skipped_badge() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:skip:issue-uuid-1")
    ctx = _context(client)

    await handle_issue_skip(update, ctx, issue_id="issue-uuid-1")

    # The subsequent queue render should show the badge
    # (handle_issue_skip calls show_global_issue_queue internally)
    # Check the last reply/edit
    text = _replied_text(update)
    assert "skipped before" in text.lower()


# ---------------------------------------------------------------------------
# Flow: handle_issue_action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_issue_action_resolved_reloads_queue() -> None:
    client = _FakeApiClient()
    client.action_result = {"result": "resolved", "message": "Resolved."}
    update = _callback_update("eng:iss:act:issue-uuid-1:resume")
    ctx = _context(client)

    await handle_issue_action(update, ctx, issue_id="issue-uuid-1", action_key="resume")

    assert len(client.act_on_issue_calls) == 1
    assert client.act_on_issue_calls[0]["action_key"] == "resume"
    # Queue is reloaded
    assert len(client.get_issues_calls) >= 1


@pytest.mark.asyncio
async def test_handle_issue_action_stale_reloads_queue() -> None:
    client = _FakeApiClient()
    client.action_result = {"result": "stale", "message": "Already changed."}
    update = _callback_update("eng:iss:act:issue-uuid-1:retry")
    ctx = _context(client)

    await handle_issue_action(update, ctx, issue_id="issue-uuid-1", action_key="retry")

    assert len(client.get_issues_calls) >= 1


@pytest.mark.asyncio
async def test_handle_issue_action_noop_shows_no_change() -> None:
    client = _FakeApiClient()
    client.action_result = {"result": "noop", "message": "No change needed."}
    update = _callback_update("eng:iss:act:issue-uuid-1:resume")
    ctx = _context(client)

    await handle_issue_action(update, ctx, issue_id="issue-uuid-1", action_key="resume")

    text = _replied_text(update)
    assert "no change" in text.lower()


@pytest.mark.asyncio
async def test_handle_issue_action_blocked_shows_reason() -> None:
    client = _FakeApiClient()
    client.action_result = {"result": "blocked", "message": "Account not ready."}
    update = _callback_update("eng:iss:act:issue-uuid-1:chacct")
    ctx = _context(client)

    await handle_issue_action(update, ctx, issue_id="issue-uuid-1", action_key="chacct")

    text = _replied_text(update)
    assert "Account not ready." in text


@pytest.mark.asyncio
async def test_handle_issue_action_next_step_navigates() -> None:
    client = _FakeApiClient()
    client.action_result = {
        "result": "next_step",
        "message": "Continue.",
        "next_callback": "eng:wz:edit:engagement-uuid-1:topic",
    }
    update = _callback_update("eng:iss:act:issue-uuid-1:chtopic")
    ctx = _context(client)

    await handle_issue_action(update, ctx, issue_id="issue-uuid-1", action_key="chtopic")

    # Should not reload queue but navigate to next
    text = _replied_text(update)
    assert "eng:wz:edit:engagement-uuid-1:topic" in text or "Next step" in text


@pytest.mark.asyncio
async def test_handle_issue_action_rate_limit_detail_dispatches() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:rate_limit_detail")
    ctx = _context(client)

    await handle_issue_action(
        update, ctx, issue_id="issue-uuid-1", action_key="rate_limit_detail"
    )

    # Should call rate limit API
    assert "issue-uuid-1" in client.get_rate_limit_calls
    text = _replied_text(update)
    assert "Rate limit" in text


@pytest.mark.asyncio
async def test_handle_issue_action_edit_quiet_hours_dispatches() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    await handle_issue_action(
        update, ctx, issue_id="issue-uuid-1", action_key="edit_quiet_hours"
    )

    # Should call quiet hours API
    assert len(client.get_quiet_hours_calls) >= 1
    text = _replied_text(update)
    assert "Quiet hours" in text or "quiet" in text.lower()


@pytest.mark.asyncio
async def test_handle_issue_action_api_error_shows_message() -> None:
    from bot.api_client import BotApiError

    client = _FakeApiClient()

    async def _raise(*a: Any, **kw: Any) -> Any:
        raise BotApiError("Action failed upstream", status_code=500)

    client.act_on_engagement_cockpit_issue = _raise  # type: ignore[method-assign]
    update = _callback_update("eng:iss:act:issue-uuid-1:resume")
    ctx = _context(client)

    await handle_issue_action(update, ctx, issue_id="issue-uuid-1", action_key="resume")

    text = _replied_text(update)
    assert "failed" in text.lower() or "Action failed" in text


# ---------------------------------------------------------------------------
# Flow: show_rate_limit_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_rate_limit_detail_calls_api_and_shows_info() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:ratelimit")
    ctx = _context(client)

    await show_rate_limit_detail(update, ctx, issue_id="issue-uuid-1")

    assert client.get_rate_limit_calls == ["issue-uuid-1"]
    text = _replied_text(update)
    assert "Rate limit active" in text
    assert "Account limit" in text


@pytest.mark.asyncio
async def test_show_rate_limit_detail_shows_blocked_action() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:ratelimit")
    ctx = _context(client)

    await show_rate_limit_detail(update, ctx, issue_id="issue-uuid-1")

    text = _replied_text(update)
    assert "Send reply" in text


@pytest.mark.asyncio
async def test_show_rate_limit_detail_api_error() -> None:
    from bot.api_client import BotApiError

    client = _FakeApiClient()

    async def _raise(*a: Any, **kw: Any) -> Any:
        raise BotApiError("Not found", status_code=404)

    client.get_engagement_cockpit_issue_rate_limit = _raise  # type: ignore[method-assign]
    update = _callback_update("eng:iss:act:issue-uuid-1:ratelimit")
    ctx = _context(client)

    await show_rate_limit_detail(update, ctx, issue_id="issue-uuid-1")

    text = _replied_text(update)
    assert "Could not load" in text or "Not found" in text


# ---------------------------------------------------------------------------
# Flow: start_quiet_hours_edit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_quiet_hours_edit_shows_current_state() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    await start_quiet_hours_edit(update, ctx, issue_id="issue-uuid-1")

    assert len(client.get_quiet_hours_calls) == 1
    text = _replied_text(update)
    assert "Quiet hours" in text
    assert "22:00" in text


@pytest.mark.asyncio
async def test_start_quiet_hours_edit_stores_pending_state() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    await start_quiet_hours_edit(update, ctx, issue_id="issue-uuid-1")

    store = ctx.application.bot_data.get(QUIET_HOURS_EDIT_STORE_KEY) or {}
    assert 123 in store
    assert store[123]["issue_id"] == "issue-uuid-1"


@pytest.mark.asyncio
async def test_start_quiet_hours_edit_no_engagement_id_shows_error() -> None:
    client = _FakeApiClient()
    client.issue_data = {"queue_count": 0, "empty_state": "All clear.", "current": None}
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    await start_quiet_hours_edit(update, ctx, issue_id="issue-uuid-1")

    text = _replied_text(update)
    assert "engagement" in text.lower() or "Could not" in text


# ---------------------------------------------------------------------------
# Flow: save_quiet_hours
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_quiet_hours_valid_range_calls_api() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    # Pre-populate edit state
    ctx.application.bot_data[QUIET_HOURS_EDIT_STORE_KEY] = {
        123: {"issue_id": "issue-uuid-1", "engagement_id": "engagement-uuid-1"}
    }

    await save_quiet_hours(update, ctx, issue_id="issue-uuid-1", time_range_text="22:00-08:00")

    assert len(client.update_quiet_hours_calls) == 1
    call = client.update_quiet_hours_calls[0]
    assert call["quiet_hours_enabled"] is True
    assert call["quiet_hours_start"] == "22:00"
    assert call["quiet_hours_end"] == "08:00"


@pytest.mark.asyncio
async def test_save_quiet_hours_off_disables_quiet_hours() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    ctx.application.bot_data[QUIET_HOURS_EDIT_STORE_KEY] = {
        123: {"issue_id": "issue-uuid-1", "engagement_id": "engagement-uuid-1"}
    }

    await save_quiet_hours(update, ctx, issue_id="issue-uuid-1", time_range_text="off")

    assert len(client.update_quiet_hours_calls) == 1
    call = client.update_quiet_hours_calls[0]
    assert call["quiet_hours_enabled"] is False


@pytest.mark.asyncio
async def test_save_quiet_hours_invalid_format_shows_error() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    ctx.application.bot_data[QUIET_HOURS_EDIT_STORE_KEY] = {
        123: {"issue_id": "issue-uuid-1", "engagement_id": "engagement-uuid-1"}
    }

    await save_quiet_hours(update, ctx, issue_id="issue-uuid-1", time_range_text="not-a-time")

    text = _replied_text(update)
    assert "Invalid format" in text or "HH:MM" in text
    # API should NOT be called
    assert len(client.update_quiet_hours_calls) == 0


@pytest.mark.asyncio
async def test_save_quiet_hours_no_pending_edit_shows_error() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    # No pending edit in store
    await save_quiet_hours(update, ctx, issue_id="issue-uuid-1", time_range_text="22:00-08:00")

    text = _replied_text(update)
    assert "No quiet-hours edit" in text or "edit in progress" in text.lower()
    assert len(client.update_quiet_hours_calls) == 0


@pytest.mark.asyncio
async def test_save_quiet_hours_clears_pending_edit_after_save() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    ctx.application.bot_data[QUIET_HOURS_EDIT_STORE_KEY] = {
        123: {"issue_id": "issue-uuid-1", "engagement_id": "engagement-uuid-1"}
    }

    await save_quiet_hours(update, ctx, issue_id="issue-uuid-1", time_range_text="22:00-08:00")

    store = ctx.application.bot_data.get(QUIET_HOURS_EDIT_STORE_KEY) or {}
    assert 123 not in store


@pytest.mark.asyncio
async def test_save_quiet_hours_shows_saved_confirmation() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:iss:act:issue-uuid-1:edit_quiet_hours")
    ctx = _context(client)

    ctx.application.bot_data[QUIET_HOURS_EDIT_STORE_KEY] = {
        123: {"issue_id": "issue-uuid-1", "engagement_id": "engagement-uuid-1"}
    }

    await save_quiet_hours(update, ctx, issue_id="issue-uuid-1", time_range_text="22:00-08:00")

    text = _replied_text(update)
    assert "updated" in text.lower() or "Quiet hours" in text


# ---------------------------------------------------------------------------
# Time range parser edge cases
# ---------------------------------------------------------------------------


def test_time_range_parser_valid() -> None:
    from bot.engagement_issue_flow import _parse_time_range

    result = _parse_time_range("22:00-08:00")
    assert result == ("22:00", "08:00")


def test_time_range_parser_single_digit_hour() -> None:
    from bot.engagement_issue_flow import _parse_time_range

    result = _parse_time_range("8:00-22:00")
    assert result == ("08:00", "22:00")


def test_time_range_parser_invalid_returns_none() -> None:
    from bot.engagement_issue_flow import _parse_time_range

    assert _parse_time_range("not-a-time") is None
    assert _parse_time_range("25:00-08:00") is None
    assert _parse_time_range("22:60-08:00") is None
    assert _parse_time_range("off") is None


def test_time_range_parser_with_spaces() -> None:
    from bot.engagement_issue_flow import _parse_time_range

    result = _parse_time_range("22:00 - 08:00")
    assert result == ("22:00", "08:00")


# ---------------------------------------------------------------------------
# Skip state isolation between users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skipped_issues_are_per_user() -> None:
    client = _FakeApiClient()
    update_a = _callback_update("eng:iss:skip:issue-uuid-1", user_id=123)
    ctx = _context(client)

    await handle_issue_skip(update_a, ctx, issue_id="issue-uuid-1")

    # User 456 should NOT have the issue marked as skipped
    store = ctx.application.bot_data.get(SKIPPED_ISSUES_STORE_KEY) or {}
    assert "issue-uuid-1" in store.get(123, set())
    assert "issue-uuid-1" not in store.get(456, set())


# ---------------------------------------------------------------------------
# Multiple issues in queue (offset navigation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_global_issue_queue_offset_1_shows_issue_1() -> None:
    client = _FakeApiClient()
    # Simulate second issue in queue at offset=1
    update = _message_update()
    ctx = _context(client)

    await show_global_issue_queue(update, ctx, offset=1)

    text = _replied_text(update)
    # Queue count is 2 and offset=1
    assert "2" in text
