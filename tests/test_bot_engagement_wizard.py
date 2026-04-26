from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bot.config_editing import PendingEditStore
from bot.main import (
    CONFIG_EDIT_STORE_KEY,
    WIZARD_RETURN_STORE_KEY,
    callback_query,
    telegram_entity_text,
)
from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_update,
    _context,
    _message_update,
)


def _command_update(text: str, args: list[str] | None = None, *, user_id: int = 123):
    msg = SimpleNamespace(
        text=text,
        replies=[],
        from_user=SimpleNamespace(id=user_id, username="operator"),
    )

    async def reply_text(t, reply_markup=None):
        msg.replies.append({"text": t, "reply_markup": reply_markup})

    msg.reply_text = reply_text
    ctx_args = args or []
    return SimpleNamespace(message=msg, callback_query=None), ctx_args


class _FakeWizardApiClient(_FakeApiClient):
    def __init__(self) -> None:
        super().__init__()
        self.create_target_calls: list[dict[str, Any]] = []
        self.start_detection_calls: list[dict[str, Any]] = []
        self.community_join_calls: list[dict[str, Any]] = []
        self.update_settings_calls: list[dict[str, Any]] = []
        self.update_target_calls: list[dict[str, Any]] = []
        self.update_topic_calls: list[dict[str, Any]] = []
        self._target_status = "resolved"
        self._raise_detection = False

    async def create_engagement_target(self, *, target_ref, added_by, notes=None, operator_user_id=None):
        call = {"target_ref": target_ref, "added_by": added_by}
        self.create_target_calls.append(call)
        return {
            "id": "target-new",
            "community_id": "community-new",
            "submitted_ref": target_ref,
            "status": self._target_status,
            "allow_join": False,
            "allow_detect": False,
            "allow_post": False,
        }

    async def update_engagement_target(self, target_id, operator_user_id=None, **updates):
        call = {"target_id": target_id, **updates}
        self.update_target_calls.append(call)
        return {"id": target_id, "status": updates.get("status", "resolved")}

    async def list_engagement_topics(self):
        return {"items": self.topics, "total": len(self.topics)}

    async def get_accounts(self):
        return self.accounts

    async def get_engagement_settings(self, community_id):
        self.get_settings_calls.append(community_id)
        return {**self.settings, "community_id": community_id}

    async def update_engagement_settings(self, community_id, *, operator_user_id=None, **payload):
        call = {"community_id": community_id, **payload}
        self.update_settings_calls.append(call)
        return {**self.settings, **payload}

    async def update_engagement_topic(self, topic_id, operator_user_id=None, **updates):
        call = {"topic_id": topic_id, **updates}
        self.update_topic_calls.append(call)
        return {"id": topic_id, **updates}

    async def start_community_join(self, community_id, *, telegram_account_id=None, requested_by=None):
        self.community_join_calls.append({"community_id": community_id, "account_id": telegram_account_id})
        return {"id": "join-job-1", "status": "queued"}

    async def start_engagement_detection(self, community_id, *, window_minutes=60, requested_by=None):
        if self._raise_detection:
            from bot.api_client import BotApiError
            raise BotApiError("Detection service unavailable")
        self.start_detection_calls.append({"community_id": community_id})
        return {"id": "detect-job-1", "status": "queued"}


def _wiz_context(client=None):
    ctx = _context(client or _FakeWizardApiClient())
    return ctx


@pytest.mark.asyncio
async def test_wizard_start_shows_community_prompt() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    update = _callback_update("eng:admin:tna")

    await callback_query(update, context)

    text = update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 5: Community" in text
    assert "t.me/" in text or "@handle" in text

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"
    assert pending.flow_step == "community"


@pytest.mark.asyncio
async def test_wizard_start_from_wizard_callback() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    update = _callback_update("eng:wz:start")

    await callback_query(update, context)

    text = update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 5: Community" in text
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"


@pytest.mark.asyncio
async def test_wizard_step1_valid_handle_advances_to_step2() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("@founders_hub")

    await telegram_entity_text(text_update, context)

    assert client.create_target_calls[-1]["target_ref"] == "@founders_hub"
    text = text_update.message.replies[0]["text"]
    assert "Step 2 of 5: Topics" in text
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending.flow_step == "topics"


@pytest.mark.asyncio
async def test_wizard_step1_invalid_text_reprompts() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("not a telegram link at all")

    await telegram_entity_text(text_update, context)

    assert not client.create_target_calls
    text = text_update.message.replies[0]["text"]
    assert "doesn't look like" in text or "t.me" in text.lower() or "@handle" in text


@pytest.mark.asyncio
async def test_wizard_step1_approved_target_exits_to_cockpit() -> None:
    client = _FakeWizardApiClient()
    client._target_status = "approved"
    context = _wiz_context(client)
    # mock engagement home
    client.capabilities = {"engagement_admin": True, "backend_capabilities_available": True}

    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("@already_approved")

    await telegram_entity_text(text_update, context)

    text = text_update.message.replies[0]["text"]
    assert "already active" in text or "approved" in text.lower()
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None


@pytest.mark.asyncio
async def test_wizard_step2_topic_toggle() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)

    # Toggle topic-1
    toggle_update = _callback_update("eng:wz:tp:topic-1")
    await callback_query(toggle_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert "topic-1" in (pending.flow_state or {}).get("topic_ids", [])
    # Toggle again to deselect
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert "topic-1" not in (pending.flow_state or {}).get("topic_ids", [])


@pytest.mark.asyncio
async def test_wizard_step2_continue_advances_to_step3() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": "acct-1", "phone": "+1*****11", "status": "available", "pool": "engagement"},
            {"id": "acct-2", "phone": "+1*****22", "status": "available", "pool": "engagement"},
        ],
    }
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    step3_update = _callback_update("eng:wz:step:3:community-new")

    await callback_query(step3_update, context)

    text = step3_update.callback_query.message.replies[0]["text"]
    assert "Step 3 of 5: Account" in text
    assert client.update_topic_calls, "Should have activated selected topics"


@pytest.mark.asyncio
async def test_wizard_step3_auto_picks_single_account() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 1},
        "items": [{"id": "acct-solo", "phone": "+1*****99", "status": "available", "pool": "engagement"}],
    }
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert (pending.flow_state or {}).get("account_id") == "acct-solo"
    # Should have triggered join
    assert client.community_join_calls


@pytest.mark.asyncio
async def test_wizard_step3_manual_account_pick() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": "acct-1", "phone": "+1*****11", "status": "available", "pool": "engagement"},
            {"id": "acct-2", "phone": "+1*****22", "status": "available", "pool": "engagement"},
        ],
    }
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)
    pick_update = _callback_update("eng:wz:ap:acct-2")

    await callback_query(pick_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("account_id") == "acct-2"
    assert client.community_join_calls[-1]["account_id"] == "acct-2"


@pytest.mark.asyncio
async def test_wizard_step4_level_watching_maps_to_observe() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)
    level_update = _callback_update("eng:wz:lv:watching:community-new")

    await callback_query(level_update, context)

    settings_call = client.update_settings_calls[-1]
    assert settings_call["mode"] == "observe"
    assert settings_call["allow_post"] is False


@pytest.mark.asyncio
async def test_wizard_step4_level_suggesting_maps_to_suggest() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)
    level_update = _callback_update("eng:wz:lv:suggesting:community-new")

    await callback_query(level_update, context)

    settings_call = client.update_settings_calls[-1]
    assert settings_call["mode"] == "suggest"
    assert settings_call["allow_post"] is False


@pytest.mark.asyncio
async def test_wizard_step4_level_sending_maps_to_require_approval() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)
    level_update = _callback_update("eng:wz:lv:sending:community-new")

    await callback_query(level_update, context)

    settings_call = client.update_settings_calls[-1]
    assert settings_call["mode"] == "require_approval"
    assert settings_call["allow_post"] is True


@pytest.mark.asyncio
async def test_wizard_step5_launch_success() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)
    await callback_query(_callback_update("eng:wz:lv:suggesting:community-new"), context)
    launch_update = _callback_update("eng:wz:go:community-new")

    await callback_query(launch_update, context)

    assert client.start_detection_calls
    assert client.start_detection_calls[-1]["community_id"] == "community-new"
    # Target should be approved
    assert any(c.get("status") == "approved" for c in client.update_target_calls)
    # Pending edit should be cleared
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None
    edit_text = launch_update.callback_query.edits[0]["text"]
    assert "Started" in edit_text or "✓" in edit_text


@pytest.mark.asyncio
async def test_wizard_step5_launch_enqueue_failure_shows_retry() -> None:
    client = _FakeWizardApiClient()
    client._raise_detection = True
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    await callback_query(_callback_update("eng:wz:tp:topic-1"), context)
    await callback_query(_callback_update("eng:wz:step:3:community-new"), context)
    await callback_query(_callback_update("eng:wz:lv:suggesting:community-new"), context)
    launch_update = _callback_update("eng:wz:go:community-new")

    await callback_query(launch_update, context)

    edit_text = launch_update.callback_query.edits[0]["text"]
    assert "Retry" in edit_text or "retry" in edit_text.lower() or "Could not" in edit_text
    edit_markup = launch_update.callback_query.edits[0]["reply_markup"]
    assert edit_markup is not None
    # Target should NOT be approved
    assert not any(c.get("status") == "approved" for c in client.update_target_calls)


@pytest.mark.asyncio
async def test_wizard_resume_skips_completed_steps() -> None:
    client = _FakeWizardApiClient()
    # Use 2 accounts so step 3 shows picker instead of auto-picking
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": "acct-a", "phone": "+1*****11", "status": "available", "pool": "engagement"},
            {"id": "acct-b", "phone": "+1*****22", "status": "available", "pool": "engagement"},
        ],
    }
    context = _wiz_context(client)
    store = context.application.bot_data.setdefault(CONFIG_EDIT_STORE_KEY, PendingEditStore())
    from bot.config_editing import editable_field

    editable = editable_field("wizard", "state")
    store.start(
        operator_id=123,
        field=editable,
        object_id="community-existing",
        flow_step="account",
        flow_state={
            "community_id": "community-existing",
            "target_id": "target-existing",
            "community_ref": "@existing",
            "topic_ids": ["topic-1"],
            "account_id": None,
            "level": None,
        },
    )
    resume_update = _callback_update("eng:wz:start")

    await callback_query(resume_update, context)

    text = resume_update.callback_query.message.replies[0]["text"]
    assert "Step 3 of 5: Account" in text


@pytest.mark.asyncio
async def test_wizard_cancel_clears_pending() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is not None

    cancel_update = _callback_update("eng:edit:cancel")
    await callback_query(cancel_update, context)

    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None


@pytest.mark.asyncio
async def test_wizard_topic_new_saves_wizard_state_and_starts_topic_create() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update("@test_community"), context)
    topic_new_update = _callback_update("eng:wz:tn")

    await callback_query(topic_new_update, context)

    # Wizard return state should be saved
    assert 123 in (context.application.bot_data.get(WIZARD_RETURN_STORE_KEY) or {})
    # Pending edit should now be topic_create
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "topic_create"
