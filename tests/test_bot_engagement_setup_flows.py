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

    assert "Creating engagement topic" in update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 5: Topic name" in update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "topic_create"
    assert pending.flow_step == "name"


@pytest.mark.asyncio
async def test_topic_inline_create_flow_previews_then_saves() -> None:
    client = _FakeApiClient()
    context = _context(client)
    start_update = _callback_update("eng:topic:create")
    name_update = _message_update("Founder outreach")
    guidance_update = _message_update("Be concise and practical.")
    triggers_update = _message_update("founder, b2b saas")
    description_update = _message_update("Startup operators")
    negative_update = _message_update("jobs, recruiting")
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(name_update, context)
    await telegram_entity_text(guidance_update, context)
    await telegram_entity_text(triggers_update, context)
    await telegram_entity_text(description_update, context)
    await telegram_entity_text(negative_update, context)
    await callback_query(save_update, context)

    assert "Step 2 of 5: Reply guidance" in name_update.message.replies[0]["text"]
    assert "Step 3 of 5: Trigger keywords" in guidance_update.message.replies[0]["text"]
    assert "Step 4 of 5: Topic description" in triggers_update.message.replies[0]["text"]
    assert "Step 5 of 5: Negative keywords" in description_update.message.replies[0]["text"]
    assert "Review Topic creation details" in negative_update.message.replies[0]["text"]
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
async def test_topic_inline_create_flow_allows_skipping_optional_fields() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("founder, b2b saas"), context)
    await telegram_entity_text(_message_update("-"), context)
    final_update = _message_update("-")

    await telegram_entity_text(final_update, context)

    assert "Description: -" in final_update.message.replies[0]["text"]
    assert "Avoid: -" in final_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_target_add_callback_starts_wizard() -> None:
    client = _FakeApiClient()
    context = _context(client)
    update = _callback_update("eng:admin:tna")

    await callback_query(update, context)

    text = update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 5: Community" in text
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"
    assert pending.flow_step == "target"
