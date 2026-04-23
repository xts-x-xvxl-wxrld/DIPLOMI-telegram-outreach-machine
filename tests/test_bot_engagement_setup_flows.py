from __future__ import annotations

import pytest

from bot.main import CONFIG_EDIT_STORE_KEY, callback_query, telegram_entity_text
from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_update,
    _context,
    _message_update,
)


@pytest.mark.asyncio
async def test_topic_create_callback_starts_guided_create() -> None:
    client = _FakeApiClient()
    context = _context(client)
    update = _callback_update("eng:topic:create")

    await callback_query(update, context)

    assert "Editing Topic creation details" in update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "topic_create"


@pytest.mark.asyncio
async def test_topic_inline_create_flow_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:topic:create")
    text_update = _message_update(
        "Founder outreach | Be concise and practical. | founder, b2b saas | Startup operators | jobs, recruiting"
    )
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(text_update, context)
    await callback_query(save_update, context)

    assert "Review Topic creation details" in text_update.message.replies[0]["text"]
    assert client.create_topic_calls[-1] == {
        "name": "Founder outreach",
        "description": "Startup operators",
        "stance_guidance": "Be concise and practical.",
        "trigger_keywords": ["founder", "b2b saas"],
        "negative_keywords": ["jobs", "recruiting"],
        "active": True,
    }
    assert "Engagement topic created." in save_update.callback_query.edits[0]["text"]
    assert "Avoid: jobs, recruiting" in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_target_add_callback_starts_guided_create() -> None:
    client = _FakeApiClient()
    context = _context(client)
    update = _callback_update("eng:admin:tna")

    await callback_query(update, context)

    assert "Editing Target creation details" in update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "target_create"


@pytest.mark.asyncio
async def test_target_inline_create_flow_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:admin:tna")
    text_update = _message_update("@opencrm | Priority pool")
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(text_update, context)
    await callback_query(save_update, context)

    assert "Review Target creation details" in text_update.message.replies[0]["text"]
    assert client.create_target_calls[-1] == {
        "target_ref": "@opencrm",
        "added_by": "telegram:123:@operator",
        "notes": "Priority pool",
    }
    assert "Engagement target added." in save_update.callback_query.edits[0]["text"]
