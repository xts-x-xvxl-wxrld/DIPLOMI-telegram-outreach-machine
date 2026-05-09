from __future__ import annotations

import pytest

from bot.discovery_handlers import telegram_entity_text
from bot.engagement_approval_flow import APPROVAL_EDIT_STORE_KEY, get_pending_approval_edit
from bot.engagement_commands_daily import cancel_edit_command, resume_edit_command
from tests.test_bot_engagement_approval_handlers import (
    _FakeApiClient,
    _context,
    _message_update,
    _rendered_text,
)


def _command_context(client: _FakeApiClient, *args: str):
    ctx = _context(client)
    ctx.args = list(args)
    return ctx


@pytest.mark.asyncio
async def test_telegram_entity_text_routes_pending_approval_edit() -> None:
    client = _FakeApiClient()
    update = _message_update("This is too formal. Make it rougher.", user_id=42)
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

    await telegram_entity_text(update, ctx)

    assert client.edit_calls == [
        {"draft_id": "draft-abc", "edit_request": "This is too formal. Make it rougher."}
    ]
    assert client.home_calls == 1
    assert get_pending_approval_edit(ctx, 42) is None
    assert "Engagements" in _rendered_text(update)


@pytest.mark.asyncio
async def test_cancel_edit_command_cancels_pending_approval_edit() -> None:
    client = _FakeApiClient()
    update = _message_update("/cancel_edit", user_id=42)
    ctx = _context(client)

    store = ctx.application.bot_data.setdefault(APPROVAL_EDIT_STORE_KEY, {})
    store[42] = {"draft_id": "draft-abc", "started_at": "2026-04-28T00:00:00+00:00"}

    await cancel_edit_command(update, ctx)

    assert get_pending_approval_edit(ctx, 42) is None
    assert update.message.replies[0]["text"] == "Cancelled draft edit request."


@pytest.mark.asyncio
async def test_resume_edit_command_restores_pending_prompt_for_current_draft() -> None:
    client = _FakeApiClient()
    update = _message_update("/resume_edit", user_id=42)
    ctx = _command_context(client)

    await resume_edit_command(update, ctx)

    pending = get_pending_approval_edit(ctx, 42)
    assert pending is not None
    assert pending["draft_id"] == "draft-abc"
    assert "Request changes for Founder Circle" in update.message.replies[0]["text"]
    assert client.approval_calls == [{"offset": 0, "draft_id": None}]


@pytest.mark.asyncio
async def test_resume_edit_command_uses_explicit_draft_id() -> None:
    client = _FakeApiClient()
    update = _message_update("/resume_edit draft-xyz", user_id=42)
    ctx = _command_context(client, "draft-xyz")

    await resume_edit_command(update, ctx)

    pending = get_pending_approval_edit(ctx, 42)
    assert pending is not None
    assert pending["draft_id"] == "draft-xyz"
    assert "Dev Circle" in update.message.replies[0]["text"]
    assert client.approval_calls == [{"offset": 0, "draft_id": "draft-xyz"}]


@pytest.mark.asyncio
async def test_resume_edit_command_reports_missing_current_draft() -> None:
    client = _FakeApiClient()
    client._global_approvals = {
        "queue_count": 0,
        "updating_count": 0,
        "empty_state": "",
        "placeholders": [],
        "current": None,
    }
    update = _message_update("/resume_edit", user_id=42)
    ctx = _command_context(client)

    await resume_edit_command(update, ctx)

    assert get_pending_approval_edit(ctx, 42) is None
    assert update.message.replies[0]["text"] == "No draft is waiting for review right now."
