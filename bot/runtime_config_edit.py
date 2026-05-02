# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *

from .runtime_context import *
from .runtime_markup import *
from .runtime_io import *
from .runtime_access import *
from .runtime_parsing import *
from .runtime_topic_brief import *


class _TopicCreateStyleRuleSaveError(BotApiError):
    def __init__(self, message: str, *, topic_data: dict[str, Any]) -> None:
        super().__init__(message)
        self.topic_data = topic_data


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
        return await _handle_topic_create_text(update, context, pending, raw_text)
    elif pending.entity == "wizard":
        from bot.engagement_wizard_flow import _handle_wizard_text
        return await _handle_wizard_text(update, context, pending, raw_text)
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
        reply_markup=(
            engagement_topic_brief_confirmation_markup()
            if pending.entity == "topic_create"
            else config_edit_confirmation_markup()
        ),
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
    if pending.entity == "wizard":
        await _callback_reply(update, "Use the wizard buttons to complete setup.")
        return
    if pending.entity == "topic_create" and (
        pending.flow_step != "confirm" or not isinstance(pending.parsed_value, dict)
    ):
        await _callback_reply(update, "Finish the remaining topic questions before saving.")
        return
    if pending.raw_value is None:
        await _callback_reply(update, "Send the replacement value before saving.")
        return
    try:
        data = await _save_config_edit(update, context, pending)
    except _TopicCreateStyleRuleSaveError as exc:
        refreshed = _refresh_topic_create_pending_after_partial_save(
            context,
            operator_id=operator_id,
            pending=pending,
            topic_data=exc.topic_data,
        )
        await _edit_callback_message(
            update,
            "Draft brief saved the topic details, but the wizard-owned style guidance still needs attention.\n\n"
            + format_api_error(exc.message)
            + "\n\n"
            + render_edit_preview(refreshed),
            reply_markup=await _topic_create_confirmation_markup(context, refreshed),
        )
        return
    except BotApiError as exc:
        if pending.entity == "topic_create":
            await _edit_callback_message(
                update,
                "Draft brief not saved yet.\n\n"
                + format_api_error(exc.message)
                + "\n\n"
                + render_edit_preview(pending),
                reply_markup=await _topic_create_confirmation_markup(context, pending),
            )
            return
        raise
    store.cancel(operator_id)
    if pending.entity == "topic_create":
        from bot.engagement_wizard_flow import _wizard_return_pop, _wizard_resume_after_topic_create
        wizard_state = _wizard_return_pop(context, operator_id)
        if wizard_state is not None:
            await _wizard_resume_after_topic_create(update, context, wizard_state, data)
            return
    message, markup = _saved_config_edit_response(pending, data)
    await _edit_callback_message(update, message, reply_markup=markup)

async def _cancel_config_edit_callback(update: Any, context: Any) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).cancel(operator_id)
    if pending is not None and pending.entity == "topic_create":
        from bot.engagement_wizard_flow import _wizard_return_pop, _wizard_resume_after_topic_create

        wizard_state = _wizard_return_pop(context, operator_id)
        if wizard_state is not None:
            await _wizard_resume_after_topic_create(update, context, wizard_state, {})
            return
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
        topic_payload = {
            "name": value["name"],
            "description": value["description"],
            "stance_guidance": value["stance_guidance"],
            "trigger_keywords": value.get("trigger_keywords") or [],
            "negative_keywords": value.get("negative_keywords") or [],
            "example_good_replies": value.get("example_good_replies") or [],
            "example_bad_replies": value.get("example_bad_replies") or [],
            "active": True,
        }
        if pending.object_id == "new":
            topic_data = await client.create_engagement_topic(
                operator_user_id=operator_user_id,
                **topic_payload,
            )
        else:
            topic_data = await client.update_engagement_topic(
                pending.object_id,
                operator_user_id=operator_user_id,
                **topic_payload,
            )
        try:
            await _upsert_topic_brief_style_rule(
                client,
                topic_id=str(topic_data.get("id") or pending.object_id),
                style_guidance=str(value.get("style_guidance") or ""),
                avoid_rules=str(value.get("avoid_rules") or ""),
                reviewer=reviewer,
                operator_user_id=operator_user_id,
                target_mode=str(value.get("style_rule_target_mode") or "wizard"),
                scope_type=str(value.get("style_rule_scope_type") or "topic"),
                scope_id=str(value.get("style_rule_scope_id") or "") or None,
                style_rule_id=str(value.get("style_rule_id") or "") or None,
            )
        except BotApiError as exc:
            raise _TopicCreateStyleRuleSaveError(exc.message, topic_data=topic_data) from exc
        return topic_data

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

    if pending.entity == "wizard":
        raise BotApiError("Wizard state cannot be saved directly.")

    raise BotApiError("That edit type is not available yet.")


def _refresh_topic_create_pending_after_partial_save(
    context: Any,
    *,
    operator_id: int,
    pending: PendingEdit,
    topic_data: dict[str, Any],
) -> PendingEdit:
    editable = editable_field("topic_create", "payload")
    if editable is None:
        return pending
    topic_id = str(topic_data.get("id") or pending.object_id)
    flow_state = dict(pending.flow_state or {})
    parsed_value = dict(pending.parsed_value or {}) if isinstance(pending.parsed_value, dict) else {}
    for key in (
        "name",
        "description",
        "stance_guidance",
        "trigger_keywords",
        "negative_keywords",
        "example_good_replies",
        "example_bad_replies",
        "style_guidance",
        "avoid_rules",
        "style_rule_id",
        "style_rule_name",
        "style_rule_target_mode",
        "style_rule_scope_type",
        "style_rule_scope_id",
        "community_id",
        "active",
    ):
        if key in topic_data:
            parsed_value[key] = topic_data.get(key)
    flow_state.update(
        {
            "name": str(topic_data.get("name") or parsed_value.get("name") or ""),
            "description": str(topic_data.get("description") or parsed_value.get("description") or ""),
            "stance_guidance": str(topic_data.get("stance_guidance") or parsed_value.get("stance_guidance") or ""),
            "example_good_replies": list(
                topic_data.get("example_good_replies") or parsed_value.get("example_good_replies") or []
            ),
            "example_bad_replies": list(
                topic_data.get("example_bad_replies") or parsed_value.get("example_bad_replies") or []
            ),
        }
    )
    if parsed_value.get("style_rule_scope_type") == "topic":
        parsed_value["style_rule_scope_id"] = topic_id
        flow_state["style_rule_scope_id"] = topic_id
    restarted = _config_edit_store(context).start(
        operator_id=operator_id,
        field=editable,
        object_id=topic_id,
        flow_step="confirm",
        flow_state=flow_state,
    )
    return (
        _config_edit_store(context).set_value(
            operator_id,
            raw_value=pending.raw_value or "",
            parsed_value=parsed_value,
            flow_step="confirm",
            flow_state=flow_state,
        )
        or restarted
    )


def _saved_config_edit_response(pending: PendingEdit, data: dict[str, Any]) -> tuple[str, Any | None]:
    prefix = render_edit_saved(pending)
    if pending.entity == "candidate":
        return (
            prefix + "\n\n" + format_engagement_candidate_card(data, detail=True),
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
        heading = "Draft brief updated." if pending.object_id != "new" else "Engagement topic created."
        return (
            heading + "\n\n" + format_engagement_topic_card(data, detail=True),
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
    "_start_topic_create_message",
    "_start_target_create",
    "_handle_config_edit_text",
    "_save_config_edit_callback",
    "_cancel_config_edit_callback",
    "_handle_topic_brief_callback",
    "_preview_topic_create_sample",
    "_save_config_edit",
    "_saved_config_edit_response",
]
