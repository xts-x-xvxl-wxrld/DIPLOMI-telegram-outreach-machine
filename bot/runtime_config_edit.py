# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *

from .runtime_context import *
from .runtime_markup import *
from .runtime_io import *
from .runtime_access import *
from .runtime_parsing import *


async def _start_config_edit(
    update: Any,
    context: Any,
    *,
    entity: str,
    object_id: str,
    field: str,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    if not object_id:
        await _callback_reply(update, "Missing item ID for this edit.")
        return
    editable = editable_field(entity, field)
    if editable is None:
        await _callback_reply(update, "That field is not editable from the bot.")
        return
    if editable.admin_only and not await _require_engagement_admin(update, context):
        return
    pending = _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id=object_id,
    )
    await _callback_reply(update, render_edit_request(pending))


async def _start_prompt_profile_create(update: Any, context: Any) -> None:
    await _start_config_edit(
        update,
        context,
        entity="prompt_profile_create",
        object_id="new",
        field="payload",
    )


async def _start_style_rule_create(update: Any, context: Any) -> None:
    await _start_config_edit(
        update,
        context,
        entity="style_rule_create",
        object_id="new",
        field="payload",
    )


async def _start_topic_create(update: Any, context: Any) -> None:
    await _start_config_edit(
        update,
        context,
        entity="topic_create",
        object_id="new",
        field="payload",
    )


async def _start_target_create(update: Any, context: Any) -> None:
    await _start_config_edit(
        update,
        context,
        entity="target_create",
        object_id="new",
        field="payload",
    )


async def _handle_config_edit_text(update: Any, context: Any, raw_text: str) -> bool:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return False
    store = _config_edit_store(context)
    pending = store.get(operator_id)
    if pending is None:
        return False
    if pending.admin_only and not await _is_engagement_admin_async(update, context):
        store.cancel(operator_id)
        await _reply(update, ENGAGEMENT_ADMIN_ONLY_MESSAGE)
        return True
    if pending.entity == "prompt_profile_create":
        parsed = _parse_create_engagement_prompt_text(raw_text)
        if parsed is None:
            await _reply(
                update,
                _create_engagement_prompt_error(raw_text)
                or _create_engagement_prompt_usage(command_name=None),
            )
            return True
        ok, parsed_or_error = True, parsed
    elif pending.entity == "style_rule_create":
        parsed = _parse_create_style_rule_text(raw_text)
        if parsed is None:
            await _reply(update, _create_style_rule_usage(command_name=None))
            return True
        ok, parsed_or_error = True, {
            "scope_type": parsed[0],
            "scope_id": parsed[1],
            "name": parsed[2],
            "priority": parsed[3],
            "rule_text": parsed[4],
        }
    elif pending.entity == "topic_create":
        parsed = _parse_create_engagement_topic_text(raw_text)
        if parsed is None:
            await _reply(update, _create_engagement_topic_usage())
            return True
        ok, parsed_or_error = True, parsed
    elif pending.entity == "target_create":
        parsed = _parse_create_engagement_target_text(raw_text)
        if parsed is None:
            await _reply(update, _create_engagement_target_usage(command_name=None))
            return True
        ok, parsed_or_error = True, parsed
    else:
        ok, parsed_or_error = parse_edit_value(pending, raw_text)
    if not ok:
        await _reply(update, str(parsed_or_error))
        return True
    updated = store.set_value(operator_id, raw_value=raw_text, parsed_value=parsed_or_error)
    if updated is None:
        await _reply(update, "That edit expired. Start again when you are ready.")
        return True
    await _reply(
        update,
        render_edit_preview(updated),
        reply_markup=config_edit_confirmation_markup(),
    )
    return True


async def _save_config_edit_callback(update: Any, context: Any) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    store = _config_edit_store(context)
    pending = store.get(operator_id)
    if pending is None:
        await _callback_reply(update, "No pending edit to save.")
        return
    if pending.admin_only and not await _is_engagement_admin_async(update, context):
        await _callback_reply(update, ENGAGEMENT_ADMIN_ONLY_MESSAGE)
        return
    if pending.raw_value is None:
        await _callback_reply(update, "Send the replacement value before saving.")
        return
    data = await _save_config_edit(update, context, pending)
    store.cancel(operator_id)
    message, markup = _saved_config_edit_response(pending, data)
    await _edit_callback_message(update, message, reply_markup=markup)


async def _cancel_config_edit_callback(update: Any, context: Any) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).cancel(operator_id)
    await _edit_callback_message(update, render_edit_cancelled(pending))


async def _save_config_edit(update: Any, context: Any, pending: PendingEdit) -> dict[str, Any]:
    client = _api_client(context)
    value = pending.parsed_value
    reviewer = _reviewer_label(update)
    operator_user_id = _telegram_user_id(update)

    if pending.entity == "candidate" and pending.field == "final_reply":
        return await client.edit_engagement_candidate(
            pending.object_id,
            final_reply=str(value),
            edited_by=reviewer,
        )

    if pending.entity == "target":
        return await client.update_engagement_target(
            pending.object_id,
            **{pending.field: value, "updated_by": reviewer},
            operator_user_id=operator_user_id,
        )

    if pending.entity == "prompt_profile":
        return await client.update_engagement_prompt_profile(
            pending.object_id,
            **{pending.field: value, "updated_by": reviewer},
            operator_user_id=operator_user_id,
        )

    if pending.entity == "prompt_profile_create":
        if not isinstance(value, dict):
            raise BotApiError("Prompt profile creation details are incomplete.")
        return await client.create_engagement_prompt_profile(
            **value,
            created_by=reviewer,
            operator_user_id=operator_user_id,
        )

    if pending.entity == "target_create":
        if not isinstance(value, dict):
            raise BotApiError("Target creation details are incomplete.")
        return await client.create_engagement_target(
            **value,
            added_by=reviewer,
            operator_user_id=operator_user_id,
        )

    if pending.entity == "topic":
        return await client.update_engagement_topic(
            pending.object_id,
            **{pending.field: value},
            operator_user_id=operator_user_id,
        )

    if pending.entity == "topic_create":
        if not isinstance(value, dict):
            raise BotApiError("Topic creation details are incomplete.")
        return await client.create_engagement_topic(
            operator_user_id=operator_user_id,
            **value,
        )

    if pending.entity == "topic_example":
        return await client.add_engagement_topic_example(
            pending.object_id,
            example_type=pending.field,
            example=str(value),
            operator_user_id=operator_user_id,
        )

    if pending.entity == "style_rule":
        return await client.update_engagement_style_rule(
            pending.object_id,
            **{pending.field: value, "updated_by": reviewer},
            operator_user_id=operator_user_id,
        )

    if pending.entity == "style_rule_create":
        if not isinstance(value, dict):
            raise BotApiError("Style rule creation details are incomplete.")
        return await client.create_engagement_style_rule(
            **value,
            created_by=reviewer,
            operator_user_id=operator_user_id,
        )

    if pending.entity == "settings":
        current = await client.get_engagement_settings(pending.object_id)
        payload = _engagement_settings_payload_from_current(current, **{pending.field: value})
        return await client.update_engagement_settings(
            pending.object_id,
            **payload,
            operator_user_id=operator_user_id,
        )

    raise BotApiError("That edit type is not available yet.")


def _saved_config_edit_response(pending: PendingEdit, data: dict[str, Any]) -> tuple[str, Any | None]:
    prefix = render_edit_saved(pending)
    if pending.entity == "candidate":
        return (
            prefix + "\n\n" + format_engagement_candidate_card(data),
            _engagement_candidate_detail_markup(pending.object_id, data),
        )
    if pending.entity == "target":
        return (
            prefix + "\n\n" + format_engagement_target_card(data, detail=True),
            _engagement_target_markup(pending.object_id, data),
        )
    if pending.entity == "prompt_profile":
        return (
            prefix + "\n\n" + format_engagement_prompt_profile_card(data, detail=True),
            engagement_prompt_actions_markup(pending.object_id, active=bool(data.get("active"))),
        )
    if pending.entity == "prompt_profile_create":
        profile_id = str(data.get("id", "unknown"))
        return (
            "Prompt profile created.\n\n" + format_engagement_prompt_profile_card(data, detail=True),
            engagement_prompt_actions_markup(profile_id, active=bool(data.get("active"))),
        )
    if pending.entity == "target_create":
        target_id = str(data.get("id", "unknown"))
        return (
            "Engagement target added.\n\n" + format_engagement_target_card(data, detail=True),
            _engagement_target_markup(target_id, data),
        )
    if pending.entity == "topic":
        return (
            prefix + "\n\n" + format_engagement_topic_card(data, detail=True),
            engagement_topic_actions_markup(
                pending.object_id,
                active=bool(data.get("active")),
                good_count=len(data.get("example_good_replies") or []),
                bad_count=len(data.get("example_bad_replies") or []),
            ),
        )
    if pending.entity == "topic_create":
        topic_id = str(data.get("id", "unknown"))
        return (
            "Engagement topic created.\n\n" + format_engagement_topic_card(data, detail=True),
            engagement_topic_actions_markup(
                topic_id,
                active=bool(data.get("active")),
                good_count=len(data.get("example_good_replies") or []),
                bad_count=len(data.get("example_bad_replies") or []),
            ),
        )
    if pending.entity == "topic_example":
        return (
            "Topic example added.\n\n" + format_engagement_topic_card(data, detail=True),
            engagement_topic_actions_markup(
                pending.object_id,
                active=bool(data.get("active")),
                good_count=len(data.get("example_good_replies") or []),
                bad_count=len(data.get("example_bad_replies") or []),
            ),
        )
    if pending.entity == "style_rule":
        return (
            prefix + "\n\n" + format_engagement_style_rule_card(data, detail=True),
            engagement_style_rule_actions_markup(
                pending.object_id,
                active=bool(data.get("active")),
            ),
        )
    if pending.entity == "style_rule_create":
        rule_id = str(data.get("id", "unknown"))
        return (
            "Style rule created.\n\n" + format_engagement_style_rule_card(data, detail=True),
            engagement_style_rule_actions_markup(
                rule_id,
                active=bool(data.get("active")),
            ),
        )
    if pending.entity == "settings":
        return (
            prefix + "\n\n" + format_engagement_settings(data),
            _engagement_settings_markup(pending.object_id, data),
        )
    return prefix, None


__all__ = [
    "_clear_pending_edit_if_command",
    "_start_config_edit",
    "_start_prompt_profile_create",
    "_start_style_rule_create",
    "_start_topic_create",
    "_start_target_create",
    "_handle_config_edit_text",
    "_save_config_edit_callback",
    "_cancel_config_edit_callback",
    "_save_config_edit",
    "_saved_config_edit_response",
]
