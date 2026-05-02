from __future__ import annotations

from typing import Any

from .engagement_handlers import (
    _create_candidate_style_rule,
    _expire_engagement_candidate,
    _prompt_candidate_style_rule_scope,
    _remove_topic_example,
    _retry_engagement_candidate,
    _review_engagement_candidate,
    _save_candidate_reply_as_good_example,
    _send_engagement_candidate_detail,
    _send_engagement_candidate_revisions,
    _send_engagement_reply,
    _send_engagement_topic,
    _send_engagement_topics,
    _toggle_engagement_topic,
)
from .runtime import (
    _callback_reply,
    _handle_topic_brief_callback,
    _parse_offset,
    _preview_topic_create_sample,
    _start_config_edit,
)
from .ui import (
    ACTION_ENGAGEMENT_APPROVE,
    ACTION_ENGAGEMENT_CANDIDATE_EDIT,
    ACTION_ENGAGEMENT_CANDIDATE_EXPIRE,
    ACTION_ENGAGEMENT_CANDIDATE_OPEN,
    ACTION_ENGAGEMENT_CANDIDATE_RETRY,
    ACTION_ENGAGEMENT_CANDIDATE_REVISIONS,
    ACTION_ENGAGEMENT_CANDIDATE_SAVE_GOOD,
    ACTION_ENGAGEMENT_CANDIDATE_STYLE,
    ACTION_ENGAGEMENT_REJECT,
    ACTION_ENGAGEMENT_SEND,
    ACTION_ENGAGEMENT_TOPIC_BRIEF,
    ACTION_ENGAGEMENT_TOPIC_EDIT,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_ENGAGEMENT_TOPIC_OPEN,
    ACTION_ENGAGEMENT_TOPIC_PREVIEW,
    ACTION_ENGAGEMENT_TOPIC_TOGGLE,
)
from .ui_common import expand_topic_edit_field


async def _handle_engagement_topic_candidate_callback(
    update: Any,
    context: Any,
    action: str,
    parts: list[str],
) -> bool:
    if action == ACTION_ENGAGEMENT_TOPIC_LIST and parts:
        await _send_engagement_topics(update, context, offset=_parse_offset(parts[0]))
        return True
    if action == ACTION_ENGAGEMENT_TOPIC_BRIEF:
        return await _handle_topic_brief_callback(update, context, parts)
    if action == ACTION_ENGAGEMENT_TOPIC_OPEN and len(parts) == 1:
        await _send_engagement_topic(update, context, parts[0])
        return True
    if action == ACTION_ENGAGEMENT_TOPIC_PREVIEW:
        preview_source = "real" if parts and parts[0] == "real" else "sample"
        await _preview_topic_create_sample(update, context, preview_source=preview_source)
        return True
    if action == ACTION_ENGAGEMENT_TOPIC_EDIT and len(parts) == 2:
        field = expand_topic_edit_field(parts[1])
        if field not in {"stance_guidance", "trigger_keywords", "negative_keywords"}:
            await _callback_reply(update, "That topic field is not editable from this button.")
            return True
        await _start_config_edit(
            update,
            context,
            entity="topic",
            object_id=parts[0],
            field=field,
        )
        return True
    if action == ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD and len(parts) == 2:
        example_type = "good" if parts[1] == "g" else "bad" if parts[1] == "b" else None
        if example_type is None:
            await _callback_reply(update, "That topic example type is not available.")
            return True
        await _start_config_edit(
            update,
            context,
            entity="topic_example",
            object_id=parts[0],
            field=example_type,
        )
        return True
    if action == ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE and len(parts) == 3:
        example_type = "good" if parts[1] == "g" else "bad"
        await _remove_topic_example(
            update,
            context,
            parts[0],
            example_type=example_type,
            index=_parse_offset(parts[2]),
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_TOPIC_TOGGLE and len(parts) == 2:
        await _toggle_engagement_topic(
            update,
            context,
            parts[0],
            active=parts[1] == "1",
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_OPEN and len(parts) == 1:
        await _send_engagement_candidate_detail(update, context, parts[0])
        return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_EDIT and len(parts) == 1:
        await _start_config_edit(
            update,
            context,
            entity="candidate",
            object_id=parts[0],
            field="final_reply",
        )
        return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_SAVE_GOOD and len(parts) == 1:
        await _save_candidate_reply_as_good_example(
            update,
            context,
            parts[0],
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_STYLE:
        if len(parts) == 1:
            await _prompt_candidate_style_rule_scope(update, context, parts[0])
            return True
        if len(parts) == 2:
            await _create_candidate_style_rule(
                update,
                context,
                parts[0],
                scope_type=parts[1],
            )
            return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_REVISIONS and len(parts) == 1:
        await _send_engagement_candidate_revisions(update, context, parts[0])
        return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_EXPIRE and len(parts) == 1:
        await _expire_engagement_candidate(
            update,
            context,
            parts[0],
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_CANDIDATE_RETRY and len(parts) == 1:
        await _retry_engagement_candidate(
            update,
            context,
            parts[0],
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_APPROVE and len(parts) == 1:
        await _review_engagement_candidate(
            update,
            context,
            parts[0],
            action="approve",
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_REJECT and len(parts) == 1:
        await _review_engagement_candidate(
            update,
            context,
            parts[0],
            action="reject",
            edit_callback=True,
        )
        return True
    if action == ACTION_ENGAGEMENT_SEND and len(parts) == 1:
        await _send_engagement_reply(update, context, parts[0])
        return True
    return False


__all__ = ["_handle_engagement_topic_candidate_callback"]
