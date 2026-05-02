from __future__ import annotations

import pytest

from bot.api_client import BotApiError
from bot.main import CONFIG_EDIT_STORE_KEY, WIZARD_RETURN_STORE_KEY, callback_query, telegram_entity_text
from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_data_values,
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

    assert "Creating draft brief" in update.callback_query.message.replies[0]["text"]
    assert "Step 1 of 7: Topic name" in update.callback_query.message.replies[0]["text"]
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
    target_update = _message_update("Startup operators asking about outbound outreach")
    guidance_update = _message_update("Be concise and practical.")
    style_update = _message_update("Brief, transparent, no links unless asked.")
    good_update = _message_update("Compare data ownership and export access first.")
    good_continue_update = _callback_update("eng:topic:brief:nav:continue")
    bad_update = _message_update("Buy our tool now.")
    bad_done_update = _callback_update("eng:topic:brief:nav:continue")
    avoid_update = _message_update("No DMs, no fake customer claims.")
    save_update = _callback_update("eng:edit:save")

    await callback_query(start_update, context)
    await telegram_entity_text(name_update, context)
    await telegram_entity_text(target_update, context)
    await telegram_entity_text(guidance_update, context)
    await telegram_entity_text(style_update, context)
    await telegram_entity_text(good_update, context)
    await callback_query(good_continue_update, context)
    await telegram_entity_text(bad_update, context)
    await callback_query(bad_done_update, context)
    await telegram_entity_text(avoid_update, context)
    await callback_query(save_update, context)

    assert "Step 2 of 7: Conversation target" in name_update.message.replies[0]["text"]
    assert "Step 3 of 7: Reply position" in target_update.message.replies[0]["text"]
    assert "Step 4 of 7: Voice and style" in guidance_update.message.replies[0]["text"]
    assert "Step 5 of 7: Good reply examples" in style_update.message.replies[0]["text"]
    assert "Current good examples:" in good_update.message.replies[0]["text"]
    assert "Step 6 of 7: Bad reply examples" in good_continue_update.callback_query.message.replies[0]["text"]
    assert "Current bad examples:" in bad_update.message.replies[0]["text"]
    assert "Step 7 of 7: Avoid rules" in bad_done_update.callback_query.message.replies[0]["text"]
    assert "Review Draft brief" in avoid_update.message.replies[0]["text"]
    assert "Good examples teach shape, not literal templates." in avoid_update.message.replies[0]["text"]
    assert "Bad examples stay in avoid-only guidance" in avoid_update.message.replies[0]["text"]
    assert "Guidance saves to: topic rule: Draft instruction wizard" in avoid_update.message.replies[0]["text"]
    assert "eng:topic:brief:scope:topic" in _callback_data_values(avoid_update.message.replies[0]["reply_markup"])
    assert client.create_topic_calls[-1] == {
        "name": "Founder outreach",
        "description": "Startup operators asking about outbound outreach",
        "stance_guidance": "Be concise and practical.",
        "trigger_keywords": [],
        "negative_keywords": [],
        "example_good_replies": ["Compare data ownership and export access first."],
        "example_bad_replies": ["Buy our tool now."],
        "active": True,
    }
    assert client.create_style_rule_calls[-1] == {
        "scope_type": "topic",
        "scope_id": "topic-created",
        "name": "Draft instruction wizard",
        "priority": 150,
        "rule_text": "Voice:\nBrief, transparent, no links unless asked.\n\nAvoid:\nNo DMs, no fake customer claims.",
        "created_by": "telegram:123:@operator",
    }
    assert "Engagement topic created." in save_update.callback_query.edits[0]["text"]
    assert "Description: Startup operators asking about outbound outreach" in save_update.callback_query.edits[0]["text"]


@pytest.mark.asyncio
async def test_topic_inline_create_flow_allows_skipping_optional_fields() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("-"), context)
    await telegram_entity_text(_message_update("-"), context)
    await telegram_entity_text(_message_update("-"), context)
    final_update = _message_update("-")

    await telegram_entity_text(final_update, context)

    assert "Voice: -" in final_update.message.replies[0]["text"]
    assert "Avoid: -" in final_update.message.replies[0]["text"]


@pytest.mark.asyncio
async def test_topic_inline_create_flow_accumulates_examples_across_add_another_loops() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    first_good_update = _message_update("Compare data ownership and export access first.")

    await telegram_entity_text(first_good_update, context)

    good_callbacks = _callback_data_values(first_good_update.message.replies[0]["reply_markup"])
    assert "eng:topic:brief:nav:add" in good_callbacks
    assert "eng:topic:brief:nav:continue" in good_callbacks

    add_good_update = _callback_update("eng:topic:brief:nav:add")
    await callback_query(add_good_update, context)
    assert "Already added:" in add_good_update.callback_query.message.replies[0]["text"]

    await telegram_entity_text(
        _message_update(
            "Lead with migration tradeoffs first.\n\n"
            "Compare implementation lift before recommending anything."
        ),
        context,
    )
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)

    first_bad_update = _message_update("Buy our tool now.")
    await telegram_entity_text(first_bad_update, context)

    bad_callbacks = _callback_data_values(first_bad_update.message.replies[0]["reply_markup"])
    assert "eng:topic:brief:nav:add" in bad_callbacks
    assert "eng:topic:brief:nav:continue" in bad_callbacks
    assert "Done reviewing examples" in [button.text for row in first_bad_update.message.replies[0]["reply_markup"].inline_keyboard for button in row]

    await callback_query(_callback_update("eng:topic:brief:nav:add"), context)
    second_bad_update = _message_update("Pretend we are a customer.\n\nPush them into DMs.")
    await telegram_entity_text(second_bad_update, context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    final_update = _message_update("-")
    await telegram_entity_text(final_update, context)

    confirm_text = final_update.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.flow_step == "confirm"
    assert (pending.parsed_value or {}).get("example_good_replies") == [
        "Compare data ownership and export access first.",
        "Lead with migration tradeoffs first.",
        "Compare implementation lift before recommending anything.",
    ]
    assert (pending.parsed_value or {}).get("example_bad_replies") == [
        "Buy our tool now.",
        "Pretend we are a customer.",
        "Push them into DMs.",
    ]
    assert "Lead with migration tradeoffs first." in confirm_text
    assert "Push them into DMs." in confirm_text


@pytest.mark.asyncio
async def test_topic_inline_create_flow_can_preview_sample_before_save() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await telegram_entity_text(_message_update("Compare data ownership and export access first."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("Buy our tool now."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    final_update = _message_update("No DMs, no fake customer claims.")

    await telegram_entity_text(final_update, context)

    preview_markup = final_update.message.replies[0]["reply_markup"]
    assert "eng:topic:preview" in _callback_data_values(preview_markup)

    preview_update = _callback_update("eng:topic:preview")
    await callback_query(preview_update, context)

    assert client.preview_prompt_calls == ["prompt-active"]
    assert client.approve_calls == []
    assert client.send_calls == []
    text = preview_update.callback_query.edits[0]["text"]
    assert "Draft brief test" in text
    assert "Preview only. This does not approve or send anything." in text
    assert "Source context: synthetic sample post." in text
    assert "Community: Founder Circle" in text


@pytest.mark.asyncio
async def test_topic_inline_create_flow_can_preview_real_post_before_save() -> None:
    client = _FakeApiClient()
    context = _context(client)
    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {
        123: {
            "engagement_id": "engagement-preview",
            "community_id": "community-1",
            "target_ref": "@founders_hub",
        }
    }

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await telegram_entity_text(_message_update("Compare data ownership and export access first."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("Buy our tool now."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("No DMs, no fake customer claims."), context)

    preview_update = _callback_update("eng:topic:preview:real")
    await callback_query(preview_update, context)

    assert client.list_candidate_calls[0]["community_id"] == "community-1"
    assert client.preview_prompt_calls == ["prompt-active"]
    text = preview_update.callback_query.edits[0]["text"]
    assert "Draft brief test" in text
    assert "Source context: real collected post from Founder Circle." in text
    assert "Preview only. This does not approve or send anything." in text
    assert "Community: Founder Circle" in text


@pytest.mark.asyncio
async def test_topic_inline_create_real_post_preview_requires_collected_candidate_context() -> None:
    client = _FakeApiClient()
    client.candidates_by_status = {
        "needs_review": {"items": [], "total": 0},
        "approved": {"items": [], "total": 0},
    }
    context = _context(client)
    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {
        123: {
            "engagement_id": "engagement-preview",
            "community_id": "community-1",
            "target_ref": "@founders_hub",
        }
    }

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await telegram_entity_text(_message_update("Compare data ownership and export access first."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("Buy our tool now."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("No DMs, no fake customer claims."), context)

    preview_update = _callback_update("eng:topic:preview:real")
    await callback_query(preview_update, context)

    assert client.preview_prompt_calls == []
    text = preview_update.callback_query.edits[0]["text"]
    assert "Draft brief test unavailable." in text
    assert "No collected post is available for a real-post preview yet." in text


@pytest.mark.asyncio
async def test_topic_brief_step_markup_exposes_back_skip_save_later_and_cancel() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    guidance_update = _message_update("Be concise and practical.")

    await telegram_entity_text(guidance_update, context)

    callbacks = _callback_data_values(guidance_update.message.replies[0]["reply_markup"])
    assert "eng:topic:brief:nav:back" in callbacks
    assert "eng:topic:brief:nav:skip" in callbacks
    assert "eng:topic:brief:nav:later" in callbacks
    assert "eng:edit:cancel" in callbacks


@pytest.mark.asyncio
async def test_topic_brief_back_callback_returns_to_previous_step() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    back_update = _callback_update("eng:topic:brief:nav:back")

    await callback_query(back_update, context)

    assert "Step 3 of 7: Reply position" in back_update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.flow_step == "stance_guidance"


@pytest.mark.asyncio
async def test_topic_brief_skip_callback_advances_optional_step() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    skip_update = _callback_update("eng:topic:brief:nav:skip")

    await callback_query(skip_update, context)

    assert "Step 5 of 7: Good reply examples" in skip_update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.flow_step == "example_good_replies"
    assert pending.flow_state["style_guidance"] == ""


@pytest.mark.asyncio
async def test_topic_brief_save_later_resumes_existing_draft() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    save_later_update = _callback_update("eng:topic:brief:nav:later")

    await callback_query(save_later_update, context)

    assert "Saved this draft brief for later." in save_later_update.callback_query.message.replies[0]["text"]

    resume_update = _callback_update("eng:topic:create")
    await callback_query(resume_update, context)

    assert "Step 2 of 7: Conversation target" in resume_update.callback_query.message.replies[0]["text"]
    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.flow_step == "description"


@pytest.mark.asyncio
async def test_topic_brief_preview_markup_keeps_back_and_save_later_controls() -> None:
    client = _FakeApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    final_update = _callback_update("eng:topic:brief:nav:skip")

    await callback_query(final_update, context)

    callbacks = _callback_data_values(final_update.callback_query.message.replies[0]["reply_markup"])
    assert "eng:edit:save" in callbacks
    assert "eng:topic:preview" in callbacks
    assert "eng:topic:preview:real" in callbacks
    assert "eng:topic:brief:nav:back" in callbacks
    assert "eng:topic:brief:nav:later" in callbacks
    assert "eng:edit:cancel" in callbacks


@pytest.mark.asyncio
async def test_topic_brief_confirmation_offers_community_and_existing_rule_targets_with_wizard_context() -> None:
    client = _FakeApiClient()
    context = _context(client)
    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {
        123: {
            "engagement_id": "engagement-preview",
            "community_id": "community-1",
            "target_ref": "@founders_hub",
        }
    }

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    final_update = _callback_update("eng:topic:brief:nav:skip")

    await callback_query(final_update, context)

    callbacks = _callback_data_values(final_update.callback_query.message.replies[0]["reply_markup"])
    assert "eng:topic:brief:scope:topic" in callbacks
    assert "eng:topic:brief:scope:community" in callbacks
    assert "eng:topic:brief:attach:rule-2" in callbacks


@pytest.mark.asyncio
async def test_topic_brief_can_save_guidance_to_community_scope() -> None:
    client = _FakeApiClient()
    context = _context(client)
    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {
        123: {
            "engagement_id": "engagement-preview",
            "community_id": "community-1",
            "target_ref": "@founders_hub",
        }
    }

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await telegram_entity_text(_message_update("No DMs, no fake customer claims."), context)

    scope_update = _callback_update("eng:topic:brief:scope:community")
    await callback_query(scope_update, context)
    assert "Guidance saves to: community rule: Draft instruction wizard" in scope_update.callback_query.message.replies[0]["text"]

    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {}
    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    assert client.create_style_rule_calls[-1] == {
        "scope_type": "community",
        "scope_id": "community-1",
        "name": "Draft instruction wizard",
        "priority": 150,
        "rule_text": "Voice:\nBrief, transparent, no links unless asked.\n\nAvoid:\nNo DMs, no fake customer claims.",
        "created_by": "telegram:123:@operator",
    }


@pytest.mark.asyncio
async def test_topic_brief_can_attach_guidance_to_existing_community_rule() -> None:
    client = _FakeApiClient()
    context = _context(client)
    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {
        123: {
            "engagement_id": "engagement-preview",
            "community_id": "community-1",
            "target_ref": "@founders_hub",
        }
    }

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await callback_query(_callback_update("eng:topic:brief:nav:skip"), context)
    await telegram_entity_text(_message_update("No DMs, no fake customer claims."), context)

    attach_update = _callback_update("eng:topic:brief:attach:rule-2")
    await callback_query(attach_update, context)
    assert "Guidance saves to: existing community rule: Mention tradeoffs" in attach_update.callback_query.message.replies[0]["text"]

    context.application.bot_data[WIZARD_RETURN_STORE_KEY] = {}
    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    assert client.update_style_rule_calls[-1] == {
        "rule_id": "rule-2",
        "updates": {
            "rule_text": "Voice:\nBrief, transparent, no links unless asked.\n\nAvoid:\nNo DMs, no fake customer claims.",
            "updated_by": "telegram:123:@operator",
        },
    }


class _PreviewFailureApiClient(_FakeApiClient):
    async def preview_engagement_prompt_profile(
        self,
        profile_id: str,
        *,
        variables: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.preview_prompt_calls.append(profile_id)
        raise BotApiError("Preview rejected")


@pytest.mark.asyncio
async def test_topic_brief_preview_failure_keeps_confirmation_controls() -> None:
    client = _PreviewFailureApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await telegram_entity_text(_message_update("Compare data ownership and export access first."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("Buy our tool now."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("No DMs, no fake customer claims."), context)

    preview_update = _callback_update("eng:topic:preview")
    await callback_query(preview_update, context)

    text = preview_update.callback_query.edits[0]["text"]
    assert "Draft brief test unavailable." in text
    assert "API error: Preview rejected" in text
    callbacks = _callback_data_values(preview_update.callback_query.edits[0]["reply_markup"])
    assert "eng:edit:save" in callbacks
    assert "eng:topic:preview" in callbacks
    assert "eng:topic:preview:real" in callbacks
    assert "eng:topic:brief:nav:back" in callbacks


class _StyleRuleFailureApiClient(_FakeApiClient):
    async def create_engagement_style_rule(
        self,
        operator_user_id: int | None = None,
        **payload: object,
    ) -> dict[str, object]:
        self.create_style_rule_calls.append(dict(payload))
        raise BotApiError("Style guidance rejected")


@pytest.mark.asyncio
async def test_topic_brief_partial_save_rebinds_pending_topic_after_style_rule_failure() -> None:
    client = _StyleRuleFailureApiClient()
    context = _context(client)

    await callback_query(_callback_update("eng:topic:create"), context)
    await telegram_entity_text(_message_update("Founder outreach"), context)
    await telegram_entity_text(_message_update("Startup operators asking about outbound outreach"), context)
    await telegram_entity_text(_message_update("Be concise and practical."), context)
    await telegram_entity_text(_message_update("Brief, transparent, no links unless asked."), context)
    await telegram_entity_text(_message_update("Compare data ownership and export access first."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("Buy our tool now."), context)
    await callback_query(_callback_update("eng:topic:brief:nav:continue"), context)
    await telegram_entity_text(_message_update("No DMs, no fake customer claims."), context)

    save_update = _callback_update("eng:edit:save")
    await callback_query(save_update, context)

    pending = context.application.bot_data[CONFIG_EDIT_STORE_KEY].get(123)
    assert pending is not None
    assert pending.entity == "topic_create"
    assert pending.object_id == "topic-created"
    assert pending.flow_step == "confirm"
    assert client.create_topic_calls[-1]["name"] == "Founder outreach"
    text = save_update.callback_query.edits[0]["text"]
    assert "Draft brief saved the topic details" in text
    assert "API error: Style guidance rejected" in text
    assert "Topic ID: topic-created" in text


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
