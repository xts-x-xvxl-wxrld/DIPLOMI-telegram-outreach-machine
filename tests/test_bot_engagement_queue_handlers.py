from __future__ import annotations

import pytest

from test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_data_values,
    _callback_update,
    _context,
    _message_update,
    callback_query,
    engagement_candidate_command,
    engagement_candidates_command,
)


@pytest.mark.asyncio
async def test_engagement_candidates_approved_status_exposes_send_not_review() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_candidates_command(update, _context(client, "approved"))

    assert "Ready to send (1-1 of 1)" in update.message.replies[0]["text"]
    card = update.message.replies[1]
    callbacks = _callback_data_values(card["reply_markup"])
    assert "eng:cand:send:candidate-approved" in callbacks
    assert "eng:cand:approve:candidate-approved" not in callbacks
    assert client.list_candidate_calls[0]["status"] == "approved"


@pytest.mark.asyncio
async def test_engagement_candidates_needs_review_orders_freshest_first_within_page() -> None:
    client = _FakeApiClient()
    client.candidates_by_status["needs_review"] = {
        "items": [
            {
                "id": "candidate-aging",
                "community_title": "Founder Circle",
                "topic_name": "Open CRM",
                "status": "needs_review",
                "timeliness": "aging",
                "review_deadline_at": "2026-04-19T13:30:00+00:00",
                "reply_deadline_at": "2026-04-19T14:00:00+00:00",
                "source_excerpt": "Older thread about CRM migration.",
                "detected_reason": "The thread still has some activity.",
                "suggested_reply": "Migration planning matters here.",
            },
            {
                "id": "candidate-fresh",
                "community_title": "Builders Hub",
                "topic_name": "Automation",
                "status": "needs_review",
                "timeliness": "fresh",
                "review_deadline_at": "2026-04-19T12:30:00+00:00",
                "reply_deadline_at": "2026-04-19T13:00:00+00:00",
                "source_excerpt": "New automation thread.",
                "detected_reason": "The conversation is active right now.",
                "suggested_reply": "Share a practical automation tradeoff.",
            },
        ],
        "total": 2,
    }
    update = _message_update()

    await engagement_candidates_command(update, _context(client, "needs_review"))

    assert "Pending approvals (1-2 of 2)" in update.message.replies[0]["text"]
    assert "1. Builders Hub" in update.message.replies[1]["text"]
    assert "2. Founder Circle" in update.message.replies[2]["text"]


@pytest.mark.asyncio
async def test_engagement_candidate_command_opens_workspace_style_detail() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_candidate_command(update, _context(client, "candidate-review"))

    assert client.get_candidate_calls == ["candidate-review"]
    text = update.message.replies[0]["text"]
    assert "Source context" in text
    assert "Reply workspace" in text
    assert "Final reply: Matches the generated suggestion right now." in text
    assert "Next safe actions" in text


@pytest.mark.asyncio
async def test_candidate_open_callback_keeps_workspace_sections() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:cand:open:candidate-review")

    await callback_query(update, _context(client))

    text = update.callback_query.message.replies[0]["text"]
    assert "Source context" in text
    assert "Reply workspace" in text
    assert "Final reply: Matches the generated suggestion right now." in text


@pytest.mark.asyncio
async def test_engagement_candidate_detail_loads_settings_context_for_blocked_send() -> None:
    client = _FakeApiClient()
    client.settings = {
        **client.settings,
        "mode": "require_approval",
        "allow_post": False,
        "has_joined_engagement_account": True,
    }
    update = _message_update()

    await engagement_candidate_command(update, _context(client, "candidate-approved"))

    assert client.get_settings_calls == ["community-1"]
    text = update.message.replies[0]["text"]
    assert "Readiness: Blocked: posting permission off" in text
    assert "Fix now: open community settings and turn reviewed posting back on." in text
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:set:open:community-1" in callbacks
    assert "eng:actions:list:community-1:0" in callbacks
