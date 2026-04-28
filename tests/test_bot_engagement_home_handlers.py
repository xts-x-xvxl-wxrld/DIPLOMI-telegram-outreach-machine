"""Tests for Slice 7: Engagements Home And Navigation Shell.

Covers:
- format_cockpit_home: all four home states and correct copy.
- cockpit_home_markup: button visibility rules per state, no nav controls on home.
- callback_query routing: op:home routes to the new cockpit home, not the legacy operator home.
- op:approve, op:issues, op:engs, op:sent, op:add thin-router callbacks.
- Regression: the default engagement entrypoint no longer renders the legacy
  candidate-review home.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.formatting_engagement_home import format_cockpit_home
from bot.ui_engagement_home import cockpit_home_markup
from bot.ui import (
    ACTION_OP_HOME,
    ACTION_OP_APPROVE,
    ACTION_OP_ISSUES,
    ACTION_OP_ENGS,
    ACTION_OP_SENT,
    ACTION_OP_ADD,
    ACTION_ENGAGEMENT_APPROVAL_QUEUE,
    ACTION_ENGAGEMENT_ISSUE_QUEUE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _buttons(markup) -> list[Any]:
    return [btn for row in markup.inline_keyboard for btn in row]


def _callbacks(markup) -> list[str]:
    return [btn.callback_data for btn in _buttons(markup)]


def _labels(markup) -> list[str]:
    return [btn.text for btn in _buttons(markup)]


def _home_payload(
    *,
    state: str = "clear",
    draft_count: int = 0,
    issue_count: int = 0,
    active_engagement_count: int = 0,
    has_sent_messages: bool = False,
    latest_issue_preview: dict | None = None,
    next_draft_preview: dict | None = None,
) -> dict:
    return {
        "state": state,
        "draft_count": draft_count,
        "issue_count": issue_count,
        "active_engagement_count": active_engagement_count,
        "has_sent_messages": has_sent_messages,
        "latest_issue_preview": latest_issue_preview,
        "next_draft_preview": next_draft_preview,
    }


# ---------------------------------------------------------------------------
# format_cockpit_home — four states
# ---------------------------------------------------------------------------

def test_format_cockpit_home_first_run() -> None:
    text = format_cockpit_home(_home_payload(state="first_run"))

    assert "Engagements" in text
    assert "Add your first engagement" in text
    # Should not mention drafts or issues
    assert "draft" not in text.lower()
    assert "issue" not in text.lower()


def test_format_cockpit_home_approval_focused_single_draft() -> None:
    text = format_cockpit_home(_home_payload(state="approvals", draft_count=1))

    assert "Engagements" in text
    assert "1 draft need approval" in text


def test_format_cockpit_home_approval_focused_plural_drafts() -> None:
    text = format_cockpit_home(_home_payload(state="approvals", draft_count=2))

    assert "2 drafts need approval" in text


def test_format_cockpit_home_approval_focused_includes_issue_line_when_issues_exist() -> None:
    payload = _home_payload(
        state="approvals",
        draft_count=2,
        issue_count=1,
        latest_issue_preview={
            "issue_id": "iss-1",
            "issue_label": "Topics not chosen",
        },
    )

    text = format_cockpit_home(payload)

    assert "2 drafts need approval" in text
    assert "issue" in text.lower()
    assert "Topics not chosen" in text


def test_format_cockpit_home_approval_focused_no_issue_line_when_no_issues() -> None:
    text = format_cockpit_home(_home_payload(state="approvals", draft_count=3, issue_count=0))

    assert "3 drafts need approval" in text
    # No issue line
    lines = text.strip().splitlines()
    issue_lines = [ln for ln in lines if "issue" in ln.lower()]
    assert issue_lines == []


def test_format_cockpit_home_issues_present_single_issue() -> None:
    text = format_cockpit_home(_home_payload(state="issues", issue_count=1))

    assert "Engagements" in text
    assert "1 issue need attention" in text


def test_format_cockpit_home_issues_present_plural_issues() -> None:
    text = format_cockpit_home(_home_payload(state="issues", issue_count=3))

    assert "3 issues need attention" in text


def test_format_cockpit_home_clear_state_no_engagements() -> None:
    text = format_cockpit_home(_home_payload(state="clear", active_engagement_count=0))

    assert "Engagements" in text
    assert "No pending work" in text


def test_format_cockpit_home_clear_state_with_engagement_count() -> None:
    text = format_cockpit_home(_home_payload(state="clear", active_engagement_count=3))

    assert "No pending work" in text
    assert "3 active engagements" in text


def test_format_cockpit_home_clear_state_single_engagement() -> None:
    text = format_cockpit_home(_home_payload(state="clear", active_engagement_count=1))

    assert "1 active engagement" in text


# ---------------------------------------------------------------------------
# cockpit_home_markup — button visibility and ordering
# ---------------------------------------------------------------------------

def test_cockpit_home_markup_first_run_only_add_engagement() -> None:
    markup = cockpit_home_markup(_home_payload(state="first_run"))
    cb = _callbacks(markup)
    labels = _labels(markup)

    assert ACTION_OP_ADD in cb
    assert len(cb) == 1
    assert "Add engagement" in labels


def test_cockpit_home_markup_first_run_has_no_nav_controls() -> None:
    markup = cockpit_home_markup(_home_payload(state="first_run"))
    cb = _callbacks(markup)

    assert ACTION_OP_HOME not in cb
    assert "op:home" not in cb


def test_cockpit_home_markup_approval_focused_action_order() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="approvals", draft_count=2, issue_count=1)
    )
    labels = _labels(markup)

    approve_idx = next(i for i, l in enumerate(labels) if "Approve draft" in l)
    issues_idx = next(i for i, l in enumerate(labels) if "Top issues" in l)
    engs_idx = next(i for i, l in enumerate(labels) if l == "My engagements")
    add_idx = next(i for i, l in enumerate(labels) if l == "Add engagement")

    assert approve_idx < issues_idx < engs_idx < add_idx


def test_cockpit_home_markup_approval_focused_hides_sent_messages() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="approvals", draft_count=2, has_sent_messages=True)
    )
    cb = _callbacks(markup)

    assert ACTION_OP_SENT not in cb
    labels = _labels(markup)
    assert "Sent messages" not in labels


def test_cockpit_home_markup_approval_focused_hides_top_issues_when_none() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="approvals", draft_count=1, issue_count=0)
    )
    cb = _callbacks(markup)
    labels = _labels(markup)

    assert "Top issues" not in labels
    # Approval queue should be present
    approve_cbs = [c for c in cb if "appr" in c]
    assert len(approve_cbs) >= 1


def test_cockpit_home_markup_approval_focused_shows_draft_count() -> None:
    markup = cockpit_home_markup(_home_payload(state="approvals", draft_count=5))
    labels = _labels(markup)

    assert any("5" in l for l in labels)


def test_cockpit_home_markup_issues_action_order() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="issues", issue_count=2, has_sent_messages=True)
    )
    labels = _labels(markup)

    issues_idx = next(i for i, l in enumerate(labels) if "Top issues" in l)
    add_idx = next(i for i, l in enumerate(labels) if l == "Add engagement")
    engs_idx = next(i for i, l in enumerate(labels) if l == "My engagements")
    sent_idx = next(i for i, l in enumerate(labels) if l == "Sent messages")

    assert issues_idx < add_idx < engs_idx < sent_idx


def test_cockpit_home_markup_issues_shows_sent_messages() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="issues", issue_count=1, has_sent_messages=True)
    )
    labels = _labels(markup)

    assert "Sent messages" in labels


def test_cockpit_home_markup_issues_hides_sent_messages_when_none() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="issues", issue_count=1, has_sent_messages=False)
    )
    labels = _labels(markup)

    assert "Sent messages" not in labels


def test_cockpit_home_markup_clear_action_order() -> None:
    markup = cockpit_home_markup(
        _home_payload(state="clear", has_sent_messages=True, issue_count=1)
    )
    labels = _labels(markup)

    add_idx = next(i for i, l in enumerate(labels) if l == "Add engagement")
    engs_idx = next(i for i, l in enumerate(labels) if l == "My engagements")
    issues_idx = next(i for i, l in enumerate(labels) if "Top issues" in l)
    sent_idx = next(i for i, l in enumerate(labels) if l == "Sent messages")

    assert add_idx < engs_idx < issues_idx < sent_idx


def test_cockpit_home_markup_clear_hides_top_issues_when_none() -> None:
    markup = cockpit_home_markup(_home_payload(state="clear", issue_count=0))
    labels = _labels(markup)

    assert "Top issues" not in labels


def test_cockpit_home_markup_clear_shows_sent_messages_when_present() -> None:
    markup = cockpit_home_markup(_home_payload(state="clear", has_sent_messages=True))
    labels = _labels(markup)

    assert "Sent messages" in labels


def test_cockpit_home_markup_no_back_or_home_on_any_state() -> None:
    for state in ("first_run", "approvals", "issues", "clear"):
        markup = cockpit_home_markup(
            _home_payload(
                state=state,
                draft_count=1 if state == "approvals" else 0,
                issue_count=1 if state in ("approvals", "issues") else 0,
            )
        )
        labels = _labels(markup)
        cb = _callbacks(markup)
        assert "Back" not in labels, f"state={state}: found unexpected Back button"
        assert "Home" not in labels, f"state={state}: found unexpected Home button"
        assert ACTION_OP_HOME not in cb, f"state={state}: found op:home in callbacks"


def test_cockpit_home_markup_approval_queue_button_routes_to_appr_list() -> None:
    markup = cockpit_home_markup(_home_payload(state="approvals", draft_count=1))
    cb = _callbacks(markup)

    # Should route to eng:appr:list:0
    assert any("appr" in c and "list" in c for c in cb)


def test_cockpit_home_markup_issues_button_routes_to_iss_list() -> None:
    markup = cockpit_home_markup(_home_payload(state="issues", issue_count=1))
    cb = _callbacks(markup)

    assert any("iss" in c and "list" in c for c in cb)


# ---------------------------------------------------------------------------
# Callback routing tests — op:home wires to new cockpit, not legacy
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self) -> None:
        self.replies: list[dict] = []

    async def reply_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})


class _FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=123, username="operator")
        self.answers: list[dict] = []
        self.edits: list[dict] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


class _MinimalApiClient:
    """Minimal fake client that only supports get_engagement_cockpit_home."""

    def __init__(self, home_payload: dict) -> None:
        self._home = home_payload
        self.home_calls: int = 0
        # Stubs for other endpoints the handler chain might probe
        self._approvals = {
            "queue_count": 0,
            "updating_count": 0,
            "empty_state": "no_drafts",
            "placeholders": [],
            "current": None,
        }
        self._issues = {
            "queue_count": 0,
            "empty_state": "no_issues",
            "current": None,
        }
        self._engagements = {
            "items": [],
            "total": 0,
            "limit": 20,
            "offset": 0,
        }
        self._sent = {
            "items": [],
            "total": 0,
            "limit": 20,
            "offset": 0,
        }

    async def get_engagement_cockpit_home(self) -> dict:
        self.home_calls += 1
        return dict(self._home)

    async def get_engagement_cockpit_approvals(self) -> dict:
        return dict(self._approvals)

    async def get_engagement_cockpit_issues(self) -> dict:
        return dict(self._issues)

    async def list_engagement_cockpit_engagements(self, *, limit: int = 20, offset: int = 0) -> dict:
        return dict(self._engagements)

    async def list_engagement_cockpit_sent(self, *, limit: int = 20, offset: int = 0) -> dict:
        return dict(self._sent)


def _context_with(client: Any) -> SimpleNamespace:
    from bot.callback_handlers import API_CLIENT_KEY
    return SimpleNamespace(
        args=[],
        application=SimpleNamespace(bot_data={API_CLIENT_KEY: client}),
    )


def _callback_update(data: str) -> SimpleNamespace:
    query = _FakeCallbackQuery(data)
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=query.from_user,
    )


@pytest.mark.asyncio
async def test_op_home_routes_to_new_cockpit_home() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="clear", active_engagement_count=2)
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    assert client.home_calls == 1
    edits = update.callback_query.edits
    assert len(edits) == 1
    assert "Engagements" in edits[0]["text"]
    assert "No pending work" in edits[0]["text"]
    # Should NOT contain legacy operator cockpit copy
    assert "Operator cockpit" not in edits[0]["text"]


@pytest.mark.asyncio
async def test_op_home_first_run_renders_first_run_copy() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="first_run")
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    assert client.home_calls == 1
    edits = update.callback_query.edits
    assert len(edits) == 1
    text = edits[0]["text"]
    assert "Add your first engagement" in text
    markup = edits[0]["reply_markup"]
    labels = _labels(markup)
    assert "Add engagement" in labels
    assert len(labels) == 1


@pytest.mark.asyncio
async def test_op_home_approval_focused_hides_sent_messages() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(
        state="approvals",
        draft_count=2,
        has_sent_messages=True,
    )
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    markup = update.callback_query.edits[0]["reply_markup"]
    labels = _labels(markup)
    assert "Sent messages" not in labels


@pytest.mark.asyncio
async def test_op_home_issues_state_shows_sent_messages() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(
        state="issues",
        issue_count=1,
        has_sent_messages=True,
    )
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    markup = update.callback_query.edits[0]["reply_markup"]
    labels = _labels(markup)
    assert "Sent messages" in labels


@pytest.mark.asyncio
async def test_op_home_no_nav_controls_in_rendered_markup() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="clear")
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    markup = update.callback_query.edits[0]["reply_markup"]
    labels = _labels(markup)
    cb = _callbacks(markup)
    assert "Back" not in labels
    assert "Home" not in labels
    assert ACTION_OP_HOME not in cb


@pytest.mark.asyncio
async def test_op_approve_routes_to_approval_queue() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="approvals", draft_count=1)
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_APPROVE)
    context = _context_with(client)

    await callback_query(update, context)

    # approval flow uses reply_text (not edit_message_text)
    replies = update.callback_query.message.replies
    assert len(replies) == 1


@pytest.mark.asyncio
async def test_op_issues_routes_to_issue_queue() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="issues", issue_count=1)
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_ISSUES)
    context = _context_with(client)

    await callback_query(update, context)

    edits = update.callback_query.edits
    assert len(edits) == 1


@pytest.mark.asyncio
async def test_op_engs_routes_to_engagement_list() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="clear")
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_ENGS)
    context = _context_with(client)

    await callback_query(update, context)

    edits = update.callback_query.edits
    assert len(edits) == 1


@pytest.mark.asyncio
async def test_op_sent_routes_to_sent_messages() -> None:
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="clear", has_sent_messages=True)
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_SENT)
    context = _context_with(client)

    await callback_query(update, context)

    edits = update.callback_query.edits
    assert len(edits) == 1


# ---------------------------------------------------------------------------
# Regression: legacy candidate-review home must not render via op:home
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_op_home_does_not_render_legacy_operator_cockpit_copy() -> None:
    """Regression guard: op:home must not show the old 'Operator cockpit' surface."""
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="clear")
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    edits = update.callback_query.edits
    assert len(edits) == 1
    text = edits[0]["text"]
    assert "Operator cockpit" not in text
    assert "Discovery" not in text
    assert "Pending approvals" not in text
    assert "Ready to send" not in text


@pytest.mark.asyncio
async def test_op_home_does_not_render_legacy_engagement_home_copy() -> None:
    """Regression guard: op:home must not call the old _send_engagement_home."""
    from bot.callback_handlers import callback_query

    payload = _home_payload(state="clear")
    client = _MinimalApiClient(payload)
    update = _callback_update(ACTION_OP_HOME)
    context = _context_with(client)

    await callback_query(update, context)

    # Only one API call expected — get_engagement_cockpit_home
    assert client.home_calls == 1
