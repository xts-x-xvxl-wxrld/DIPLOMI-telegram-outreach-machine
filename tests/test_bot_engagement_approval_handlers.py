from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.engagement_approval_flow import (
    APPROVAL_EDIT_STORE_KEY,
    cancel_pending_approval_edit,
    get_pending_approval_edit,
    handle_approve_confirm,
    handle_approve_confirmed,
    handle_edit_request_start,
    handle_edit_request_text,
    handle_reject_confirm,
    handle_reject_confirmed,
    scoped_queue_empty_callback,
    show_draft_card,
    show_global_approval_queue,
    show_scoped_approval_queue,
)
from bot.formatting_engagement_approval import (
    format_approval_queue_empty,
    format_approval_queue_header,
    format_approval_placeholder_only,
    format_approve_confirm,
    format_draft_card,
    format_edit_request_prompt,
    format_edit_submitted,
    format_approval_result,
    format_reject_confirm,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=123, username="operator")
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


class _FakeUpdate:
    def __init__(self, *, callback_data: str | None = None, message_text: str | None = None, user_id: int = 123) -> None:
        if callback_data is not None:
            self.callback_query = _FakeCallbackQuery(callback_data, user_id=user_id)
            self.message = None
        else:
            self.callback_query = None
            self.message = _FakeMessage(text=message_text)
        self.effective_user = SimpleNamespace(id=user_id)


class _FakeApiClient:
    def __init__(self) -> None:
        self.approval_calls: list[str] = []
        self.scoped_approval_calls: list[str] = []
        self.approve_calls: list[str] = []
        self.reject_calls: list[str] = []
        self.edit_calls: list[dict[str, Any]] = []

        self._global_approvals: dict[str, Any] = {
            "queue_count": 1,
            "updating_count": 0,
            "empty_state": "",
            "placeholders": [],
            "current": {
                "draft_id": "draft-abc",
                "engagement_id": "eng-1",
                "target_label": "Founder Circle",
                "text": "Compare ownership and integrations first.",
                "why": "Relevant CRM discussion.",
                "badge": None,
            },
        }

        self._scoped_approvals: dict[str, Any] = {
            "queue_count": 1,
            "updating_count": 0,
            "empty_state": "",
            "placeholders": [],
            "current": {
                "draft_id": "draft-abc",
                "engagement_id": "eng-1",
                "target_label": "Founder Circle",
                "text": "Compare ownership and integrations first.",
                "why": "Relevant CRM discussion.",
                "badge": None,
            },
        }

        self._approve_result: dict[str, Any] = {
            "result": "approved",
            "message": "Draft approved and scheduled.",
            "draft_id": "draft-abc",
            "engagement_id": "eng-1",
        }

        self._reject_result: dict[str, Any] = {
            "result": "rejected",
            "message": "Draft rejected.",
            "draft_id": "draft-abc",
            "engagement_id": "eng-1",
        }

        self._edit_result: dict[str, Any] = {
            "result": "queued_update",
            "message": "Draft update queued.",
            "draft_id": "draft-abc",
            "engagement_id": "eng-1",
        }

    async def get_engagement_cockpit_approvals(self) -> dict[str, Any]:
        self.approval_calls.append("global")
        return dict(self._global_approvals)

    async def get_engagement_cockpit_approvals_for_engagement(self, engagement_id: str) -> dict[str, Any]:
        self.scoped_approval_calls.append(engagement_id)
        return dict(self._scoped_approvals)

    async def approve_engagement_cockpit_draft(self, draft_id: str) -> dict[str, Any]:
        self.approve_calls.append(draft_id)
        return dict(self._approve_result)

    async def reject_engagement_cockpit_draft(self, draft_id: str) -> dict[str, Any]:
        self.reject_calls.append(draft_id)
        return dict(self._reject_result)

    async def edit_engagement_cockpit_draft(
        self,
        draft_id: str,
        *,
        edit_request: str,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        self.edit_calls.append({"draft_id": draft_id, "edit_request": edit_request})
        return dict(self._edit_result)


def _context(client: _FakeApiClient) -> Any:
    bot_data: dict[str, Any] = {"api_client": client}
    application = SimpleNamespace(bot_data=bot_data)
    return SimpleNamespace(application=application, user_data={})


def _callback_update(data: str, *, user_id: int = 123) -> _FakeUpdate:
    return _FakeUpdate(callback_data=data, user_id=user_id)


def _message_update(text: str = "hello", *, user_id: int = 123) -> _FakeUpdate:
    return _FakeUpdate(message_text=text, user_id=user_id)


def _callback_data_values(markup: Any) -> list[str]:
    if markup is None:
        return []
    rows = getattr(markup, "inline_keyboard", [])
    result = []
    for row in rows:
        for button in row:
            cd = getattr(button, "callback_data", None)
            if cd:
                result.append(cd)
    return result


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------

def test_format_draft_card_includes_fields() -> None:
    data = {
        "draft_id": "draft-abc",
        "engagement_id": "eng-1",
        "target_label": "Founder Circle",
        "text": "Compare ownership and integrations.",
        "why": "Relevant CRM discussion.",
        "badge": None,
    }
    text = format_draft_card(data)
    assert "Founder Circle" in text
    assert "draft-abc" in text
    assert "Compare ownership" in text
    assert "Relevant CRM" in text


def test_format_draft_card_with_index() -> None:
    data = {
        "draft_id": "draft-abc",
        "engagement_id": "eng-1",
        "target_label": "Founder Circle",
        "text": "Some message text.",
        "why": "Why this draft.",
        "badge": "urgent",
    }
    text = format_draft_card(data, index=2)
    assert "2. Founder Circle" in text
    assert "urgent" in text


def test_format_approval_queue_header_with_items() -> None:
    data = {
        "queue_count": 3,
        "updating_count": 0,
        "empty_state": "",
        "current": {"draft_id": "draft-abc"},
    }
    text = format_approval_queue_header(data)
    assert "3" in text
    assert "pending" in text.lower() or "queue" in text.lower()


def test_format_approval_queue_empty_global() -> None:
    text = format_approval_queue_empty(scoped=False)
    assert "No drafts for approval" in text


def test_format_approval_queue_empty_scoped() -> None:
    text = format_approval_queue_empty(scoped=True)
    assert "No drafts" in text


def test_format_approval_placeholder_only() -> None:
    text = format_approval_placeholder_only()
    assert "Waiting for updated drafts" in text or "updating" in text.lower()


def test_format_approve_confirm_has_key_fields() -> None:
    draft_data = {"target_label": "Founder Circle", "text": "Reply text here."}
    text = format_approve_confirm("draft-abc", draft_data)
    assert "Founder Circle" in text
    assert "draft-abc" in text
    assert "Approve" in text or "approve" in text


def test_format_reject_confirm_has_key_fields() -> None:
    draft_data = {"target_label": "Founder Circle", "text": "Reply text here."}
    text = format_reject_confirm("draft-abc", draft_data)
    assert "Founder Circle" in text
    assert "draft-abc" in text
    assert "Reject" in text or "reject" in text


def test_format_edit_request_prompt_has_draft_id() -> None:
    draft_data = {"target_label": "Founder Circle", "text": "Reply text."}
    text = format_edit_request_prompt("draft-abc", draft_data)
    assert "draft-abc" in text
    assert "edit" in text.lower() or "Edit" in text


def test_format_edit_submitted_shows_result() -> None:
    result = {"result": "queued_update", "message": "Draft update queued."}
    text = format_edit_submitted("draft-abc", result)
    assert "draft-abc" in text
    assert "queued_update" in text or "queued" in text.lower()


def test_format_approval_result_approved() -> None:
    result = {"result": "approved", "message": "Draft approved."}
    text = format_approval_result(result, draft_id="draft-abc", action="approved")
    assert "approved" in text
    assert "draft-abc" in text


def test_format_approval_result_stale() -> None:
    result = {"result": "stale", "message": "Draft is stale."}
    text = format_approval_result(result, draft_id="draft-abc", action="approved")
    assert "stale" in text


# ---------------------------------------------------------------------------
# show_global_approval_queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_global_queue_shows_header_and_draft_card() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:list:0")
    ctx = _context(client)

    await show_global_approval_queue(update, ctx)

    replies = update.callback_query.message.replies
    assert len(replies) >= 2
    assert "draft-abc" in replies[1]["text"] or "Founder Circle" in replies[1]["text"]
    assert client.approval_calls == ["global"]


@pytest.mark.asyncio
async def test_global_queue_empty_shows_empty_message() -> None:
    client = _FakeApiClient()
    client._global_approvals = {
        "queue_count": 0,
        "updating_count": 0,
        "empty_state": "",
        "placeholders": [],
        "current": None,
    }
    update = _callback_update("eng:appr:list:0")
    ctx = _context(client)

    await show_global_approval_queue(update, ctx)

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    assert "No drafts for approval" in replies[0]["text"]


@pytest.mark.asyncio
async def test_global_queue_all_placeholders_shows_waiting() -> None:
    client = _FakeApiClient()
    client._global_approvals = {
        "queue_count": 2,
        "updating_count": 2,
        "empty_state": "",
        "placeholders": [
            {"slot": 1, "label": "Updating draft"},
            {"slot": 2, "label": "Updating draft"},
        ],
        "current": None,
    }
    update = _callback_update("eng:appr:list:0")
    ctx = _context(client)

    await show_global_approval_queue(update, ctx)

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "Waiting for updated drafts" in text or "updating" in text.lower()


@pytest.mark.asyncio
async def test_global_queue_draft_card_has_approve_reject_buttons() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:list:0")
    ctx = _context(client)

    await show_global_approval_queue(update, ctx)

    replies = update.callback_query.message.replies
    assert len(replies) >= 2
    card_reply = replies[1]
    callbacks = _callback_data_values(card_reply["reply_markup"])
    assert any("appr:ok:draft-abc" in cb for cb in callbacks)
    assert any("appr:no:draft-abc" in cb for cb in callbacks)


# ---------------------------------------------------------------------------
# show_scoped_approval_queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scoped_queue_shows_drafts_for_engagement() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:eng:eng-1")
    ctx = _context(client)

    await show_scoped_approval_queue(update, ctx, engagement_id="eng-1")

    assert client.scoped_approval_calls == ["eng-1"]
    replies = update.callback_query.message.replies
    assert len(replies) >= 2


@pytest.mark.asyncio
async def test_scoped_queue_empty_stores_engagement_id_and_shows_message() -> None:
    client = _FakeApiClient()
    client._scoped_approvals = {
        "queue_count": 0,
        "updating_count": 0,
        "empty_state": "",
        "placeholders": [],
        "current": None,
    }
    update = _callback_update("eng:appr:eng:eng-1")
    ctx = _context(client)

    await show_scoped_approval_queue(update, ctx, engagement_id="eng-1")

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    assert "No drafts" in replies[0]["text"]
    assert ctx.user_data.get("last_scoped_engagement_id") == "eng-1"


@pytest.mark.asyncio
async def test_scoped_queue_all_placeholders_shows_waiting() -> None:
    client = _FakeApiClient()
    client._scoped_approvals = {
        "queue_count": 1,
        "updating_count": 1,
        "empty_state": "",
        "placeholders": [{"slot": 1, "label": "Updating draft"}],
        "current": None,
    }
    update = _callback_update("eng:appr:eng:eng-1")
    ctx = _context(client)

    await show_scoped_approval_queue(update, ctx, engagement_id="eng-1")

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "Waiting for updated drafts" in text or "updating" in text.lower()


# ---------------------------------------------------------------------------
# scoped_queue_empty_callback
# ---------------------------------------------------------------------------

def test_scoped_queue_empty_callback_returns_correct_string() -> None:
    result = scoped_queue_empty_callback("eng-1")
    assert result == "eng:det:open:eng-1"


# ---------------------------------------------------------------------------
# show_draft_card
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_show_draft_card_renders_card_with_actions() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:open:draft-abc")
    ctx = _context(client)

    await show_draft_card(update, ctx, draft_id="draft-abc")

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "draft-abc" in text
    callbacks = _callback_data_values(replies[0]["reply_markup"])
    assert any("appr:ok:draft-abc" in cb for cb in callbacks)
    assert any("appr:no:draft-abc" in cb for cb in callbacks)
    assert any("appr:edit:draft-abc" in cb for cb in callbacks)


@pytest.mark.asyncio
async def test_show_draft_card_for_non_current_draft_still_renders() -> None:
    client = _FakeApiClient()
    # Make the global queue return a different draft
    client._global_approvals["current"]["draft_id"] = "draft-xyz"
    update = _callback_update("eng:appr:open:draft-abc")
    ctx = _context(client)

    await show_draft_card(update, ctx, draft_id="draft-abc")

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    # Should still render with the draft_id we requested
    text = replies[0]["text"]
    assert "draft-abc" in text


# ---------------------------------------------------------------------------
# handle_approve_confirm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_confirm_shows_confirmation_without_backend_call() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:ok:draft-abc")
    ctx = _context(client)

    await handle_approve_confirm(update, ctx, draft_id="draft-abc")

    # No approve call yet
    assert client.approve_calls == []
    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "draft-abc" in text
    assert "Approve" in text or "approve" in text
    callbacks = _callback_data_values(replies[0]["reply_markup"])
    assert any("appr:okc:draft-abc" in cb for cb in callbacks)


# ---------------------------------------------------------------------------
# handle_approve_confirmed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_confirmed_calls_backend_and_shows_result() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:okc:draft-abc")
    ctx = _context(client)

    await handle_approve_confirmed(update, ctx, draft_id="draft-abc")

    assert client.approve_calls == ["draft-abc"]
    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "approved" in text.lower()
    assert "draft-abc" in text


@pytest.mark.asyncio
async def test_approve_confirmed_shows_stale_result() -> None:
    client = _FakeApiClient()
    client._approve_result = {
        "result": "stale",
        "message": "Draft already processed.",
        "draft_id": "draft-abc",
    }
    update = _callback_update("eng:appr:okc:draft-abc")
    ctx = _context(client)

    await handle_approve_confirmed(update, ctx, draft_id="draft-abc")

    replies = update.callback_query.message.replies
    text = replies[0]["text"]
    assert "stale" in text


# ---------------------------------------------------------------------------
# handle_reject_confirm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_confirm_shows_confirmation_without_backend_call() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:no:draft-abc")
    ctx = _context(client)

    await handle_reject_confirm(update, ctx, draft_id="draft-abc")

    assert client.reject_calls == []
    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "draft-abc" in text
    assert "Reject" in text or "reject" in text
    callbacks = _callback_data_values(replies[0]["reply_markup"])
    assert any("appr:noc:draft-abc" in cb for cb in callbacks)


# ---------------------------------------------------------------------------
# handle_reject_confirmed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_confirmed_calls_backend_and_shows_result() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:noc:draft-abc")
    ctx = _context(client)

    await handle_reject_confirmed(update, ctx, draft_id="draft-abc")

    assert client.reject_calls == ["draft-abc"]
    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "rejected" in text.lower()
    assert "draft-abc" in text


# ---------------------------------------------------------------------------
# handle_edit_request_start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edit_request_start_prompts_user_and_stores_pending() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:edit:draft-abc", user_id=42)
    ctx = _context(client)

    await handle_edit_request_start(update, ctx, draft_id="draft-abc")

    # No backend edit call yet
    assert client.edit_calls == []
    replies = update.callback_query.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "draft-abc" in text
    assert "edit" in text.lower() or "Edit" in text

    # Pending edit is stored
    pending = get_pending_approval_edit(ctx, 42)
    assert pending is not None
    assert pending["draft_id"] == "draft-abc"


@pytest.mark.asyncio
async def test_edit_request_start_no_user_id_replies_error() -> None:
    client = _FakeApiClient()
    # Create an update with no user id
    update = _FakeUpdate(callback_data="eng:appr:edit:draft-abc")
    update.callback_query.from_user = SimpleNamespace(id=None)
    update.effective_user = None
    ctx = _context(client)

    await handle_edit_request_start(update, ctx, draft_id="draft-abc")

    replies = update.callback_query.message.replies
    assert len(replies) == 1
    assert "user ID" in replies[0]["text"]


# ---------------------------------------------------------------------------
# handle_edit_request_text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edit_request_text_calls_backend_and_shows_confirmation() -> None:
    client = _FakeApiClient()
    update = _message_update("Please make it shorter.", user_id=42)
    ctx = _context(client)

    # Pre-store a pending edit
    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}

    await handle_edit_request_text(update, ctx, text="Please make it shorter.", draft_id="draft-abc")

    assert client.edit_calls == [{"draft_id": "draft-abc", "edit_request": "Please make it shorter."}]
    replies = update.message.replies
    assert len(replies) == 1
    text = replies[0]["text"]
    assert "draft-abc" in text
    assert "queued" in text.lower() or "queued_update" in text


@pytest.mark.asyncio
async def test_edit_request_text_clears_pending_edit() -> None:
    client = _FakeApiClient()
    update = _message_update("Make it punchier.", user_id=42)
    ctx = _context(client)

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}

    await handle_edit_request_text(update, ctx, text="Make it punchier.", draft_id="draft-abc")

    # Should be cleared
    pending = get_pending_approval_edit(ctx, 42)
    assert pending is None


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def test_get_pending_approval_edit_returns_none_if_missing() -> None:
    client = _FakeApiClient()
    ctx = _context(client)
    assert get_pending_approval_edit(ctx, 99) is None


def test_cancel_pending_approval_edit_removes_entry() -> None:
    client = _FakeApiClient()
    ctx = _context(client)

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}

    result = cancel_pending_approval_edit(ctx, 42)
    assert result is not None
    assert result["draft_id"] == "draft-abc"
    assert get_pending_approval_edit(ctx, 42) is None


def test_cancel_pending_approval_edit_returns_none_if_missing() -> None:
    client = _FakeApiClient()
    ctx = _context(client)
    result = cancel_pending_approval_edit(ctx, 99)
    assert result is None


# ---------------------------------------------------------------------------
# Multiple result states
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_confirmed_blocked_result() -> None:
    client = _FakeApiClient()
    client._approve_result = {
        "result": "blocked",
        "message": "Draft approval is blocked.",
        "draft_id": "draft-abc",
    }
    update = _callback_update("eng:appr:okc:draft-abc")
    ctx = _context(client)

    await handle_approve_confirmed(update, ctx, draft_id="draft-abc")

    replies = update.callback_query.message.replies
    text = replies[0]["text"]
    assert "blocked" in text


@pytest.mark.asyncio
async def test_reject_confirmed_stale_result() -> None:
    client = _FakeApiClient()
    client._reject_result = {
        "result": "stale",
        "message": "Draft already processed.",
        "draft_id": "draft-abc",
    }
    update = _callback_update("eng:appr:noc:draft-abc")
    ctx = _context(client)

    await handle_reject_confirmed(update, ctx, draft_id="draft-abc")

    replies = update.callback_query.message.replies
    text = replies[0]["text"]
    assert "stale" in text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_global_queue_with_no_current_but_queue_count_nonzero() -> None:
    client = _FakeApiClient()
    client._global_approvals = {
        "queue_count": 3,
        "updating_count": 0,
        "empty_state": "",
        "placeholders": [],
        "current": None,  # No current draft exposed yet
    }
    update = _callback_update("eng:appr:list:0")
    ctx = _context(client)

    await show_global_approval_queue(update, ctx)

    replies = update.callback_query.message.replies
    # Should render the header at minimum
    assert len(replies) >= 1


@pytest.mark.asyncio
async def test_scoped_queue_shows_draft_card_with_edit_button() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:appr:eng:eng-1")
    ctx = _context(client)

    await show_scoped_approval_queue(update, ctx, engagement_id="eng-1")

    replies = update.callback_query.message.replies
    assert len(replies) >= 2
    card_reply = replies[1]
    callbacks = _callback_data_values(card_reply["reply_markup"])
    assert any("appr:edit:draft-abc" in cb for cb in callbacks)
