from __future__ import annotations

import pytest

from bot.config_editing import PendingEditStore, editable_field
from bot.main import CONFIG_EDIT_STORE_KEY, callback_query
from tests.test_bot_engagement_handlers import _callback_update
from tests.test_bot_engagement_wizard import (
    _ACCT_1_ID,
    _ENG_EDIT_ID,
    _FakeWizardApiClient,
    _TOPIC_1_ID,
    _wiz_context,
)


@pytest.mark.asyncio
async def test_wizard_edit_reentry_accepts_legacy_sending_mode_field() -> None:
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

    legacy_update = _callback_update(f"eng:wz:edit:{_ENG_EDIT_ID}:sending_mode")
    await callback_query(legacy_update, context)

    text = legacy_update.callback_query.message.replies[0]["text"]
    assert "Step 4 of 5" in text

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.flow_step == "mode"
