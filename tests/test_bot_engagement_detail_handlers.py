"""Tests for engagement detail flow handlers and formatters."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.formatting_engagement_detail import (
    format_engagement_list,
    format_engagement_row,
    format_engagement_detail,
    format_sent_messages,
    format_sent_message_row,
)
from bot.ui_engagement_detail import (
    engagement_list_markup,
    engagement_detail_markup,
    sent_messages_markup,
)
from bot.engagement_detail_flow import (
    show_engagement_list,
    show_engagement_preview,
    show_engagement_detail,
    handle_engagement_resume,
    show_sent_messages,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeCallbackQuery:
    def __init__(self, data: str = "eng:mine:list:0") -> None:
        self.data = data
        self.edits: list[dict[str, Any]] = []
        self.answers: list[dict[str, Any]] = []

    async def edit_message_text(self, text: str, reply_markup: Any | None = None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})


class _FakeUpdate:
    def __init__(self, callback_data: str = "eng:mine:list:0") -> None:
        self.callback_query = _FakeCallbackQuery(callback_data)
        self.message = None


class _FakeContext:
    def __init__(self, client: Any) -> None:
        self.application = SimpleNamespace(bot_data={"api_client": client})
        self.user_data: dict[str, Any] = {}


class _FakeApiClient:
    def __init__(self) -> None:
        self.list_engagements_calls: list[dict[str, Any]] = []
        self.get_engagement_calls: list[str] = []
        self.list_sent_calls: list[dict[str, Any]] = []
        self.raise_error: str | None = None

        self.engagements = [
            {
                "engagement_id": "eng-1",
                "primary_label": "Open CRM",
                "community_label": "Founder Circle",
                "sending_mode_label": "Draft",
                "issue_count": 2,
                "pending_task": {
                    "task_kind": "approvals",
                    "label": "Approve draft",
                    "count": 1,
                    "resume_callback": "eng:appr:list:0",
                },
                "created_at": "2026-04-20T10:00:00Z",
            },
            {
                "engagement_id": "eng-2",
                "primary_label": "Automation",
                "community_label": "Dev Circle",
                "sending_mode_label": "Auto send",
                "issue_count": 0,
                "pending_task": None,
                "created_at": "2026-04-19T10:00:00Z",
            },
        ]

        self.engagement_detail = {
            "engagement_id": "eng-1",
            "target_label": "Founder Circle",
            "topic_label": "Open CRM",
            "account_label": "@mybot",
            "sending_mode_label": "Draft",
            "approval_count": 1,
            "issue_count": 2,
            "pending_task": {
                "task_kind": "approvals",
                "label": "Approve draft",
                "count": 1,
                "resume_callback": "eng:appr:list:0",
            },
        }

        self.sent_messages = [
            {
                "action_id": "act-1",
                "message_text": "Compare ownership and integrations first.",
                "community_label": "Founder Circle",
                "sent_at": "2026-04-20T10:00:00Z",
            },
            {
                "action_id": "act-2",
                "message_text": "Automation tradeoffs are worth discussing.",
                "community_label": "Dev Circle",
                "sent_at": "2026-04-19T11:00:00Z",
            },
        ]

    async def list_engagement_cockpit_engagements(
        self, *, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        from bot.api_client import BotApiError
        if self.raise_error:
            raise BotApiError(self.raise_error)
        self.list_engagements_calls.append({"limit": limit, "offset": offset})
        items = self.engagements[offset : offset + limit]
        return {
            "items": items,
            "total": len(self.engagements),
            "offset": offset,
            "limit": limit,
        }

    async def get_engagement_cockpit_engagement(self, engagement_id: str) -> dict[str, Any]:
        from bot.api_client import BotApiError
        if self.raise_error:
            raise BotApiError(self.raise_error)
        self.get_engagement_calls.append(engagement_id)
        detail = dict(self.engagement_detail)
        detail["engagement_id"] = engagement_id
        return detail

    async def list_engagement_cockpit_sent(
        self, *, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        from bot.api_client import BotApiError
        if self.raise_error:
            raise BotApiError(self.raise_error)
        self.list_sent_calls.append({"limit": limit, "offset": offset})
        items = self.sent_messages[offset : offset + limit]
        return {
            "items": items,
            "total": len(self.sent_messages),
            "offset": offset,
            "limit": limit,
        }


def _callback_data(markup: Any | None) -> list[str]:
    if markup is None:
        return []
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if getattr(button, "callback_data", None)
    ]


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------

class TestFormatEngagementList:
    def test_empty(self):
        payload = {"items": [], "total": 0, "offset": 0, "limit": 20}
        assert format_engagement_list(payload) == "No engagements"

    def test_single_page(self):
        payload = {
            "items": [{"engagement_id": "e1"}],
            "total": 1,
            "offset": 0,
            "limit": 20,
        }
        result = format_engagement_list(payload)
        assert "My engagements" in result
        assert "1-1 of 1" in result

    def test_second_page(self):
        items = [{"engagement_id": f"e{i}"} for i in range(5)]
        payload = {"items": items, "total": 25, "offset": 20, "limit": 5}
        result = format_engagement_list(payload)
        assert "21-25 of 25" in result


class TestFormatEngagementRow:
    def test_basic_row(self):
        eng = {
            "engagement_id": "eng-1",
            "primary_label": "Open CRM",
            "community_label": "Founder Circle",
            "sending_mode_label": "Draft",
            "issue_count": 0,
        }
        result = format_engagement_row(eng)
        assert "Open CRM" in result
        assert "[Draft]" in result
        assert "Founder Circle" in result

    def test_row_with_issues(self):
        eng = {
            "engagement_id": "eng-1",
            "primary_label": "Open CRM",
            "community_label": "Founder Circle",
            "sending_mode_label": "Auto send",
            "issue_count": 3,
        }
        result = format_engagement_row(eng)
        assert "[3 issues]" in result

    def test_row_single_issue(self):
        eng = {
            "engagement_id": "eng-1",
            "primary_label": "Open CRM",
            "community_label": "Test",
            "sending_mode_label": "Draft",
            "issue_count": 1,
        }
        result = format_engagement_row(eng)
        assert "[1 issue]" in result

    def test_row_zero_issues_no_badge(self):
        eng = {
            "engagement_id": "eng-1",
            "primary_label": "Open CRM",
            "community_label": "Test",
            "sending_mode_label": "Draft",
            "issue_count": 0,
        }
        result = format_engagement_row(eng)
        assert "issue" not in result


class TestFormatEngagementDetail:
    def test_full_detail(self):
        payload = {
            "engagement_id": "eng-1",
            "target_label": "Founder Circle",
            "topic_label": "Open CRM",
            "account_label": "@mybot",
            "sending_mode_label": "Draft",
            "approval_count": 1,
            "issue_count": 2,
            "pending_task": None,
        }
        result = format_engagement_detail(payload)
        assert "Founder Circle" in result
        assert "Open CRM" in result
        assert "@mybot" in result
        assert "Draft" in result
        assert "1" in result
        assert "2" in result

    def test_pending_task_shown(self):
        payload = {
            "engagement_id": "eng-1",
            "target_label": "Target",
            "topic_label": "Topic",
            "account_label": "Account",
            "sending_mode_label": "Draft",
            "approval_count": 1,
            "issue_count": 0,
            "pending_task": {
                "task_kind": "approvals",
                "label": "Approve draft",
                "count": 1,
                "resume_callback": "eng:appr:list:0",
            },
        }
        result = format_engagement_detail(payload)
        assert "Approve draft" in result

    def test_no_pending_task(self):
        payload = {
            "engagement_id": "eng-1",
            "target_label": "Target",
            "topic_label": "Topic",
            "account_label": "Account",
            "sending_mode_label": "Draft",
            "approval_count": 0,
            "issue_count": 0,
            "pending_task": None,
        }
        result = format_engagement_detail(payload)
        assert "Pending task" not in result

    def test_missing_optional_fields(self):
        payload = {
            "engagement_id": "eng-1",
            "target_label": "Target",
            "sending_mode_label": "Draft",
            "approval_count": 0,
            "issue_count": 0,
        }
        result = format_engagement_detail(payload)
        assert "Target" in result
        assert "-" in result  # missing optional fields fall back to "-"


class TestFormatSentMessages:
    def test_empty(self):
        payload = {"items": [], "total": 0, "offset": 0, "limit": 20}
        assert format_sent_messages(payload) == "No sent messages"

    def test_with_items(self):
        payload = {
            "items": [{"action_id": "a1"}],
            "total": 1,
            "offset": 0,
            "limit": 20,
        }
        result = format_sent_messages(payload)
        assert "Sent messages" in result
        assert "1-1 of 1" in result

    def test_pagination_range(self):
        items = [{"action_id": f"a{i}"} for i in range(5)]
        payload = {"items": items, "total": 30, "offset": 20, "limit": 5}
        result = format_sent_messages(payload)
        assert "21-25 of 30" in result


class TestFormatSentMessageRow:
    def test_full_row(self):
        msg = {
            "action_id": "act-1",
            "message_text": "Compare ownership and integrations first.",
            "community_label": "Founder Circle",
            "sent_at": "2026-04-20T10:00:00Z",
        }
        result = format_sent_message_row(msg)
        assert "Compare ownership" in result
        assert "Founder Circle" in result
        assert "2026-04-20" in result

    def test_long_text_truncated(self):
        msg = {
            "action_id": "act-1",
            "message_text": "x" * 300,
            "community_label": "Circle",
            "sent_at": "2026-04-20T10:00:00Z",
        }
        result = format_sent_message_row(msg)
        # Should be truncated - the row text should be shorter than 300 chars
        lines = result.split("\n")
        assert len(lines[0]) < 300

    def test_missing_fields(self):
        msg = {"message_text": "Hello world"}
        result = format_sent_message_row(msg)
        assert "Hello world" in result


# ---------------------------------------------------------------------------
# Markup tests
# ---------------------------------------------------------------------------

class TestEngagementListMarkup:
    def test_empty_list(self):
        markup = engagement_list_markup([], offset=0, total=0)
        # Should still return a markup object with navigation
        assert markup is not None
        callbacks = _callback_data(markup)
        assert "eng:home" in callbacks
        assert "op:home" not in callbacks

    def test_items_produce_buttons(self):
        items = [
            {
                "engagement_id": "eng-1",
                "primary_label": "Open CRM",
                "community_label": "Founder Circle",
                "sending_mode_label": "Draft",
                "issue_count": 0,
            }
        ]
        markup = engagement_list_markup(items, offset=0, total=1)
        keyboard = markup.inline_keyboard
        # Should have at least one row with a button for the engagement
        all_buttons = [btn for row in keyboard for btn in row]
        cb_data = [btn.callback_data for btn in all_buttons if hasattr(btn, "callback_data")]
        assert any("eng-1" in d for d in cb_data)

    def test_pager_not_shown_when_fits(self):
        items = [
            {
                "engagement_id": f"eng-{i}",
                "primary_label": f"Eng {i}",
                "community_label": "Circle",
                "sending_mode_label": "Draft",
                "issue_count": 0,
            }
            for i in range(3)
        ]
        markup = engagement_list_markup(items, offset=0, total=3, page_size=20)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        cb_data = [btn.callback_data for btn in all_buttons if hasattr(btn, "callback_data")]
        assert not any("Newer" in d or "Older" in d for d in cb_data)

    def test_pager_shown_when_more(self):
        items = [
            {
                "engagement_id": f"eng-{i}",
                "primary_label": f"Eng {i}",
                "community_label": "Circle",
                "sending_mode_label": "Draft",
                "issue_count": 0,
            }
            for i in range(20)
        ]
        markup = engagement_list_markup(items, offset=0, total=40, page_size=20)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        labels = [btn.text for btn in all_buttons if hasattr(btn, "text")]
        assert any("Older" in lbl for lbl in labels)


class TestEngagementDetailMarkup:
    def test_no_pending_task(self):
        markup = engagement_detail_markup("eng-1", pending_task=None)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        cb_data = [btn.callback_data for btn in all_buttons if hasattr(btn, "callback_data")]
        # Should not have a resume button
        assert not any("resume" in d for d in cb_data)

    def test_pending_task_approvals(self):
        pending_task = {
            "task_kind": "approvals",
            "label": "Approve draft",
            "count": 1,
            "resume_callback": "eng:appr:list:0",
        }
        markup = engagement_detail_markup("eng-1", pending_task=pending_task)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        cb_data = [btn.callback_data for btn in all_buttons if hasattr(btn, "callback_data")]
        assert any("resume" in d for d in cb_data)

    def test_pending_task_issues(self):
        pending_task = {
            "task_kind": "issues",
            "label": "Top issues",
            "count": 2,
            "resume_callback": "eng:iss:list:0",
        }
        markup = engagement_detail_markup("eng-1", pending_task=pending_task)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        labels = [btn.text for btn in all_buttons if hasattr(btn, "text")]
        assert any("Top issues" in lbl for lbl in labels)

    def test_edit_buttons_present(self):
        markup = engagement_detail_markup("eng-1", pending_task=None)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        cb_data = [btn.callback_data for btn in all_buttons if hasattr(btn, "callback_data")]
        assert any("topic" in d for d in cb_data)
        assert any("account" in d for d in cb_data)
        assert any("mode" in d for d in cb_data)
        assert "eng:home" in cb_data
        assert "op:home" not in cb_data


class TestSentMessagesMarkup:
    def test_no_pager_when_fits(self):
        markup = sent_messages_markup(offset=0, total=5, page_size=20)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        labels = [btn.text for btn in all_buttons if hasattr(btn, "text")]
        assert not any("Newer" in lbl or "Older" in lbl for lbl in labels)
        callbacks = _callback_data(markup)
        assert "eng:home" in callbacks
        assert "op:home" not in callbacks

    def test_older_shown_when_more(self):
        markup = sent_messages_markup(offset=0, total=40, page_size=20)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        labels = [btn.text for btn in all_buttons if hasattr(btn, "text")]
        assert any("Older" in lbl for lbl in labels)

    def test_newer_shown_on_second_page(self):
        markup = sent_messages_markup(offset=20, total=40, page_size=20)
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        labels = [btn.text for btn in all_buttons if hasattr(btn, "text")]
        assert any("Newer" in lbl for lbl in labels)


# ---------------------------------------------------------------------------
# Flow handler tests
# ---------------------------------------------------------------------------

class TestShowEngagementList:
    @pytest.mark.asyncio
    async def test_renders_list(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_list(update, context, offset=0)
        assert len(update.callback_query.edits) == 1
        text = update.callback_query.edits[0]["text"]
        assert "My engagements" in text

    @pytest.mark.asyncio
    async def test_empty_state(self):
        client = _FakeApiClient()
        client.engagements = []
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_list(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "No engagements" in text

    @pytest.mark.asyncio
    async def test_api_error(self):
        client = _FakeApiClient()
        client.raise_error = "Service unavailable"
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_list(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "Couldn't load" in text or "Service unavailable" in text

    @pytest.mark.asyncio
    async def test_passes_offset(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_list(update, context, offset=20)
        assert client.list_engagements_calls[0]["offset"] == 20

    @pytest.mark.asyncio
    async def test_shows_rows(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_list(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "Open CRM" in text
        assert "Automation" in text


class TestShowEngagementPreview:
    @pytest.mark.asyncio
    async def test_renders_preview(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_preview(update, context, engagement_id="eng-1")
        assert len(update.callback_query.edits) == 1
        text = update.callback_query.edits[0]["text"]
        assert "Founder Circle" in text or "Engagement detail" in text

    @pytest.mark.asyncio
    async def test_api_error(self):
        client = _FakeApiClient()
        client.raise_error = "Not found"
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_preview(update, context, engagement_id="eng-x")
        text = update.callback_query.edits[0]["text"]
        assert "Couldn't load" in text or "Not found" in text


class TestShowEngagementDetail:
    @pytest.mark.asyncio
    async def test_renders_detail(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_detail(update, context, engagement_id="eng-1")
        text = update.callback_query.edits[0]["text"]
        assert "Founder Circle" in text
        assert "Open CRM" in text

    @pytest.mark.asyncio
    async def test_shows_pending_task(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_detail(update, context, engagement_id="eng-1")
        text = update.callback_query.edits[0]["text"]
        assert "Approve draft" in text

    @pytest.mark.asyncio
    async def test_no_pending_task(self):
        client = _FakeApiClient()
        client.engagement_detail = {
            **client.engagement_detail,
            "pending_task": None,
        }
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_detail(update, context, engagement_id="eng-1")
        text = update.callback_query.edits[0]["text"]
        assert "Pending task" not in text

    @pytest.mark.asyncio
    async def test_markup_has_edit_buttons(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_detail(update, context, engagement_id="eng-1")
        markup = update.callback_query.edits[0]["reply_markup"]
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        cb_data = [btn.callback_data for btn in all_buttons if hasattr(btn, "callback_data")]
        assert any("topic" in d for d in cb_data)

    @pytest.mark.asyncio
    async def test_api_error(self):
        client = _FakeApiClient()
        client.raise_error = "Not found"
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_engagement_detail(update, context, engagement_id="eng-x")
        text = update.callback_query.edits[0]["text"]
        assert "Couldn't load" in text


class TestHandleEngagementResume:
    @pytest.mark.asyncio
    async def test_no_pending_task_shows_detail(self):
        client = _FakeApiClient()
        client.engagement_detail = {
            **client.engagement_detail,
            "pending_task": None,
        }
        update = _FakeUpdate()
        context = _FakeContext(client)
        await handle_engagement_resume(update, context, engagement_id="eng-1")
        # Should fall back to showing the detail view
        text = update.callback_query.edits[0]["text"]
        assert "Engagement detail" in text

    @pytest.mark.asyncio
    async def test_no_resume_callback_shows_detail(self):
        client = _FakeApiClient()
        client.engagement_detail = {
            **client.engagement_detail,
            "pending_task": {
                "task_kind": "approvals",
                "label": "Approve draft",
                "count": 1,
                "resume_callback": None,
            },
        }
        update = _FakeUpdate()
        context = _FakeContext(client)
        await handle_engagement_resume(update, context, engagement_id="eng-1")
        text = update.callback_query.edits[0]["text"]
        assert "Engagement detail" in text

    @pytest.mark.asyncio
    async def test_resume_callback_stored(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        dispatched: list[str] = []

        async def _dispatch(_update: Any, _context: Any, *, data: str) -> None:
            dispatched.append(data)

        context._dispatch_callback = _dispatch
        await handle_engagement_resume(update, context, engagement_id="eng-1")
        assert dispatched == ["eng:appr:list:0"]
        assert update.callback_query.edits == []

    @pytest.mark.asyncio
    async def test_api_error(self):
        client = _FakeApiClient()
        client.raise_error = "Service down"
        update = _FakeUpdate()
        context = _FakeContext(client)
        await handle_engagement_resume(update, context, engagement_id="eng-1")
        text = update.callback_query.edits[0]["text"]
        assert "Couldn't resume" in text or "Service down" in text


class TestShowSentMessages:
    @pytest.mark.asyncio
    async def test_renders_list(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_sent_messages(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "Sent messages" in text

    @pytest.mark.asyncio
    async def test_shows_rows(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_sent_messages(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "Compare ownership" in text
        assert "Founder Circle" in text

    @pytest.mark.asyncio
    async def test_empty_state(self):
        client = _FakeApiClient()
        client.sent_messages = []
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_sent_messages(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "No sent messages" in text

    @pytest.mark.asyncio
    async def test_api_error(self):
        client = _FakeApiClient()
        client.raise_error = "DB error"
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_sent_messages(update, context, offset=0)
        text = update.callback_query.edits[0]["text"]
        assert "Couldn't load" in text or "DB error" in text

    @pytest.mark.asyncio
    async def test_passes_offset(self):
        client = _FakeApiClient()
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_sent_messages(update, context, offset=20)
        assert client.list_sent_calls[0]["offset"] == 20

    @pytest.mark.asyncio
    async def test_markup_has_pager(self):
        client = _FakeApiClient()
        # Simulate 40 total messages
        client.sent_messages = [
            {
                "action_id": f"act-{i}",
                "message_text": f"Message {i}",
                "community_label": "Circle",
                "sent_at": "2026-04-20T10:00:00Z",
            }
            for i in range(20)
        ]
        # Patch total
        original = client.list_engagement_cockpit_sent

        async def patched(**kwargs: Any) -> dict[str, Any]:
            result = await original(**kwargs)
            result["total"] = 40
            return result

        client.list_engagement_cockpit_sent = patched
        update = _FakeUpdate()
        context = _FakeContext(client)
        await show_sent_messages(update, context, offset=0)
        markup = update.callback_query.edits[0]["reply_markup"]
        keyboard = markup.inline_keyboard
        all_buttons = [btn for row in keyboard for btn in row]
        labels = [btn.text for btn in all_buttons if hasattr(btn, "text")]
        assert any("Older" in lbl for lbl in labels)
