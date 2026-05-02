from __future__ import annotations

import pytest

from bot.main import CONFIG_EDIT_STORE_KEY, callback_query, edit_reply_command, telegram_entity_text
from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_data_values,
    _callback_update,
    _context,
    _message_update,
)


@pytest.mark.asyncio
async def test_guided_edit_reply_previews_then_saves_latest_value() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")
    start_update = _message_update()

    await edit_reply_command(start_update, context)
    text_update = _message_update("Compare data ownership and export access first.")
    await telegram_entity_text(text_update, context)

    preview = text_update.message.replies[0]
    assert "Review Final reply" in preview["text"]
    assert "Confirmation required before saving." in preview["text"]
    assert "Compare data ownership" in preview["text"]
    assert "eng:edit:save" in _callback_data_values(preview["reply_markup"])
    assert "eng:edit:cancel" in _callback_data_values(preview["reply_markup"])
    assert client.edit_candidate_calls == []

    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    assert client.edit_candidate_calls == [
        {
            "candidate_id": "candidate-review",
            "final_reply": "Compare data ownership and export access first.",
            "edited_by": "telegram:123:@operator",
            "edit_reason": None,
        }
    ]
    assert "Saved Final reply." in save_update.callback_query.edits[0]["text"]
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None


@pytest.mark.asyncio
async def test_guided_edit_save_is_scoped_to_operator() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")

    await edit_reply_command(_message_update(), context)
    await telegram_entity_text(_message_update("Keep this scoped to the operator."), context)

    await callback_query(_callback_update("eng:edit:save", user_id=456), context)

    assert client.edit_candidate_calls == []
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is not None


@pytest.mark.asyncio
async def test_guided_edit_cancel_removes_only_callers_pending_edit() -> None:
    client = _FakeApiClient()
    context = _context(client, "candidate-review")

    await edit_reply_command(_message_update(), context)
    await telegram_entity_text(_message_update("Draft to cancel."), context)
    cancel_update = _callback_update("eng:edit:cancel")
    await callback_query(cancel_update, context)

    assert "Cancelled edit for Final reply." in cancel_update.callback_query.edits[0]["text"]
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None
    assert client.edit_candidate_calls == []
