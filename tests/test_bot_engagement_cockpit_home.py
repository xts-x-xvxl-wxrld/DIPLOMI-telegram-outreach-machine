from __future__ import annotations

import pytest

from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _button_labels,
    _callback_update,
    _context,
    callback_query,
)


@pytest.mark.asyncio
async def test_engagement_home_callback_uses_task_first_cockpit_home() -> None:
    client = _FakeApiClient()
    update = _callback_update("eng:home")

    await callback_query(update, _context(client))

    assert client.list_candidate_calls == []
    assert update.callback_query.edits
    text = update.callback_query.edits[0]["text"]
    assert "Engagements" in text
    labels = _button_labels(update.callback_query.edits[0]["reply_markup"])
    assert any("Add engagement" in lbl for lbl in labels)
    assert any("My engagements" in lbl for lbl in labels)
