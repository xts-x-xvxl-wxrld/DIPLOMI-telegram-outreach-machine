from __future__ import annotations

from typing import Any

import pytest

from bot.config_editing import PendingEditStore
from bot.main import (
    CONFIG_EDIT_STORE_KEY,
    callback_query,
    telegram_entity_text,
)
from bot.ui_common import compact_uuid
from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_update,
    _context,
    _message_update,
)

# ---------------------------------------------------------------------------
# UUID fixtures — must be real UUIDs since compact_uuid encodes UUID bytes
# ---------------------------------------------------------------------------

_TOPIC_1_ID = "11111111-1111-1111-1111-111111111111"
_TOPIC_2_ID = "22222222-2222-2222-2222-222222222222"
_ENG_NEW_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_ACCT_1_ID = "33333333-3333-3333-3333-333333333333"
_ACCT_2_ID = "44444444-4444-4444-4444-444444444444"
_ACCT_SOLO_ID = "55555555-5555-5555-5555-555555555555"
_ACCT_A_ID = "66666666-6666-6666-6666-666666666666"
_ACCT_B_ID = "77777777-7777-7777-7777-777777777777"
_ENG_EXISTING_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_ENG_EDIT_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
_ENG_XYZ_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"

# Pre-computed compact forms used in callback strings
_C_TOPIC_1 = compact_uuid(_TOPIC_1_ID)
_C_TOPIC_2 = compact_uuid(_TOPIC_2_ID)
_C_ENG_NEW = compact_uuid(_ENG_NEW_ID)
_C_ACCT_2 = compact_uuid(_ACCT_2_ID)
_C_ACCT_SOLO = compact_uuid(_ACCT_SOLO_ID)


# ---------------------------------------------------------------------------
# Fake API client for wizard tests
# ---------------------------------------------------------------------------


class _FakeWizardApiClient(_FakeApiClient):
    def __init__(self) -> None:
        super().__init__()
        self.create_target_calls: list[dict[str, Any]] = []
        self.resolve_target_calls: list[dict[str, Any]] = []
        self.get_target_calls: list[str] = []
        self.create_engagement_calls: list[dict[str, Any]] = []
        self.patch_engagement_calls: list[dict[str, Any]] = []
        self.put_engagement_settings_calls: list[dict[str, Any]] = []
        self.wizard_confirm_calls: list[dict[str, Any]] = []
        self.wizard_retry_calls: list[dict[str, Any]] = []
        self.community_join_calls: list[dict[str, Any]] = []
        self._target_status = "resolved"
        self._resolved_target_status = "resolved"
        self._confirm_result = "confirmed"
        self._confirm_message = "Engagement confirmed"
        self._raise_confirm = False
        self._raise_retry = False
        self._join_action_status = "queued"
        self._join_action_error: str | None = None
        self._raise_start_join = False
        # Override base-class topics with real UUIDs
        self.topics = [
            {
                "id": _TOPIC_1_ID,
                "name": "Open CRM",
                "stance_guidance": "Be factual, brief, and non-salesy.",
                "trigger_keywords": ["crm", "open source"],
                "negative_keywords": [],
                "example_good_replies": ["Compare export paths first."],
                "example_bad_replies": ["Buy our tool now."],
                "active": True,
            },
            {
                "id": _TOPIC_2_ID,
                "name": "DevOps",
                "stance_guidance": "Focus on reliability.",
                "trigger_keywords": ["devops", "ci"],
                "negative_keywords": [],
                "example_good_replies": [],
                "example_bad_replies": [],
                "active": True,
            },
        ]

    async def create_engagement_target(self, *, target_ref, added_by, notes=None, operator_user_id=None):
        call = {"target_ref": target_ref, "added_by": added_by}
        self.create_target_calls.append(call)
        community_id = None if self._target_status == "pending" else "community-new"
        return {
            "id": "target-new",
            "community_id": community_id,
            "submitted_ref": target_ref,
            "status": self._target_status,
            "allow_join": False,
            "allow_detect": False,
            "allow_post": False,
        }

    async def resolve_engagement_target(self, target_id, *, requested_by=None, operator_user_id=None):
        self.resolve_target_calls.append(
            {
                "target_id": target_id,
                "requested_by": requested_by,
                "operator_user_id": operator_user_id,
            }
        )
        return {"job": {"id": "resolve-job-1", "status": "queued"}}

    async def get_engagement_target(self, target_id):
        self.get_target_calls.append(target_id)
        community_id = (
            "community-new"
            if self._resolved_target_status in {"resolved", "approved"}
            else None
        )
        return {
            "id": target_id,
            "community_id": community_id,
            "submitted_ref": "@resolved_target",
            "status": self._resolved_target_status,
            "allow_join": False,
            "allow_detect": False,
            "allow_post": False,
            "last_error": None,
        }

    async def create_engagement(self, *, target_id, created_by):
        call = {"target_id": target_id, "created_by": created_by}
        self.create_engagement_calls.append(call)
        return {
            "result": "created",
            "engagement": {
                "id": _ENG_NEW_ID,
                "target_id": target_id,
                "community_id": "community-new",
                "topic_id": None,
                "status": "draft",
                "name": None,
                "created_by": created_by,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        }

    async def patch_engagement(self, engagement_id, *, topic_id=None, name=None):
        call = {"engagement_id": engagement_id, "topic_id": topic_id, "name": name}
        self.patch_engagement_calls.append(call)
        return {"result": "updated", "engagement": {"id": engagement_id, "topic_id": topic_id}}

    async def put_engagement_settings(self, engagement_id, *, assigned_account_id=None, mode=None):
        call = {"engagement_id": engagement_id, "assigned_account_id": assigned_account_id, "mode": mode}
        self.put_engagement_settings_calls.append(call)
        return {"result": "updated", "settings": {"engagement_id": engagement_id, "mode": mode}}

    async def wizard_confirm_engagement(self, engagement_id, *, requested_by=None):
        call = {"engagement_id": engagement_id, "requested_by": requested_by}
        self.wizard_confirm_calls.append(call)
        if self._raise_confirm:
            from bot.api_client import BotApiError
            raise BotApiError("Confirm failed")
        return {
            "result": self._confirm_result,
            "message": self._confirm_message,
            "next_callback": f"eng:det:{engagement_id}",
            "engagement_id": engagement_id,
        }

    async def wizard_retry_engagement(self, engagement_id):
        call = {"engagement_id": engagement_id}
        self.wizard_retry_calls.append(call)
        if self._raise_retry:
            from bot.api_client import BotApiError
            raise BotApiError("Retry failed")
        return {
            "result": "reset",
            "message": "Engagement reset. Start fresh.",
            "next_callback": "eng:wz:start",
            "engagement_id": engagement_id,
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
        self.community_join_calls.append(
            {
                "community_id": community_id,
                "account_id": telegram_account_id,
                "requested_by": requested_by,
            }
        )
        if self._raise_start_join:
            from bot.api_client import BotApiError

            raise BotApiError("Join queue unavailable")
        self.actions.insert(
            0,
            {
                "id": "wizard-join-action",
                "community_id": community_id,
                "candidate_id": None,
                "telegram_account_id": telegram_account_id,
                "action_type": "join",
                "status": self._join_action_status,
                "outbound_text": None,
                "created_at": "2026-04-28T20:29:00Z",
                "sent_at": "2026-04-28T20:30:00Z" if self._join_action_status == "sent" else None,
                "error_message": self._join_action_error,
            },
        )
        return {"job": {"id": "join-job-1", "status": "queued"}}

    async def start_engagement_detection(self, community_id, *, window_minutes=60, requested_by=None):
        self.start_detection_calls.append({"community_id": community_id})
        return {"id": "detect-job-1", "status": "queued"}


def _wiz_context(client=None):
    ctx = _context(client or _FakeWizardApiClient())
    return ctx


# ---------------------------------------------------------------------------
# Helper to run through Step 1 (text entry) to Step 2
# ---------------------------------------------------------------------------


async def _wizard_through_step2(context, *, handle="@test_community"):
    """Start wizard and submit a handle to reach Step 2. Returns client."""
    await callback_query(_callback_update("eng:wz:start"), context)
    await telegram_entity_text(_message_update(handle), context)


# ---------------------------------------------------------------------------
# Tests: Step 1 — target entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_start_shows_community_prompt() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    update = _callback_update("eng:wz:start")

    await callback_query(update, context)

    text = update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 5" in text
    assert "t.me/" in text or "@handle" in text or "@" in text

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"
    assert pending.flow_step == "target"


@pytest.mark.asyncio
async def test_wizard_start_from_wizard_callback() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    update = _callback_update("eng:wz:start")

    await callback_query(update, context)

    text = update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 5" in text
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"


@pytest.mark.asyncio
async def test_wizard_step1_valid_handle_creates_engagement_and_advances_to_step2() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("@founders_hub")

    await telegram_entity_text(text_update, context)

    # Should have called create_engagement_target
    assert client.create_target_calls[-1]["target_ref"] == "@founders_hub"
    # Should have called create_engagement
    assert client.create_engagement_calls
    assert client.create_engagement_calls[-1]["target_id"] == "target-new"

    text = text_update.message.replies[0]["text"]
    assert "Step 2 of 5" in text

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending.flow_step == "topics"
    assert (pending.flow_state or {}).get("engagement_id") == _ENG_NEW_ID


@pytest.mark.asyncio
async def test_wizard_step1_pending_target_waits_for_resolution_before_creating_engagement() -> None:
    client = _FakeWizardApiClient()
    client._target_status = "pending"
    client._resolved_target_status = "resolved"
    context = _wiz_context(client)

    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("https://t.me/hse_live")

    await telegram_entity_text(text_update, context)

    assert client.resolve_target_calls[-1]["target_id"] == "target-new"
    assert client.get_target_calls[-1] == "target-new"
    assert client.create_engagement_calls[-1]["target_id"] == "target-new"

    text = text_update.message.replies[0]["text"]
    assert "Step 2 of 5" in text


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

    await callback_query(_callback_update("eng:wz:start"), context)
    text_update = _message_update("@already_approved")

    await telegram_entity_text(text_update, context)

    text = text_update.message.replies[0]["text"]
    assert "already active" in text or "approved" in text.lower()
    # No engagement should be created
    assert not client.create_engagement_calls
    # Pending edit should be cleared
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None


# ---------------------------------------------------------------------------
# Tests: Step 2 — topic picker (single-select)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_step2_topic_select() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)

    toggle_update = _callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}")
    await callback_query(toggle_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("topic_id") == _TOPIC_1_ID
    assert client.patch_engagement_calls
    assert client.patch_engagement_calls[-1]["topic_id"] == _TOPIC_1_ID


@pytest.mark.asyncio
async def test_wizard_step2_topic_deselect() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)

    # Select topic-1
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    # Deselect topic-1 (same pick = toggle off)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("topic_id") is None


@pytest.mark.asyncio
async def test_wizard_step2_selecting_different_topic_replaces() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)

    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_2}:{_C_ENG_NEW}"), context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("topic_id") == _TOPIC_2_ID


@pytest.mark.asyncio
async def test_wizard_step2_continue_advances_to_step3() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": _ACCT_1_ID, "phone": "+1*****11", "status": "available", "account_pool": "engagement"},
            {"id": _ACCT_2_ID, "phone": "+1*****22", "status": "available", "account_pool": "engagement"},
        ],
    }
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    step3_update = _callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}")

    await callback_query(step3_update, context)

    text = step3_update.callback_query.message.replies[0]["text"]
    assert "Step 3 of 5" in text


# ---------------------------------------------------------------------------
# Tests: Step 3 — account picker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_step3_auto_picks_single_account() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 1},
        "items": [{"id": _ACCT_SOLO_ID, "phone": "+1*****99", "status": "available", "account_pool": "engagement"}],
    }
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert (pending.flow_state or {}).get("account_id") == _ACCT_SOLO_ID
    assert (pending.flow_state or {}).get("community_id") == "community-new"
    assert client.put_engagement_settings_calls
    account_calls = [c for c in client.put_engagement_settings_calls if c.get("assigned_account_id") == _ACCT_SOLO_ID]
    assert account_calls
    assert client.community_join_calls == [
        {
            "community_id": "community-new",
            "account_id": _ACCT_SOLO_ID,
            "requested_by": "telegram:123:@operator",
        }
    ]
    assert (pending.flow_state or {}).get("join_status") == "connecting"
    assert "connecting now" in str((pending.flow_state or {}).get("join_message") or "")


@pytest.mark.asyncio
async def test_wizard_step3_manual_account_pick() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": _ACCT_1_ID, "phone": "+1*****11", "status": "available", "account_pool": "engagement"},
            {"id": _ACCT_2_ID, "phone": "+1*****22", "status": "available", "account_pool": "engagement"},
        ],
    }
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)

    pick_update = _callback_update(f"eng:wz:ap:{_C_ACCT_2}:{_C_ENG_NEW}")
    await callback_query(pick_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("account_id") == _ACCT_2_ID
    account_calls = [c for c in client.put_engagement_settings_calls if c.get("assigned_account_id") == _ACCT_2_ID]
    assert account_calls
    assert client.community_join_calls == [
        {
            "community_id": "community-new",
            "account_id": _ACCT_2_ID,
            "requested_by": "telegram:123:@operator",
        }
    ]
    assert "connecting now" in pick_update.callback_query.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_wizard_step3_joined_account_shows_ready_note() -> None:
    client = _FakeWizardApiClient()
    client._join_action_status = "sent"
    client.accounts = {
        "counts": {"available": 1},
        "items": [{"id": _ACCT_SOLO_ID, "phone": "+1*****99", "status": "available", "account_pool": "engagement"}],
    }
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    ready_update = _callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}")

    await callback_query(ready_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("join_status") == "joined"
    assert "joined and ready" in ready_update.callback_query.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_wizard_step3_failed_join_stays_on_account_picker() -> None:
    client = _FakeWizardApiClient()
    client._join_action_status = "failed"
    client._join_action_error = "Invite required"
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": _ACCT_1_ID, "phone": "+1*****11", "status": "available", "account_pool": "engagement"},
            {"id": _ACCT_2_ID, "phone": "+1*****22", "status": "available", "account_pool": "engagement"},
        ],
    }
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)

    failed_update = _callback_update(f"eng:wz:ap:{_C_ACCT_2}:{_C_ENG_NEW}")
    await callback_query(failed_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.flow_step == "account"
    assert (pending.flow_state or {}).get("join_status") == "failed"
    text = failed_update.callback_query.message.replies[0]["text"]
    assert "Step 3 of 5" in text
    assert "Invite required" in text


# ---------------------------------------------------------------------------
# Tests: Step 4 — mode picker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_step4_level_watching_maps_to_observe() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    level_update = _callback_update(f"eng:wz:lv:watching:{_ENG_NEW_ID}")

    await callback_query(level_update, context)

    mode_calls = [c for c in client.put_engagement_settings_calls if c.get("mode") is not None]
    assert mode_calls
    assert mode_calls[-1]["mode"] == "observe"


@pytest.mark.asyncio
async def test_wizard_step4_level_suggesting_maps_to_suggest() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    level_update = _callback_update(f"eng:wz:lv:suggesting:{_ENG_NEW_ID}")

    await callback_query(level_update, context)

    mode_calls = [c for c in client.put_engagement_settings_calls if c.get("mode") is not None]
    assert mode_calls
    assert mode_calls[-1]["mode"] == "suggest"


@pytest.mark.asyncio
async def test_wizard_step4_level_sending_maps_to_require_approval() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    level_update = _callback_update(f"eng:wz:lv:sending:{_ENG_NEW_ID}")

    await callback_query(level_update, context)

    mode_calls = [c for c in client.put_engagement_settings_calls if c.get("mode") is not None]
    assert mode_calls
    assert mode_calls[-1]["mode"] == "require_approval"


# ---------------------------------------------------------------------------
# Tests: Step 5 — confirm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_step5_confirm_success() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:suggesting:{_ENG_NEW_ID}"), context)

    confirm_update = _callback_update(f"eng:wz:confirm:{_ENG_NEW_ID}")
    await callback_query(confirm_update, context)

    assert client.wizard_confirm_calls
    assert client.wizard_confirm_calls[-1]["engagement_id"] == _ENG_NEW_ID
    # Pending edit should be cleared
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None
    edit_text = confirm_update.callback_query.edits[0]["text"]
    assert "Started" in edit_text or "✓" in edit_text or "Engagement started" in edit_text


@pytest.mark.asyncio
async def test_wizard_step5_confirm_validation_failed() -> None:
    client = _FakeWizardApiClient()
    client._confirm_result = "validation_failed"
    client._confirm_message = "Topic is required."
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)
    await callback_query(_callback_update(f"eng:wz:step:3:{_ENG_NEW_ID}"), context)
    await callback_query(_callback_update(f"eng:wz:lv:suggesting:{_ENG_NEW_ID}"), context)

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
    await callback_query(_callback_update(f"eng:wz:lv:suggesting:{_ENG_NEW_ID}"), context)

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
    await callback_query(_callback_update(f"eng:wz:lv:suggesting:{_ENG_NEW_ID}"), context)

    confirm_update = _callback_update(f"eng:wz:confirm:{_ENG_NEW_ID}")
    await callback_query(confirm_update, context)

    edit_text = confirm_update.callback_query.edits[0]["text"]
    assert "Retry" in edit_text or "Couldn't" in edit_text
    edit_markup = confirm_update.callback_query.edits[0]["reply_markup"]
    assert edit_markup is not None


# ---------------------------------------------------------------------------
# Tests: Retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_retry_calls_endpoint_and_resets_to_step1() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    await callback_query(_callback_update(f"eng:wz:tp:{_C_TOPIC_1}:{_C_ENG_NEW}"), context)

    retry_update = _callback_update(f"eng:wz:retry:{_ENG_NEW_ID}")
    await callback_query(retry_update, context)

    assert client.wizard_retry_calls
    assert client.wizard_retry_calls[-1]["engagement_id"] == _ENG_NEW_ID

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "wizard"
    assert pending.flow_step == "target"
    assert (pending.flow_state or {}).get("engagement_id") is None


# ---------------------------------------------------------------------------
# Tests: Cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_cancel_shows_confirmation_prompt() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)

    cancel_update = _callback_update(f"eng:wz:cancel:{_ENG_NEW_ID}")
    await callback_query(cancel_update, context)

    edit_text = cancel_update.callback_query.edits[0]["text"]
    assert "cancel" in edit_text.lower() or "Cancel" in edit_text
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is not None


@pytest.mark.asyncio
async def test_wizard_cancel_yes_clears_pending() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    await _wizard_through_step2(context)
    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is not None

    cancel_yes_update = _callback_update(f"eng:wz:cancel_yes:{_ENG_NEW_ID}")
    await callback_query(cancel_yes_update, context)

    assert context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123) is None


# ---------------------------------------------------------------------------
# Tests: Resume wizard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_resume_shows_appropriate_step() -> None:
    client = _FakeWizardApiClient()
    client.accounts = {
        "counts": {"available": 2},
        "items": [
            {"id": _ACCT_A_ID, "phone": "+1*****11", "status": "available", "account_pool": "engagement"},
            {"id": _ACCT_B_ID, "phone": "+1*****22", "status": "available", "account_pool": "engagement"},
        ],
    }
    context = _wiz_context(client)
    store = context.application.bot_data.setdefault(CONFIG_EDIT_STORE_KEY, PendingEditStore())
    from bot.config_editing import editable_field

    editable = editable_field("wizard", "state")
    store.start(
        operator_id=123,
        field=editable,
        object_id=_ENG_EXISTING_ID,
        flow_step="account",
        flow_state={
            "engagement_id": _ENG_EXISTING_ID,
            "target_id": "target-existing",
            "target_ref": "@existing",
            "topic_id": _TOPIC_1_ID,
            "account_id": None,
            "mode": None,
            "return_callback": None,
        },
    )
    resume_update = _callback_update("eng:wz:start")

    await callback_query(resume_update, context)

    text = resume_update.callback_query.message.replies[0]["text"]
    assert "Step 3 of 5" in text


@pytest.mark.asyncio
async def test_wizard_resume_at_mode_step() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)
    store = context.application.bot_data.setdefault(CONFIG_EDIT_STORE_KEY, PendingEditStore())
    from bot.config_editing import editable_field

    editable = editable_field("wizard", "state")
    store.start(
        operator_id=123,
        field=editable,
        object_id=_ENG_XYZ_ID,
        flow_step="mode",
        flow_state={
            "engagement_id": _ENG_XYZ_ID,
            "target_id": "target-xyz",
            "target_ref": "@xyz",
            "topic_id": _TOPIC_1_ID,
            "account_id": _ACCT_1_ID,
            "mode": None,
            "return_callback": None,
        },
    )
    resume_update = _callback_update("eng:wz:start")

    await callback_query(resume_update, context)

    text = resume_update.callback_query.message.replies[0]["text"]
    assert "Step 4 of 5" in text


# ---------------------------------------------------------------------------
# Tests: Edit reentry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wizard_edit_reentry_topic_opens_step2() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    store = context.application.bot_data.setdefault(CONFIG_EDIT_STORE_KEY, PendingEditStore())
    from bot.config_editing import editable_field
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
            "mode": "suggesting",
            "return_callback": None,
        },
    )

    edit_update = _callback_update(f"eng:wz:edit:{_ENG_EDIT_ID}:topic")
    await callback_query(edit_update, context)

    text = edit_update.callback_query.message.replies[0]["text"]
    assert "Step 2 of 5" in text

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("return_callback") is not None


@pytest.mark.asyncio
async def test_wizard_edit_reentry_mode_returns_to_review_after_save() -> None:
    client = _FakeWizardApiClient()
    context = _wiz_context(client)

    store = context.application.bot_data.setdefault(CONFIG_EDIT_STORE_KEY, PendingEditStore())
    from bot.config_editing import editable_field
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
            "mode": "suggesting",
            "return_callback": None,
        },
    )

    await callback_query(_callback_update(f"eng:wz:edit:{_ENG_EDIT_ID}:mode"), context)

    level_update = _callback_update(f"eng:wz:lv:watching:{_ENG_EDIT_ID}")
    await callback_query(level_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert (pending.flow_state or {}).get("mode") == "watching"
    assert (pending.flow_state or {}).get("return_callback") is None

    mode_calls = [c for c in client.put_engagement_settings_calls if c.get("mode") == "observe"]
    assert mode_calls
