from __future__ import annotations

import pytest

from tests.test_bot_engagement_handlers import (
    _FakeApiClient,
    _callback_data_values,
    _callback_update,
    _context,
    _message_update,
    callback_query,
    engagement_candidate_command,
)


@pytest.mark.asyncio
async def test_engagement_candidate_command_opens_detail_with_revision_and_edit_controls() -> None:
    client = _FakeApiClient()
    update = _message_update()

    await engagement_candidate_command(update, _context(client, "candidate-review"))

    assert client.get_candidate_calls == ["candidate-review"]
    text = update.message.replies[0]["text"]
    assert "Candidate ID: candidate-review" in text
    assert "Source: Discussing CRM tools." in text
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:cand:edit:candidate-review" in callbacks
    assert "eng:cand:rev:candidate-review" in callbacks
    assert "eng:cand:send:candidate-review" not in callbacks


@pytest.mark.asyncio
async def test_engagement_candidate_detail_hides_learning_shortcuts_until_final_reply_exists() -> None:
    client = _FakeApiClient()
    client.candidates_by_status["needs_review"]["items"][0]["topic_id"] = "topic-1"
    update = _message_update()

    await engagement_candidate_command(update, _context(client, "candidate-review"))

    text = update.message.replies[0]["text"]
    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:cand:savegood:candidate-review" not in callbacks
    assert "eng:cand:style:candidate-review" not in callbacks
    assert "Learning shortcuts unlock after you edit Final reply" in text


@pytest.mark.asyncio
async def test_engagement_candidate_detail_shows_learning_shortcuts_when_final_reply_exists() -> None:
    client = _FakeApiClient()
    client.candidates_by_status["needs_review"]["items"][0]["topic_id"] = "topic-1"
    client.candidates_by_status["needs_review"]["items"][0]["final_reply"] = (
        "Compare ownership, integrations, and export access before you switch."
    )
    update = _message_update()

    await engagement_candidate_command(update, _context(client, "candidate-review"))

    callbacks = _callback_data_values(update.message.replies[0]["reply_markup"])
    assert "eng:cand:savegood:candidate-review" in callbacks
    assert "eng:cand:style:candidate-review" in callbacks


@pytest.mark.asyncio
async def test_candidate_save_good_example_callback_adds_topic_example_and_refreshes_card() -> None:
    client = _FakeApiClient()
    client.candidates_by_status["needs_review"]["items"][0]["topic_id"] = "topic-1"
    client.candidates_by_status["needs_review"]["items"][0]["final_reply"] = (
        "Compare ownership, integrations, and export access before you switch."
    )
    update = _callback_update("eng:cand:savegood:candidate-review")

    await callback_query(update, _context(client))

    assert client.add_topic_example_calls[-1] == {
        "topic_id": "topic-1",
        "example_type": "good",
        "example": "Compare ownership, integrations, and export access before you switch.",
    }
    text = update.callback_query.edits[0]["text"]
    assert "Saved the current reply as a good example." in text
    assert "Topic good examples:" in text


@pytest.mark.asyncio
async def test_candidate_style_rule_callback_prompts_for_scope_then_creates_topic_rule() -> None:
    client = _FakeApiClient()
    client.candidates_by_status["needs_review"]["items"][0]["topic_id"] = "topic-1"
    client.candidates_by_status["needs_review"]["items"][0]["final_reply"] = (
        "Compare ownership, integrations, and export access before you switch."
    )
    scope_update = _callback_update("eng:cand:style:candidate-review")

    await callback_query(scope_update, _context(client))

    scope_callbacks = _callback_data_values(scope_update.callback_query.edits[0]["reply_markup"])
    assert "eng:cand:style:candidate-review:global" in scope_callbacks
    assert "eng:cand:style:candidate-review:community" in scope_callbacks
    assert "eng:cand:style:candidate-review:topic" in scope_callbacks

    create_update = _callback_update("eng:cand:style:candidate-review:topic")
    await callback_query(create_update, _context(client))

    assert client.create_style_rule_calls[-1] == {
        "scope_type": "topic",
        "scope_id": "topic-1",
        "name": "Reply edit reference: Open CRM",
        "priority": 160,
        "rule_text": (
            "Use this approved reply as a style reference for tone, structure, and level of detail. "
            "Do not copy it word for word.\n\n"
            "Reference reply:\nCompare ownership, integrations, and export access before you switch."
        ),
        "created_by": "telegram:123:@operator",
    }
    text = create_update.callback_query.edits[0]["text"]
    assert "Created a topic style rule from this reply edit." in text
    assert "Rule ID: rule-created" in text


@pytest.mark.asyncio
async def test_candidate_learning_shortcuts_require_edited_final_reply() -> None:
    client = _FakeApiClient()
    client.candidates_by_status["needs_review"]["items"][0]["topic_id"] = "topic-1"

    save_update = _callback_update("eng:cand:savegood:candidate-review")
    await callback_query(save_update, _context(client))

    assert client.add_topic_example_calls == []
    assert save_update.callback_query.message.replies[0]["text"] == (
        "Edit the final reply first, then save that deliberate edit as guidance."
    )

    style_update = _callback_update("eng:cand:style:candidate-review")
    await callback_query(style_update, _context(client))

    assert client.create_style_rule_calls == []
    assert style_update.callback_query.message.replies[0]["text"] == (
        "Edit the final reply first, then save that deliberate edit as guidance."
    )
