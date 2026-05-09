from __future__ import annotations

import asyncio

import pytest

from bot.engagement_approval_flow import APPROVAL_EDIT_STORE_KEY, get_pending_approval_edit, handle_edit_request_text
from tests.test_bot_engagement_approval_handlers import (
    _FakeApiClient,
    _context,
    _message_update,
    _rendered_text,
)


@pytest.mark.asyncio
async def test_edit_request_text_calls_backend_and_shows_confirmation() -> None:
    client = _FakeApiClient()
    update = _message_update("Please make it shorter.", user_id=42)
    ctx = _context(client)
    client._global_approvals = {
        "queue_count": 0,
        "updating_count": 0,
        "empty_state": "",
        "placeholders": [],
        "current": None,
    }

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}

    await handle_edit_request_text(update, ctx, text="Please make it shorter.", draft_id="draft-abc")

    assert client.edit_calls == [{"draft_id": "draft-abc", "edit_request": "Please make it shorter."}]
    assert client.home_calls == 1
    text = _rendered_text(update)
    assert "Engagements" in text


@pytest.mark.asyncio
async def test_edit_request_text_shows_revised_draft_when_replacement_is_ready() -> None:
    client = _FakeApiClient()
    update = _message_update("Make it rougher.", user_id=42)
    ctx = _context(client)

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}
    client._post_edit_scoped_approvals["eng-1"] = {
        "queue_count": 1,
        "updating_count": 0,
        "offset": 0,
        "empty_state": "none",
        "placeholders": [],
        "current": {
            "draft_id": "draft-new",
            "engagement_id": "eng-1",
            "target_label": "Founder Circle",
            "engagement_label": "CRM migration evaluation",
            "community_label": "@founder_circle",
            "source_excerpt": "We are comparing CRM ownership and integrations.",
            "text": "A rougher updated reply with less polish.",
            "why": "Relevant CRM discussion.",
            "badge": "Updated draft",
        },
    }

    await handle_edit_request_text(update, ctx, text="Make it rougher.", draft_id="draft-abc")

    text = _rendered_text(update)
    assert "Updated draft" in text
    assert "A rougher updated reply with less polish." in text
    assert client.scoped_approval_calls == [
        {"engagement_id": "eng-1", "offset": 0, "draft_id": None}
    ]
    assert get_pending_approval_edit(ctx, 42) is None


@pytest.mark.asyncio
async def test_edit_request_text_falls_back_to_placeholder_when_revised_draft_not_ready() -> None:
    client = _FakeApiClient()
    update = _message_update("Make it rougher.", user_id=42)
    ctx = _context(client)

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}
    client._post_edit_scoped_approvals["eng-1"] = {
        "queue_count": 0,
        "updating_count": 1,
        "offset": 0,
        "empty_state": "waiting_for_updates",
        "placeholders": [{"slot": 0, "label": "Updating draft"}],
        "current": None,
    }
    client._global_approvals = {
        "queue_count": 1,
        "updating_count": 1,
        "empty_state": "",
        "placeholders": [{"slot": 0, "label": "Updating draft"}],
        "current": None,
    }

    await handle_edit_request_text(update, ctx, text="Make it rougher.", draft_id="draft-abc")

    text = _rendered_text(update)
    assert "Approval queue" in text
    assert "updating" in text.lower()
    assert get_pending_approval_edit(ctx, 42) is None


@pytest.mark.asyncio
async def test_edit_request_text_clears_pending_edit() -> None:
    client = _FakeApiClient()
    update = _message_update("Make it punchier.", user_id=42)
    ctx = _context(client)

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}

    await handle_edit_request_text(update, ctx, text="Make it punchier.", draft_id="draft-abc")

    pending = get_pending_approval_edit(ctx, 42)
    assert pending is None


@pytest.mark.asyncio
async def test_edit_request_text_sends_delayed_notification_when_revised_draft_arrives_later() -> None:
    client = _FakeApiClient()
    update = _message_update("Make it rougher.", user_id=42, chat_id=4242)
    ctx = _context(client)
    ctx.application.bot_data["approval_update_notify_poll_attempts"] = 2
    ctx.application.bot_data["approval_update_notify_poll_interval_seconds"] = 0

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}
    client._post_edit_scoped_approvals["eng-1"] = [
        {
            "queue_count": 0,
            "updating_count": 1,
            "offset": 0,
            "empty_state": "waiting_for_updates",
            "placeholders": [{"slot": 0, "label": "Updating draft"}],
            "current": None,
        },
        {
            "queue_count": 1,
            "updating_count": 0,
            "offset": 0,
            "empty_state": "none",
            "placeholders": [],
            "current": {
                "draft_id": "draft-new",
                "engagement_id": "eng-1",
                "target_label": "Founder Circle",
                "engagement_label": "CRM migration evaluation",
                "community_label": "@founder_circle",
                "source_excerpt": "We are comparing CRM ownership and integrations.",
                "text": "A delayed updated reply with less polish.",
                "why": "Relevant CRM discussion.",
                "badge": "Updated draft",
            },
        },
    ]
    client._global_approvals = {
        "queue_count": 1,
        "updating_count": 1,
        "empty_state": "",
        "placeholders": [{"slot": 0, "label": "Updating draft"}],
        "current": None,
    }

    await handle_edit_request_text(update, ctx, text="Make it rougher.", draft_id="draft-abc")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    text = _rendered_text(update)
    assert "Approval queue" in text
    sent_messages = ctx.application.bot.sent_messages
    assert len(sent_messages) == 1
    assert sent_messages[0]["chat_id"] == 4242
    assert "Updated draft ready" in sent_messages[0]["text"]
    assert "A delayed updated reply with less polish." in sent_messages[0]["text"]


@pytest.mark.asyncio
async def test_edit_request_text_replaces_older_notification_watcher_for_same_operator() -> None:
    client = _FakeApiClient()
    first_update = _message_update("First rewrite.", user_id=42, chat_id=4242)
    second_update = _message_update("Second rewrite.", user_id=42, chat_id=4242)
    ctx = _context(client)
    ctx.application.bot_data["approval_update_notify_poll_attempts"] = 3
    ctx.application.bot_data["approval_update_notify_poll_interval_seconds"] = 0

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}
    client._edit_results = [
        {
            "result": "queued_update",
            "message": "Draft update queued.",
            "draft_id": "draft-abc",
            "engagement_id": "eng-1",
        },
        {
            "result": "queued_update",
            "message": "Draft update queued.",
            "draft_id": "draft-xyz",
            "engagement_id": "eng-2",
        },
    ]
    client._post_edit_scoped_approvals["eng-1"] = [
        {
            "queue_count": 0,
            "updating_count": 1,
            "offset": 0,
            "empty_state": "waiting_for_updates",
            "placeholders": [{"slot": 0, "label": "Updating draft"}],
            "current": None,
        },
        {
            "queue_count": 0,
            "updating_count": 1,
            "offset": 0,
            "empty_state": "waiting_for_updates",
            "placeholders": [{"slot": 0, "label": "Updating draft"}],
            "current": None,
        },
        {
            "queue_count": 1,
            "updating_count": 0,
            "offset": 0,
            "empty_state": "none",
            "placeholders": [],
            "current": {
                "draft_id": "draft-should-not-send",
                "engagement_id": "eng-1",
                "target_label": "Founder Circle",
                "engagement_label": "CRM migration evaluation",
                "community_label": "@founder_circle",
                "source_excerpt": "We are comparing CRM ownership and integrations.",
                "text": "This notification should be cancelled.",
                "why": "Relevant CRM discussion.",
                "badge": "Updated draft",
            },
        },
    ]
    client._post_edit_scoped_approvals["eng-2"] = [
        {
            "queue_count": 0,
            "updating_count": 1,
            "offset": 0,
            "empty_state": "waiting_for_updates",
            "placeholders": [{"slot": 0, "label": "Updating draft"}],
            "current": None,
        },
        {
            "queue_count": 1,
            "updating_count": 0,
            "offset": 0,
            "empty_state": "none",
            "placeholders": [],
            "current": {
                "draft_id": "draft-newest",
                "engagement_id": "eng-2",
                "target_label": "Dev Circle",
                "engagement_label": "Developer outreach",
                "community_label": "@dev_circle",
                "source_excerpt": "How are people handling outbound personalization at scale?",
                "text": "Only the newest watcher should notify.",
                "why": "Follow up on the target's last thread.",
                "badge": "Updated draft",
            },
        },
    ]
    client._global_approvals = {
        "queue_count": 1,
        "updating_count": 1,
        "empty_state": "",
        "placeholders": [{"slot": 0, "label": "Updating draft"}],
        "current": None,
    }

    await handle_edit_request_text(first_update, ctx, text="First rewrite.", draft_id="draft-abc")
    store[42] = {"draft_id": "draft-xyz", "started_at": "2026-04-28T00:01:00+00:00"}
    await handle_edit_request_text(second_update, ctx, text="Second rewrite.", draft_id="draft-xyz")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    sent_messages = ctx.application.bot.sent_messages
    assert len(sent_messages) == 1
    assert "Only the newest watcher should notify." in sent_messages[0]["text"]
    assert "This notification should be cancelled." not in sent_messages[0]["text"]
