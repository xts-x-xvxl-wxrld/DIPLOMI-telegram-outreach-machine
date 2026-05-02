from __future__ import annotations

import pytest

from bot.main import CONFIG_EDIT_STORE_KEY, create_engagement_topic_command
from tests.test_bot_engagement_handlers import _FakeApiClient, _context, _message_update


@pytest.mark.asyncio
async def test_create_engagement_topic_command_without_args_starts_guided_flow() -> None:
    client = _FakeApiClient()
    update = _message_update()
    context = _context(client)

    await create_engagement_topic_command(update, context)

    assert "Creating draft brief" in update.message.replies[0]["text"]
    assert "Step 1 of 7: Topic name" in update.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "topic_create"
    assert pending.flow_step == "name"
    assert client.create_topic_calls == []
