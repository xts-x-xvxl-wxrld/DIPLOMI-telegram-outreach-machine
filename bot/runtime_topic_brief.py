# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *
from .runtime_context import *
from .runtime_markup import *
from .runtime_io import *
from .runtime_access import *
from .runtime_parsing import *
from .runtime_topic_brief_style import (
    _find_topic_brief_style_rule,
    _split_topic_brief_style_rule,
    _topic_brief_selection_state,
    _upsert_topic_brief_style_rule,
)
from .runtime_topic_brief_flow import (
    _TOPIC_CREATE_STEP_ORDER,
    _handle_topic_brief_existing_rule_choice,
    _handle_topic_brief_scope_choice,
    _merge_topic_examples,
    _preview_topic_create_sample,
    _show_topic_create_pending,
    _split_topic_examples,
    _topic_create_add_another_step,
    _topic_create_confirmation_markup,
    _topic_create_continue_step,
    _topic_create_finish_questions,
    _topic_create_normalized_step,
    _topic_create_saved_for_later_message,
    _topic_create_skip_step,
    _topic_create_step_back,
)


async def _start_topic_create(
    update: Any,
    context: Any,
    *,
    topic_id: str | None = None,
) -> None:
    await _start_topic_create_with_reply(
        update,
        context,
        reply_func=_callback_reply,
        topic_id=topic_id,
    )


async def _start_topic_create_message(
    update: Any,
    context: Any,
    *,
    topic_id: str | None = None,
) -> None:
    await _start_topic_create_with_reply(
        update,
        context,
        reply_func=_reply,
        topic_id=topic_id,
    )


async def _start_topic_create_with_reply(
    update: Any,
    context: Any,
    *,
    reply_func: Any,
    topic_id: str | None = None,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await reply_func(update, "Telegram did not include a user ID on this update.")
        return
    editable = editable_field("topic_create", "payload")
    if editable is None:
        await reply_func(update, "Topic creation is not available from the bot right now.")
        return
    if editable.admin_only and not await _require_engagement_admin(update, context):
        return
    requested_object_id = topic_id or "new"
    existing = _config_edit_store(context).get(operator_id)
    if existing is not None and existing.entity == "topic_create":
        notice = None
        if existing.object_id != requested_object_id:
            notice = "Finish or cancel the current draft brief before starting another one."
        await _show_topic_create_pending(
            update,
            existing,
            context=context,
            reply_func=reply_func,
            notice=notice,
        )
        return
    flow_state: dict[str, Any] = {}
    object_id = requested_object_id
    wizard_return_store = context.application.bot_data.get(WIZARD_RETURN_STORE_KEY) or {}
    wizard_state = wizard_return_store.get(operator_id)
    if isinstance(wizard_state, dict):
        community_id = str(wizard_state.get("community_id") or "").strip()
        if community_id:
            flow_state["community_id"] = community_id
    if topic_id:
        client = _api_client(context)
        try:
            topic = await client.get_engagement_topic(topic_id)
            style_rule = await _find_topic_brief_style_rule(client, topic_id)
        except BotApiError as exc:
            await reply_func(update, f"Couldn't load topic brief: {exc.message}")
            return
        flow_state.update(_prefill_topic_create_state(topic, style_rule))
        object_id = topic_id
    pending = _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id=object_id,
        flow_step=_TOPIC_CREATE_STEP_ORDER[0],
        flow_state=flow_state,
    )
    await _show_topic_create_pending(update, pending, context=context, reply_func=reply_func)


def _prefill_topic_create_state(
    topic: dict[str, Any],
    style_rule: dict[str, Any] | None,
) -> dict[str, Any]:
    style_guidance, avoid_rules = _split_topic_brief_style_rule(
        str((style_rule or {}).get("rule_text") or "")
    )
    return {
        "name": str(topic.get("name") or ""),
        "description": str(topic.get("description") or ""),
        "stance_guidance": str(topic.get("stance_guidance") or ""),
        "style_guidance": style_guidance,
        "example_good_replies": list(topic.get("example_good_replies") or []),
        "example_bad_replies": list(topic.get("example_bad_replies") or []),
        "avoid_rules": avoid_rules,
        **_topic_brief_selection_state(style_rule),
    }


async def _handle_topic_create_text(
    update: Any,
    context: Any,
    pending: PendingEdit,
    raw_text: str,
) -> bool:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return False

    step = pending.flow_step or _TOPIC_CREATE_STEP_ORDER[0]
    state = dict(pending.flow_state or {})
    text = raw_text.strip()
    normalized_step = _topic_create_normalized_step(step)

    if normalized_step == "name":
        if not text:
            await _reply(update, "Topic name cannot be blank.\n\n" + render_edit_request(pending))
            return True
        state["name"] = text
        return await _advance_topic_create_step(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            next_step="description",
            flow_state=state,
        )

    if normalized_step == "description":
        if not text:
            await _reply(update, "Conversation target cannot be blank.\n\n" + render_edit_request(pending))
            return True
        state["description"] = text
        return await _advance_topic_create_step(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            next_step="stance_guidance",
            flow_state=state,
        )

    if normalized_step == "stance_guidance":
        if not text:
            await _reply(update, "Reply position cannot be blank.\n\n" + render_edit_request(pending))
            return True
        state["stance_guidance"] = text
        return await _advance_topic_create_step(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            next_step="style_guidance",
            flow_state=state,
        )

    if normalized_step == "style_guidance":
        state["style_guidance"] = "" if text == "-" else text
        return await _advance_topic_create_step(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            next_step="example_good_replies",
            flow_state=state,
        )

    if normalized_step == "example_good_replies":
        existing_examples = list(state.get("example_good_replies") or [])
        if text == "-":
            if not existing_examples:
                state["example_good_replies"] = []
            return await _advance_topic_create_step(
                update,
                context,
                operator_id=operator_id,
                raw_value=raw_text,
                next_step="example_bad_replies",
                flow_state=state,
            )
        next_examples = _split_topic_examples(raw_text)
        if not next_examples:
            await _reply(
                update,
                "Paste one or more good examples, or - to skip.\n\n" + render_edit_request(pending),
            )
            return True
        state["example_good_replies"] = _merge_topic_examples(existing_examples, next_examples)
        return await _advance_topic_create_step(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            next_step="example_good_replies_review",
            flow_state=state,
        )

    if normalized_step == "example_bad_replies":
        existing_examples = list(state.get("example_bad_replies") or [])
        if text == "-":
            if not existing_examples:
                state["example_bad_replies"] = []
            return await _advance_topic_create_step(
                update,
                context,
                operator_id=operator_id,
                raw_value=raw_text,
                next_step="avoid_rules",
                flow_state=state,
            )
        next_examples = _split_topic_examples(raw_text)
        if not next_examples:
            await _reply(
                update,
                "Paste one or more bad examples, or - to skip.\n\n" + render_edit_request(pending),
            )
            return True
        state["example_bad_replies"] = _merge_topic_examples(existing_examples, next_examples)
        return await _advance_topic_create_step(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            next_step="example_bad_replies_review",
            flow_state=state,
        )

    if normalized_step == "avoid_rules":
        state["avoid_rules"] = "" if text == "-" else text
        return await _topic_create_finish_questions(
            update,
            context,
            operator_id=operator_id,
            raw_value=raw_text,
            flow_state=state,
            reply_func=_reply,
        )

    await _reply(update, "That topic draft is out of sync. Start again when you are ready.")
    _config_edit_store(context).cancel(operator_id)
    return True


async def _advance_topic_create_step(
    update: Any,
    context: Any,
    *,
    operator_id: int,
    raw_value: str,
    next_step: str,
    flow_state: dict[str, Any],
) -> bool:
    updated = _config_edit_store(context).set_value(
        operator_id,
        raw_value=raw_value,
        parsed_value=None,
        flow_step=next_step,
        flow_state=flow_state,
    )
    if updated is None:
        await _reply(update, "That edit expired. Start again when you are ready.")
        return True
    await _show_topic_create_pending(update, updated, context=context, reply_func=_reply)
    return True


async def _handle_topic_brief_callback(update: Any, context: Any, parts: list[str]) -> bool:
    if len(parts) == 1:
        await _start_topic_create(update, context, topic_id=parts[0])
        return True
    if len(parts) == 2 and parts[0] == "nav":
        await _handle_topic_brief_navigation(update, context, action=parts[1])
        return True
    if len(parts) == 2 and parts[0] == "scope":
        await _handle_topic_brief_scope_choice(update, context, scope_type=parts[1])
        return True
    if len(parts) == 2 and parts[0] == "attach":
        await _handle_topic_brief_existing_rule_choice(update, context, rule_id=parts[1])
        return True
    return False


async def _handle_topic_brief_navigation(
    update: Any,
    context: Any,
    *,
    action: str,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).get(operator_id)
    if pending is None or pending.entity != "topic_create":
        await _callback_reply(update, "No draft brief is waiting right now.")
        return
    if action == "later":
        await _callback_reply(update, _topic_create_saved_for_later_message(pending))
        return
    if action == "back":
        updated = _topic_create_step_back(context, operator_id, pending)
        if updated is None:
            await _callback_reply(update, "That draft brief expired. Start again when you are ready.")
            return
        await _show_topic_create_pending(update, updated, context=context, reply_func=_callback_reply)
        return
    if action == "skip":
        updated = _topic_create_skip_step(context, operator_id, pending)
        if updated is None:
            await _callback_reply(update, "This step needs an answer.")
            return
        await _show_topic_create_pending(update, updated, context=context, reply_func=_callback_reply)
        return
    if action == "add":
        updated = _topic_create_add_another_step(context, operator_id, pending)
        if updated is None:
            await _callback_reply(update, "That example loop is no longer available.")
            return
        await _show_topic_create_pending(update, updated, context=context, reply_func=_callback_reply)
        return
    if action == "continue":
        updated = _topic_create_continue_step(context, operator_id, pending)
        if updated is None:
            await _callback_reply(update, "Add at least one example or skip this step first.")
            return
        await _show_topic_create_pending(update, updated, context=context, reply_func=_callback_reply)
        return
    await _callback_reply(update, "That draft-brief action is no longer available.")


__all__ = [
    "_TOPIC_CREATE_STEP_ORDER",
    "_start_topic_create",
    "_start_topic_create_message",
    "_handle_topic_brief_callback",
    "_handle_topic_create_text",
    "_preview_topic_create_sample",
    "_topic_create_confirmation_markup",
    "_upsert_topic_brief_style_rule",
]
