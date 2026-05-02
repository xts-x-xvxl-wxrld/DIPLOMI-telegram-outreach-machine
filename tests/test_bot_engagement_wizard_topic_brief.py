from __future__ import annotations

import pytest

from bot.main import CONFIG_EDIT_STORE_KEY, WIZARD_RETURN_STORE_KEY, callback_query, telegram_entity_text
from tests.test_bot_engagement_wizard import (
    _C_ENG_NEW,
    _ENG_NEW_ID,
    _FakeWizardApiClient,
    _callback_update,
    _message_update,
    _wiz_context,
    _wizard_through_step2,
)


@pytest.mark.asyncio
async def test_wizard_step2_create_topic_starts_subflow_and_saves_return_state() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("@founders_hub")
    await telegram_entity_text(text_update, context)
    markup = text_update.message.replies[0]["reply_markup"]
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert f"eng:wz:tpnew:{_C_ENG_NEW}" in callbacks
    assert "Create topic" in " ".join(labels)

    create_update = _callback_update(f"eng:wz:tpnew:{_C_ENG_NEW}")
    await callback_query(create_update, context)

    text = create_update.callback_query.message.replies[0]["text"]
    assert "Creating draft brief" in text
    assert "Step 1 of 7: Topic name" in text
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "topic_create"
    assert pending.flow_step == "name"
    wizard_return = context.application.bot_data[WIZARD_RETURN_STORE_KEY][123]
    assert wizard_return["engagement_id"] == _ENG_NEW_ID


@pytest.mark.asyncio
async def test_wizard_topic_create_save_returns_to_step2_with_new_topic_selected() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tpnew:{_C_ENG_NEW}"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(
        _message_update("Startup operators asking about outbound outreach"),
        context,
    )
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(
        _message_update("Brief, transparent, no links unless asked."),
        context,
    )
    await telegram_entity_text(
        _message_update("Compare data ownership and export access first."),
        context,
    )
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("Buy our tool now."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(
        _message_update("No DMs, no fake customer claims."),
        context,
    )
    save_update = _callback_update("eng:edit:save")

    await callback_query(save_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"
    assert pending.flow_step == "topics"
    assert (pending.flow_state or {}).get("topic_id") == "topic-created"
    assert client.patch_engagement_calls[-1]["topic_id"] == "topic-created"
    text = save_update.callback_query.message.replies[0]["text"]
    assert "Step 2 of 5" in text
