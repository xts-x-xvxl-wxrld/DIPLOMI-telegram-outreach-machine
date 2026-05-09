from __future__ import annotations

import pytest

from tests.test_bot_engagement_wizard import (
    _C_ENG_NEW,
    _C_TOPIC_1,
    _ENG_NEW_ID,
    _FakeWizardApiClient,
    _wiz_context,
    _wizard_through_step2,
    callback_query,
    _callback_update,
)
from bot.main import CONFIG_EDIT_STORE_KEY


@pytest.mark.asyncio
async def test_wizard_step5_confirm_success() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}"), context)

    confirm_update = _callback_update(f"eng:wz:confirm:{_ENG_NEW_ID}")
    await callback_query(confirm_update, context)

    assert client.wizard_confirm_calls
    assert client.wizard_confirm_calls[-1]["engagement_id"] == _ENG_NEW_ID
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None
    assert client.get_engagement_calls == [_ENG_NEW_ID]
    reply_text = confirm_update.callback_query.message.replies[0]["text"]
    assert "Engagement confirmed" in reply_text or "First results should appear" in reply_text
    edit_text = confirm_update.callback_query.edits[0]["text"]
    assert "Founder Circle" in edit_text
    assert "Approve draft" in edit_text


@pytest.mark.asyncio
async def test_wizard_step5_confirm_validation_failed() -> None:
    client = _FakeWizardApiClient()
    client._confirm_result = "validation_failed"
    client._confirm_message = "Topic is required."
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}"), context)

    confirm_update = _callback_update(f"eng:wz:confirm:{_ENG_NEW_ID}")
    await callback_query(confirm_update, context)

    edit_text = confirm_update.callback_query.edits[0]["text"]
    assert "Topic is required" in edit_text or "Validation" in edit_text or "Fix" in edit_text
    edit_markup = confirm_update.callback_query.edits[0]["reply_markup"]
    assert edit_markup is not None


@pytest.mark.asyncio
async def test_wizard_step5_confirm_stale_shows_retry() -> None:
    client = _FakeWizardApiClient()
    client._confirm_result = "stale"
    client._confirm_message = "Engagement data is out of date."
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}"), context)

    confirm_update = _callback_update(f"eng:wz:confirm:{_ENG_NEW_ID}")
    await callback_query(confirm_update, context)

    edit_text = confirm_update.callback_query.edits[0]["text"]
    assert "out of date" in edit_text or "Retry" in edit_text or "stale" in edit_text.lower()


@pytest.mark.asyncio
async def test_wizard_step5_confirm_api_error_shows_retry() -> None:
    client = _FakeWizardApiClient()
    client._raise_confirm = True
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}"), context)

    confirm_update = _callback_update(f"eng:wz:confirm:{_ENG_NEW_ID}")
    await callback_query(confirm_update, context)

    edit_text = confirm_update.callback_query.edits[0]["text"]
    assert "Retry" in edit_text or "Couldn't" in edit_text
    edit_markup = confirm_update.callback_query.edits[0]["reply_markup"]
    assert edit_markup is not None
