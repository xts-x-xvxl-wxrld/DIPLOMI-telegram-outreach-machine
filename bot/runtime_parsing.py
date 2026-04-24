# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *

from .runtime_context import *
from .runtime_io import *
from .runtime_access import *


def _first_arg(context: Any) -> str | None:
    if not context.args:
        return None
    value = context.args[0].strip()
    return value or None


def _parse_settings_value(field_name: str, raw_value: str) -> tuple[bool, Any | str]:
    field = editable_field("settings", field_name)
    if field is None:
        return False, "That settings field is not editable from the bot."
    return parse_edit_value(field, raw_value)


def _normalize_prompt_profile_edit_field(value: str) -> str | None:
    normalized = value.strip().casefold()
    if normalized in PROMPT_PROFILE_EDIT_FIELD_CODES:
        return PROMPT_PROFILE_EDIT_FIELD_CODES[normalized]
    if normalized in PROMPT_PROFILE_EDIT_FIELDS:
        return normalized
    return None


def _normalize_settings_edit_field(value: str) -> str | None:
    normalized = value.strip().casefold()
    field = SETTINGS_EDIT_FIELD_CODES.get(normalized, normalized)
    if editable_field("settings", field) is None:
        return None
    return field


def _second_arg_as_offset(context: Any) -> int:
    if len(context.args) < 2:
        return 0
    return _parse_offset(context.args[1])


def _positive_int_arg(context: Any, *, default: int) -> int:
    value = _first_arg(context)
    if value is None:
        return default
    return _parse_positive_int(value, default=default)


def _engagement_candidate_status_arg(context: Any) -> str:
    status = _first_arg(context) or "needs_review"
    if status not in ENGAGEMENT_CANDIDATE_STATUSES:
        return "needs_review"
    return status


def _engagement_target_status_arg(context: Any) -> str | None:
    status = _first_arg(context)
    if status is None or status == "all":
        return None
    if status not in ENGAGEMENT_TARGET_STATUSES:
        return None
    return status


def _engagement_callback_status_and_offset(parts: list[str]) -> tuple[str, int]:
    if len(parts) >= 2:
        raw_status = parts[0]
        status = raw_status if raw_status in ENGAGEMENT_CANDIDATE_STATUSES else "needs_review"
        return status, _parse_offset(parts[1])
    return "needs_review", _parse_offset(parts[0])


def _engagement_target_callback_status_and_offset(parts: list[str]) -> tuple[str | None, int]:
    if len(parts) >= 2:
        raw_status = parts[0]
        status = raw_status if raw_status in ENGAGEMENT_TARGET_STATUSES else None
        return status, _parse_offset(parts[1])
    return None, _parse_offset(parts[0])


def _engagement_actions_filter_and_offset(parts: list[str]) -> tuple[str | None, int]:
    if len(parts) >= 2:
        return parts[0], _parse_offset(parts[1])
    return None, _parse_offset(parts[0])


def _parse_engagement_style_args(context: Any) -> tuple[str | None, str | None]:
    if not context.args:
        return None, None
    scope_type = str(context.args[0]).strip().casefold()
    if scope_type not in ENGAGEMENT_STYLE_SCOPE_VALUES:
        raise ValueError("invalid_style_scope")
    scope_id = str(context.args[1]).strip() if len(context.args) > 1 else None
    if scope_type == "global":
        return "global", None
    if not scope_id:
        return scope_type, None
    return scope_type, scope_id


def _parse_style_callback_parts(parts: list[str]) -> tuple[str | None, str | None, int]:
    if len(parts) >= 3:
        scope_type = parts[0]
        scope_id = None if parts[1] == "-" else parts[1]
        if scope_type == "all":
            scope_type = None
            scope_id = None
        return scope_type, scope_id, _parse_offset(parts[2])
    if len(parts) == 2:
        scope_type = parts[0]
        if scope_type == "all":
            return None, None, _parse_offset(parts[1])
        return scope_type, None, _parse_offset(parts[1])
    return None, None, _parse_offset(parts[0])


def _engagement_preset_payload(preset: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reply_only": True,
        "require_approval": True,
        "max_posts_per_day": 1,
        "min_minutes_between_posts": 240,
    }
    if preset == "ready":
        return {
            **base,
            "mode": "require_approval",
            "allow_join": True,
            "allow_post": True,
        }
    if preset == "observe":
        return {**base, "mode": "observe", "allow_join": False, "allow_post": False}
    if preset == "suggest":
        return {**base, "mode": "suggest", "allow_join": False, "allow_post": False}
    return {**base, "mode": "disabled", "allow_join": False, "allow_post": False}


def _engagement_settings_payload_from_current(
    current: dict[str, Any],
    **updates: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": current.get("mode") or "disabled",
        "allow_join": bool(current.get("allow_join")),
        "allow_post": bool(current.get("allow_post")),
        "reply_only": True,
        "require_approval": True,
        "max_posts_per_day": int(current.get("max_posts_per_day") or 1),
        "min_minutes_between_posts": int(current.get("min_minutes_between_posts") or 240),
        "quiet_hours_start": current.get("quiet_hours_start"),
        "quiet_hours_end": current.get("quiet_hours_end"),
        "assigned_account_id": current.get("assigned_account_id"),
    }
    payload.update(updates)
    return payload


def _optional_window_minutes(context: Any) -> int | None:
    if len(context.args) < 2:
        return 60
    try:
        value = int(context.args[1])
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_positive_int(raw_value: str, *, default: int) -> int:
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_create_engagement_topic_args(context: Any) -> tuple[str, str, list[str]] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
    parsed = _parse_create_engagement_topic_text(raw_value)
    if parsed is None:
        return None
    return (
        str(parsed["name"]),
        str(parsed["stance_guidance"]),
        list(parsed["trigger_keywords"]),
    )


def _parse_create_engagement_topic_text(raw_value: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in raw_value.split("|", maxsplit=4)]
    if len(parts) < 3 or len(parts) > 5:
        return None

    name, guidance, raw_keywords, *optional_parts = parts
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    if not name or not guidance or not keywords:
        return None

    description = None
    negative_keywords: list[str] = []
    if optional_parts:
        raw_description = optional_parts[0]
        if raw_description and raw_description != "-":
            description = raw_description
    if len(optional_parts) > 1:
        negative_keywords = [
            keyword.strip() for keyword in optional_parts[1].split(",") if keyword.strip()
        ]

    return {
        "name": name,
        "description": description,
        "stance_guidance": guidance,
        "trigger_keywords": keywords,
        "negative_keywords": negative_keywords,
        "active": True,
    }


def _parse_create_engagement_target_text(raw_value: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in raw_value.split("|", maxsplit=1)]
    if not parts:
        return None
    target_ref = parts[0]
    if not target_ref:
        return None
    notes = None
    if len(parts) > 1 and parts[1] and parts[1] != "-":
        notes = parts[1]
    return {"target_ref": target_ref, "notes": notes}


def _parse_create_engagement_prompt_args(context: Any) -> dict[str, Any] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
    return _parse_create_engagement_prompt_text(raw_value)


def _parse_create_engagement_prompt_text(raw_value: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in raw_value.split("|", maxsplit=6)]
    if len(parts) != 7:
        return None
    (
        name,
        description,
        model,
        raw_temperature,
        raw_max_output_tokens,
        system_prompt,
        user_prompt_template,
    ) = parts
    if not name or not model or not system_prompt or not user_prompt_template:
        return None
    temperature_field = editable_field("prompt_profile", "temperature")
    max_tokens_field = editable_field("prompt_profile", "max_output_tokens")
    template_field = editable_field("prompt_profile", "user_prompt_template")
    if temperature_field is None or max_tokens_field is None or template_field is None:
        return None
    temperature_ok, temperature = parse_edit_value(temperature_field, raw_temperature)
    max_tokens_ok, max_output_tokens = parse_edit_value(max_tokens_field, raw_max_output_tokens)
    template_ok, parsed_template = parse_edit_value(template_field, user_prompt_template)
    if not (temperature_ok and max_tokens_ok and template_ok):
        return None
    return {
        "name": name,
        "description": None if description in {"", "-"} else description,
        "active": False,
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "system_prompt": system_prompt,
        "user_prompt_template": parsed_template,
        "output_schema_name": "engagement_detection_v1",
    }


def _create_engagement_prompt_error(raw_value: str) -> str | None:
    parts = [part.strip() for part in raw_value.split("|", maxsplit=6)]
    if len(parts) != 7:
        return None
    _, _, _, raw_temperature, raw_max_output_tokens, _, user_prompt_template = parts
    checks = [
        ("prompt_profile", "temperature", raw_temperature),
        ("prompt_profile", "max_output_tokens", raw_max_output_tokens),
        ("prompt_profile", "user_prompt_template", user_prompt_template),
    ]
    for entity, field_name, value in checks:
        field = editable_field(entity, field_name)
        if field is None:
            continue
        ok, parsed_or_error = parse_edit_value(field, value)
        if not ok:
            return str(parsed_or_error)
    return None


def _parse_create_style_rule_args(
    context: Any,
) -> tuple[str, str | None, str, int, str] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
    return _parse_create_style_rule_text(raw_value)


def _parse_create_style_rule_text(
    raw_value: str,
) -> tuple[str, str | None, str, int, str] | None:
    parts = [part.strip() for part in raw_value.split("|", maxsplit=3)]
    if len(parts) != 4:
        return None
    scope_part, name, raw_priority, rule_text = parts
    scope_bits = scope_part.split()
    if len(scope_bits) != 2:
        return None
    scope_type = scope_bits[0].strip().casefold()
    scope_id_token = scope_bits[1].strip()
    if scope_type not in ENGAGEMENT_STYLE_SCOPE_VALUES:
        return None
    if scope_type == "global":
        scope_id = None
    else:
        scope_id = None if scope_id_token == "-" else scope_id_token
        if scope_id is None:
            return None
    try:
        priority = int(raw_priority)
    except ValueError:
        return None
    if not name or not rule_text:
        return None
    return scope_type, scope_id, name, priority, rule_text


async def _topic_example_command(update: Any, context: Any, *, example_type: str) -> None:
    parsed = _parse_topic_example_args(context)
    if parsed is None:
        command = "topic_good_reply" if example_type == "good" else "topic_bad_reply"
        await _reply(update, f"Usage: /{command} <topic_id> | <example>")
        return
    topic_id, example = parsed
    client = _api_client(context)
    try:
        data = await client.add_engagement_topic_example(
            topic_id,
            example_type=example_type,
            example=example,
            operator_user_id=_telegram_user_id(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(
        update,
        "Topic example added.\n\n" + format_engagement_topic_card(data, detail=True),
        reply_markup=engagement_topic_actions_markup(
            topic_id,
            active=bool(data.get("active")),
            good_count=len(data.get("example_good_replies") or []),
            bad_count=len(data.get("example_bad_replies") or []),
        ),
    )


def _parse_topic_example_args(context: Any) -> tuple[str, str] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
    parts = [part.strip() for part in raw_value.split("|", maxsplit=1)]
    if len(parts) != 2:
        return None
    topic_id, example = parts
    if not topic_id or not example:
        return None
    return topic_id, example


def _parse_edit_reply_args(context: Any) -> tuple[str, str] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
    parts = [part.strip() for part in raw_value.split("|", maxsplit=1)]
    if len(parts) != 2:
        return None
    candidate_id, final_reply = parts
    if not candidate_id or not final_reply:
        return None
    return candidate_id, final_reply


def _create_engagement_topic_usage() -> str:
    return "\n".join(
        [
            "Usage: /create_engagement_topic",
            "Send the command with no arguments to start the guided flow.",
            "Legacy inline format: /create_engagement_topic <name> | <guidance> | <comma_keywords> [| <description_or_dash> | <negative_keywords>]",
            "Include at least one trigger keyword.",
            "Example: /create_engagement_topic Open CRM | Be factual and brief. | crm, open source",
        ]
    )


def _create_engagement_target_usage(*, command_name: str | None = "add_engagement_target") -> str:
    prefix = f"Usage: /{command_name} " if command_name else "Send: "
    return "\n".join(
        [
            prefix + "<telegram_link_or_username_or_community_id> [| <notes_or_dash>]",
            "Examples: @opencrm | Priority account pool, or https://t.me/opencrm",
        ]
    )


def _create_engagement_prompt_usage(*, command_name: str | None = "create_engagement_prompt") -> str:
    prefix = (
        f"Usage: /{command_name} "
        if command_name
        else "Send: "
    )
    return "\n".join(
        [
            (
                prefix
                + "<name> | <description_or_dash> | <model> | <temperature> | "
                "<max_output_tokens> | <system_prompt> | <user_prompt_template>"
            ),
            "New prompt profiles are created inactive.",
            (
                "Allowed template variables include {{community.title}}, {{topic.name}}, "
                "and {{source_post.text}}. Sender identity variables are not allowed."
            ),
        ]
    )


def _create_style_rule_usage(*, command_name: str | None = "create_style_rule") -> str:
    prefix = f"Usage: /{command_name} " if command_name else "Send: "
    return "\n".join(
        [
            prefix + "<scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>",
            "Scopes: global, account, community, topic. Use '-' only for global.",
        ]
    )


def _parse_on_off(raw_value: str) -> bool | None:
    value = raw_value.strip().casefold()
    if value == "on":
        return True
    if value == "off":
        return False
    return None


def _parse_callback_bool(raw_value: str) -> bool | None:
    if raw_value == "1":
        return True
    if raw_value == "0":
        return False
    return None


def _normalize_target_permission(raw_value: str) -> str | None:
    value = raw_value.strip().casefold()
    value = ENGAGEMENT_TARGET_PERMISSION_ALIASES.get(value, value)
    if value in ENGAGEMENT_TARGET_PERMISSIONS:
        return value
    return None


def _candidate_community(item: dict[str, Any]) -> dict[str, Any]:
    community = item.get("community")
    if isinstance(community, dict):
        return community
    return item


def _parse_offset(raw_value: str) -> int:
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return 0


__all__ = [
    "_first_arg",
    "_parse_settings_value",
    "_normalize_prompt_profile_edit_field",
    "_normalize_settings_edit_field",
    "_second_arg_as_offset",
    "_positive_int_arg",
    "_engagement_candidate_status_arg",
    "_engagement_target_status_arg",
    "_engagement_callback_status_and_offset",
    "_engagement_target_callback_status_and_offset",
    "_engagement_actions_filter_and_offset",
    "_parse_engagement_style_args",
    "_parse_style_callback_parts",
    "_engagement_preset_payload",
    "_engagement_settings_payload_from_current",
    "_optional_window_minutes",
    "_parse_positive_int",
    "_parse_create_engagement_topic_args",
    "_parse_create_engagement_topic_text",
    "_parse_create_engagement_target_text",
    "_parse_create_engagement_prompt_args",
    "_parse_create_engagement_prompt_text",
    "_create_engagement_prompt_error",
    "_parse_create_style_rule_args",
    "_parse_create_style_rule_text",
    "_topic_example_command",
    "_parse_topic_example_args",
    "_parse_edit_reply_args",
    "_create_engagement_topic_usage",
    "_create_engagement_target_usage",
    "_create_engagement_prompt_usage",
    "_create_style_rule_usage",
    "_parse_on_off",
    "_parse_callback_bool",
    "_normalize_target_permission",
    "_candidate_community",
    "_parse_offset",
]
