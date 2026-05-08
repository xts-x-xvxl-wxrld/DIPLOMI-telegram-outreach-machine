from __future__ import annotations

import pytest

from bot.config_editing import PendingEditStore, editable_field
from bot.main import CONFIG_EDIT_STORE_KEY, callback_query, telegram_entity_text
from tests.test_bot_engagement_handlers import _callback_update, _message_update
from tests.test_bot_engagement_wizard import (
    _ACCT_1_ID,
    _C_ENG_NEW,
    _C_TOPIC_1,
    _ENG_EDIT_ID,
    _ENG_NEW_ID,
    _FakeWizardApiClient,
    _TOPIC_1_ID,
    _wiz_context,
    _wizard_through_step2,
)


@pytest.mark.asyncio
async def test_wizard_review_shows_limits_and_quiet_hours() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    review_update = _callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}")

    await callback_query(review_update, context)

    text = review_update.callback_query.message.replies[0]["text"]
    assert "300 per day, 1 minute gap" in text
    assert "Quiet hours" in text
    assert "Off" in text
    assert "Timezone" in text
    assert "CET" in text


@pytest.mark.asyncio
async def test_wizard_quiet_hours_can_be_saved_from_review() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:qh:open:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:qh:tz_us_east:{_ENG_NEW_ID}"), context)

    quiet_hours_update = _message_update("22:00-08:00")
    await telegram_entity_text(quiet_hours_update, context)

    quiet_calls = [
        call
        for call in client.put_engagement_settings_calls
        if call.get("quiet_hours_start") == "22:00" and call.get("quiet_hours_end") == "08:00"
    ]
    assert quiet_calls
    assert quiet_calls[-1]["quiet_hours_timezone"] == "us_east"
    text = quiet_hours_update.message.replies[0]["text"]
    assert "22:00-08:00" in text
    assert "US East" in text


@pytest.mark.asyncio
async def test_wizard_quiet_hours_can_be_cleared_from_review() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:draft:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:qh:open:{_ENG_NEW_ID}"), context)
    clear_update = _callback_update(f"eng:wz:qh:off:{_ENG_NEW_ID}")

    await callback_query(clear_update, context)

    quiet_calls = [
        call
        for call in client.put_engagement_settings_calls
        if "quiet_hours_start" in call
        and "quiet_hours_end" in call
        and call.get("quiet_hours_start") is None
        and call.get("quiet_hours_end") is None
    ]
    assert quiet_calls
    assert quiet_calls[-1]["quiet_hours_timezone"] == "cet"
    text = clear_update.callback_query.message.replies[0]["text"]
    assert "Quiet hours" in text
    assert "Off" in text


@pytest.mark.asyncio
async def test_wizard_edit_reentry_mode_returns_to_review_after_save() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    store = context.application.bot_data.setdefault(CONFIG_EDIT_STORE_KEY, PendingEditStore())
    editable = editable_field("wizard", "state")
    store.start(
        operator_id=123,
        field=editable,
        object_id=_ENG_EDIT_ID,
        flow_step="review",
        flow_state={
            "engagement_id": _ENG_EDIT_ID,
            "target_id": "target-edit",
            "target_ref": "@edit_community",
            "topic_id": _TOPIC_1_ID,
            "account_id": _ACCT_1_ID,
            "mode": "draft",
            "return_callback": None,
        },
    )

    await callback_query(_callback_update(f"eng:wz:edit:{_ENG_EDIT_ID}:mode"), context)

    level_update = _callback_update(f"eng:wz:lv:auto_send:{_ENG_EDIT_ID}")
    await callback_query(level_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("mode") == "auto_send"
    assert (pending.flow_state or {}).get("return_callback") is None
    mode_calls = [c for c in client.put_engagement_settings_calls if c.get("mode") == "auto_limited"]
    assert mode_calls
    reply = level_update.callback_query.message.replies[0]
    assert "Step 5 of 5" in reply["text"]
