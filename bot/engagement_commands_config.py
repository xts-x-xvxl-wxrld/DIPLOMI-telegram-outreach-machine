# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

import csv
import io
import re
from typing import Any

from bot.api_client import BotApiClient, BotApiError
from bot.config import BotSettings, load_settings, validate_runtime_settings
from bot.config_editing import (
    PendingEdit,
    PendingEditStore,
    editable_field,
    parse_edit_value,
    render_edit_cancelled,
    render_edit_preview,
    render_edit_request,
    render_edit_saved,
)
from bot.formatting import (
    format_access_denied,
    format_accounts,
    format_api_error,
    format_briefs_unavailable,
    format_candidate_card,
    format_candidates,
    format_community_detail,
    format_created_brief,
    format_discovery_cockpit,
    format_discovery_help,
    format_engagement_action_card,
    format_engagement_actions,
    format_engagement_admin_advanced_home,
    format_engagement_admin_home,
    format_engagement_admin_limits_home,
    format_engagement_account_assignment_confirmation,
    format_engagement_candidate_card,
    format_engagement_candidate_review,
    format_engagement_candidate_revisions,
    format_engagement_candidates,
    format_engagement_home,
    format_engagement_job_response,
    format_engagement_prompt_activation_confirmation,
    format_engagement_prompt_preview,
    format_engagement_prompt_profile_card,
    format_engagement_prompt_profiles,
    format_engagement_prompt_rollback_confirmation,
    format_engagement_prompt_versions,
    format_engagement_settings,
    format_engagement_settings_lookup,
    format_engagement_semantic_rollout,
    format_engagement_style_rule_card,
    format_engagement_style_rules,
    format_engagement_target_card,
    format_engagement_target_approval_confirmation,
    format_engagement_target_mutation,
    format_engagement_target_permission_confirmation,
    format_engagement_targets,
    format_engagement_topic_card,
    format_engagement_topics,
    format_help,
    format_job_status,
    format_member_export,
    format_members,
    format_operator_cockpit,
    format_review,
    format_seed_channels,
    format_seed_group,
    format_seed_group_card,
    format_seed_group_resolution,
    format_seed_groups,
    format_seed_import,
    format_snapshot_job,
    format_telegram_entity_intake,
    format_telegram_entity_submission,
    format_whoami,
)
from bot.ui import (
    ACCOUNTS_MENU_LABEL,
    ACTION_ENGAGEMENT_ACCOUNT_CANCEL,
    ACTION_ENGAGEMENT_ACCOUNT_CONFIRM,
    ACTION_APPROVE_COMMUNITY,
    ACTION_COMMUNITY_MEMBERS,
    ACTION_CONFIG_EDIT_CANCEL,
    ACTION_CONFIG_EDIT_SAVE,
    ACTION_DISC_ACTIVITY,
    ACTION_DISC_ALL,
    ACTION_DISC_ATTENTION,
    ACTION_DISC_HELP,
    ACTION_DISC_HOME,
    ACTION_DISC_REVIEW,
    ACTION_DISC_START,
    ACTION_DISC_WATCHING,
    ACTION_ENGAGEMENT_ACTIONS,
    ACTION_ENGAGEMENT_ADMIN,
    ACTION_ENGAGEMENT_ADMIN_ADVANCED,
    ACTION_ENGAGEMENT_ADMIN_LIMITS,
    ACTION_ENGAGEMENT_APPROVE,
    ACTION_ENGAGEMENT_CANDIDATES,
    ACTION_ENGAGEMENT_CANDIDATE_EDIT,
    ACTION_ENGAGEMENT_CANDIDATE_EXPIRE,
    ACTION_ENGAGEMENT_CANDIDATE_OPEN,
    ACTION_ENGAGEMENT_CANDIDATE_RETRY,
    ACTION_ENGAGEMENT_CANDIDATE_REVISIONS,
    ACTION_ENGAGEMENT_DETECT,
    ACTION_ENGAGEMENT_HOME,
    ACTION_ENGAGEMENT_JOIN,
    ACTION_ENGAGEMENT_PROMPT_ACTIVATE,
    ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM,
    ACTION_ENGAGEMENT_PROMPT_CREATE,
    ACTION_ENGAGEMENT_PROMPT_DUPLICATE,
    ACTION_ENGAGEMENT_PROMPT_EDIT,
    ACTION_ENGAGEMENT_PROMPT_OPEN,
    ACTION_ENGAGEMENT_PROMPT_PREVIEW,
    ACTION_ENGAGEMENT_PROMPT_ROLLBACK,
    ACTION_ENGAGEMENT_PROMPT_ROLLBACK_CONFIRM,
    ACTION_ENGAGEMENT_PROMPT_VERSIONS,
    ACTION_ENGAGEMENT_PROMPTS,
    ACTION_ENGAGEMENT_REJECT,
    ACTION_ENGAGEMENT_SEND,
    ACTION_ENGAGEMENT_SETTINGS_JOIN,
    ACTION_ENGAGEMENT_SETTINGS_EDIT,
    ACTION_ENGAGEMENT_SETTINGS_LOOKUP,
    ACTION_ENGAGEMENT_SETTINGS_OPEN,
    ACTION_ENGAGEMENT_SETTINGS_POST,
    ACTION_ENGAGEMENT_SETTINGS_PRESET,
    ACTION_ENGAGEMENT_STYLE,
    ACTION_ENGAGEMENT_STYLE_CREATE,
    ACTION_ENGAGEMENT_STYLE_EDIT,
    ACTION_ENGAGEMENT_STYLE_OPEN,
    ACTION_ENGAGEMENT_STYLE_TOGGLE,
    ACTION_ENGAGEMENT_TARGET_ADD,
    ACTION_ENGAGEMENT_TARGET_APPROVE,
    ACTION_ENGAGEMENT_TARGET_APPROVE_CONFIRM,
    ACTION_ENGAGEMENT_TARGET_ARCHIVE,
    ACTION_ENGAGEMENT_TARGET_DETECT,
    ACTION_ENGAGEMENT_TARGET_EDIT,
    ACTION_ENGAGEMENT_TARGET_JOIN,
    ACTION_ENGAGEMENT_TARGET_OPEN,
    ACTION_ENGAGEMENT_TARGET_PERMISSION,
    ACTION_ENGAGEMENT_TARGET_PERMISSION_CONFIRM,
    ACTION_ENGAGEMENT_TARGET_REJECT,
    ACTION_ENGAGEMENT_TARGET_RESOLVE,
    ACTION_ENGAGEMENT_TARGETS,
    ACTION_ENGAGEMENT_TOPIC_EDIT,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_ENGAGEMENT_TOPIC_OPEN,
    ACTION_ENGAGEMENT_TOPIC_TOGGLE,
    ACTION_JOB_STATUS,
    ACTION_OP_ACCOUNTS,
    ACTION_OP_DISCOVERY,
    ACTION_OP_HELP,
    ACTION_OP_HOME,
    ACTION_OPEN_COMMUNITY,
    ACTION_OPEN_SEED_GROUP,
    ACTION_REJECT_COMMUNITY,
    ACTION_RESOLVE_SEED_GROUP,
    ACTION_SEED_CANDIDATES,
    ACTION_SEED_CHANNELS,
    ACTION_SNAPSHOT_COMMUNITY,
    HELP_MENU_LABEL,
    ENGAGEMENT_MENU_LABEL,
    SEEDS_MENU_LABEL,
    candidate_actions_markup,
    community_actions_markup,
    config_edit_confirmation_markup,
    discovery_cockpit_markup,
    engagement_account_confirm_markup,
    discovery_seeds_markup,
    engagement_action_pager_markup,
    engagement_admin_advanced_markup,
    engagement_admin_home_markup,
    engagement_admin_limits_markup,
    engagement_candidate_actions_markup,
    engagement_candidate_detail_markup,
    engagement_candidate_filter_markup,
    engagement_candidate_pager_markup,
    engagement_candidate_revisions_markup,
    engagement_candidate_send_markup,
    engagement_home_markup,
    engagement_prompt_actions_markup,
    engagement_prompt_activation_confirm_markup,
    engagement_prompt_list_markup,
    engagement_prompt_rollback_confirm_markup,
    engagement_prompt_versions_markup,
    engagement_job_markup,
    engagement_settings_markup,
    engagement_settings_lookup_markup,
    engagement_style_list_markup,
    engagement_style_rule_actions_markup,
    engagement_target_actions_markup,
    engagement_target_approval_confirm_markup,
    engagement_target_permission_confirm_markup,
    engagement_target_list_markup,
    engagement_topic_actions_markup,
    engagement_topic_pager_markup,
    job_actions_markup,
    member_pager_markup,
    operator_cockpit_markup,
    parse_callback_data,
    reply_keyboard_remove,
    review_result_markup,
    seed_group_actions_markup,
    seed_group_pager_markup,
)


API_CLIENT_KEY = "api_client"
CONFIG_EDIT_STORE_KEY = "config_edit_store"
ACCOUNT_CONFIRM_STORE_KEY = "account_confirm_store"
OPERATOR_CAPABILITY_CACHE_KEY = "operator_capabilities"
CANDIDATE_PAGE_SIZE = 5
CHANNEL_PAGE_SIZE = 5
MEMBER_PAGE_SIZE = 10
MEMBER_EXPORT_PAGE_SIZE = 1000
ENGAGEMENT_CANDIDATE_PAGE_SIZE = 5
ENGAGEMENT_TOPIC_PAGE_SIZE = 5
ENGAGEMENT_ACTION_PAGE_SIZE = 5
ENGAGEMENT_ADMIN_PAGE_SIZE = 5
ENGAGEMENT_CANDIDATE_STATUSES = {"needs_review", "approved", "failed", "sent", "rejected"}
ENGAGEMENT_TARGET_STATUSES = {"pending", "resolved", "approved", "rejected", "archived", "failed"}
ENGAGEMENT_STYLE_SCOPE_VALUES = {"global", "account", "community", "topic"}
TOPIC_KEYWORD_FIELDS = {"trigger": "trigger_keywords", "negative": "negative_keywords"}
PROMPT_PROFILE_EDIT_FIELD_CODES = {
    "n": "name",
    "d": "description",
    "m": "model",
    "t": "temperature",
    "x": "max_output_tokens",
    "s": "system_prompt",
    "u": "user_prompt_template",
}
PROMPT_PROFILE_EDIT_FIELDS = set(PROMPT_PROFILE_EDIT_FIELD_CODES.values())
SETTINGS_EDIT_FIELD_CODES = {
    "mp": "max_posts_per_day",
    "gap": "min_minutes_between_posts",
    "qs": "quiet_hours_start",
    "qe": "quiet_hours_end",
    "acct": "assigned_account_id",
}
ENGAGEMENT_TARGET_PERMISSIONS = {"join": "allow_join", "detect": "allow_detect", "post": "allow_post"}
ENGAGEMENT_TARGET_PERMISSION_ALIASES = {"j": "join", "d": "detect", "p": "post"}
ENGAGEMENT_SETTING_PRESETS = {"off", "observe", "suggest", "ready"}
ENGAGEMENT_ADMIN_ONLY_MESSAGE = (
    "This engagement admin control is limited to admin operators."
)

from .runtime import *

from .engagement_targets_flow import *
from .engagement_prompts_flow import *
from .engagement_review_flow import *
from .engagement_topics_flow import *


async def engagement_prompts_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    try:
        await _send_engagement_prompts(update, context, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_prompt_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    profile_id = _first_arg(context)
    if profile_id is None:
        await _reply(update, "Usage: /engagement_prompt <profile_id>")
        return
    try:
        await _send_engagement_prompt_detail(update, context, profile_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_prompt_versions_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    profile_id = _first_arg(context)
    if profile_id is None:
        await _reply(update, "Usage: /engagement_prompt_versions <profile_id>")
        return
    try:
        await _send_engagement_prompt_versions(update, context, profile_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_prompt_preview_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    profile_id = _first_arg(context)
    if profile_id is None:
        await _reply(update, "Usage: /engagement_prompt_preview <profile_id>")
        return
    client = _api_client(context)
    try:
        data = await client.preview_engagement_prompt_profile(profile_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(update, format_engagement_prompt_preview(data))


async def create_engagement_prompt_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    parsed = _parse_create_engagement_prompt_args(context)
    if parsed is None:
        raw_value = " ".join(str(arg) for arg in context.args).strip()
        await _reply(update, _create_engagement_prompt_error(raw_value) or _create_engagement_prompt_usage())
        return
    client = _api_client(context)
    try:
        data = await client.create_engagement_prompt_profile(
            **parsed,
            created_by=_reviewer_label(update),
            operator_user_id=_telegram_user_id(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    profile_id = str(data.get("id", "unknown"))
    await _reply(
        update,
        "Prompt profile created.\n\n" + format_engagement_prompt_profile_card(data, detail=True),
        reply_markup=engagement_prompt_actions_markup(profile_id, active=bool(data.get("active"))),
    )


async def activate_engagement_prompt_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    profile_id = _first_arg(context)
    if profile_id is None:
        await _reply(update, "Usage: /activate_engagement_prompt <profile_id>")
        return
    try:
        await _confirm_engagement_prompt_activation(update, context, profile_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def duplicate_engagement_prompt_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(update, "Usage: /duplicate_engagement_prompt <profile_id> <new_name>")
        return
    profile_id = str(context.args[0]).strip()
    new_name = " ".join(str(part).strip() for part in context.args[1:]).strip()
    if not profile_id or not new_name:
        await _reply(update, "Usage: /duplicate_engagement_prompt <profile_id> <new_name>")
        return
    client = _api_client(context)
    try:
        data = await client.duplicate_engagement_prompt_profile(
            profile_id,
            name=new_name,
            created_by=_reviewer_label(update),
            operator_user_id=_telegram_user_id(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(
        update,
        "Prompt profile duplicated.\n\n" + format_engagement_prompt_profile_card(data, detail=True),
        reply_markup=engagement_prompt_actions_markup(str(data.get("id", profile_id)), active=bool(data.get("active"))),
    )


async def edit_engagement_prompt_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(update, "Usage: /edit_engagement_prompt <profile_id> <field>")
        return
    profile_id = str(context.args[0]).strip()
    field = _normalize_prompt_profile_edit_field(str(context.args[1]).strip())
    if not profile_id or field is None:
        await _reply(
            update,
            "Usage: /edit_engagement_prompt <profile_id> <field>\n"
            "Fields: " + ", ".join(sorted(PROMPT_PROFILE_EDIT_FIELDS)),
        )
        return
    await _start_config_edit(update, context, entity="prompt_profile", object_id=profile_id, field=field)


async def rollback_engagement_prompt_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(update, "Usage: /rollback_engagement_prompt <profile_id> <version_number>")
        return
    profile_id = str(context.args[0]).strip()
    version_number = _parse_positive_int(str(context.args[1]), default=0)
    if not profile_id or version_number <= 0:
        await _reply(update, "Usage: /rollback_engagement_prompt <profile_id> <version_number>")
        return
    try:
        await _confirm_engagement_prompt_rollback(update, context, profile_id, version_number)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_style_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    parsed = _parse_engagement_style_args(context)
    try:
        await _send_engagement_style_rules(
            update,
            context,
            scope_type=parsed[0],
            scope_id=parsed[1],
            offset=0,
        )
    except ValueError:
        await _reply(update, "Usage: /engagement_style [global|account|community|topic] [scope_id]")
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_style_rule_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    rule_id = _first_arg(context)
    if rule_id is None:
        await _reply(update, "Usage: /engagement_style_rule <rule_id>")
        return
    try:
        await _send_engagement_style_rule(update, context, rule_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def create_style_rule_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    parsed = _parse_create_style_rule_args(context)
    if parsed is None:
        await _reply(update, _create_style_rule_usage())
        return
    scope_type, scope_id, name, priority, rule_text = parsed
    client = _api_client(context)
    try:
        data = await client.create_engagement_style_rule(
            scope_type=scope_type,
            scope_id=scope_id,
            name=name,
            priority=priority,
            rule_text=rule_text,
            created_by=_reviewer_label(update),
            operator_user_id=_telegram_user_id(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    rule_id = str(data.get("id", "unknown"))
    await _reply(
        update,
        "Style rule created.\n\n" + format_engagement_style_rule_card(data, detail=True),
        reply_markup=engagement_style_rule_actions_markup(rule_id, active=bool(data.get("active"))),
    )


async def edit_style_rule_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    rule_id = _first_arg(context)
    if rule_id is None:
        await _reply(update, "Usage: /edit_style_rule <rule_id>")
        return
    await _start_config_edit(update, context, entity="style_rule", object_id=rule_id, field="rule_text")


async def toggle_style_rule_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(update, "Usage: /toggle_style_rule <rule_id> <on|off>")
        return
    rule_id = str(context.args[0]).strip()
    active = _parse_on_off(str(context.args[1]))
    if not rule_id or active is None:
        await _reply(update, "Usage: /toggle_style_rule <rule_id> <on|off>")
        return
    try:
        await _toggle_style_rule(update, context, rule_id, active=active)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_settings_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /engagement_settings <community_id>")
        return

    try:
        await _send_engagement_settings(update, context, community_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def set_engagement_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(update, "Usage: /set_engagement <community_id> <off|observe|suggest|ready>")
        return

    community_id = str(context.args[0]).strip()
    preset = str(context.args[1]).strip().casefold()
    if not community_id or preset not in ENGAGEMENT_SETTING_PRESETS:
        await _reply(update, "Usage: /set_engagement <community_id> <off|observe|suggest|ready>")
        return

    try:
        await _apply_engagement_preset(update, context, community_id, preset=preset)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def join_community_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /join_community <community_id>")
        return

    try:
        await _start_engagement_join(update, context, community_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def detect_engagement_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /detect_engagement <community_id> [window_minutes]")
        return

    window_minutes = _optional_window_minutes(context)
    if window_minutes is None:
        await _reply(update, "Usage: /detect_engagement <community_id> [window_minutes]")
        return

    try:
        await _start_engagement_detection(update, context, community_id, window_minutes=window_minutes)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def set_engagement_limits_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 3:
        await _reply(
            update,
            "Usage: /set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>",
        )
        return

    community_id = str(context.args[0]).strip()
    if not community_id:
        await _reply(
            update,
            "Usage: /set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>",
        )
        return

    ok_max_posts, max_posts_or_error = _parse_settings_value("max_posts_per_day", str(context.args[1]))
    if not ok_max_posts:
        await _reply(update, str(max_posts_or_error))
        return
    ok_min_minutes, min_minutes_or_error = _parse_settings_value(
        "min_minutes_between_posts",
        str(context.args[2]),
    )
    if not ok_min_minutes:
        await _reply(update, str(min_minutes_or_error))
        return

    try:
        await _update_engagement_settings_from_current(
            update,
            context,
            community_id,
            max_posts_per_day=max_posts_or_error,
            min_minutes_between_posts=min_minutes_or_error,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def set_engagement_quiet_hours_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 3:
        await _reply(
            update,
            "Usage: /set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>",
        )
        return

    community_id = str(context.args[0]).strip()
    if not community_id:
        await _reply(
            update,
            "Usage: /set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>",
        )
        return

    ok_start, start_or_error = _parse_settings_value("quiet_hours_start", str(context.args[1]))
    if not ok_start:
        await _reply(update, str(start_or_error))
        return
    ok_end, end_or_error = _parse_settings_value("quiet_hours_end", str(context.args[2]))
    if not ok_end:
        await _reply(update, str(end_or_error))
        return

    try:
        await _update_engagement_settings_from_current(
            update,
            context,
            community_id,
            quiet_hours_start=start_or_error,
            quiet_hours_end=end_or_error,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def clear_engagement_quiet_hours_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /clear_engagement_quiet_hours <community_id>")
        return

    try:
        await _update_engagement_settings_from_current(
            update,
            context,
            community_id,
            quiet_hours_start=None,
            quiet_hours_end=None,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def assign_engagement_account_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(
            update,
            "Usage: /assign_engagement_account <community_id> <telegram_account_id>",
        )
        return

    community_id = str(context.args[0]).strip()
    if not community_id:
        await _reply(
            update,
            "Usage: /assign_engagement_account <community_id> <telegram_account_id>",
        )
        return

    ok_account, account_id_or_error = _parse_settings_value(
        "assigned_account_id",
        str(context.args[1]),
    )
    if not ok_account:
        await _reply(update, str(account_id_or_error))
        return

    try:
        await _confirm_engagement_account_assignment(
            update,
            context,
            community_id,
            assigned_account_id=account_id_or_error,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def clear_engagement_account_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /clear_engagement_account <community_id>")
        return

    try:
        await _confirm_engagement_account_assignment(
            update,
            context,
            community_id,
            assigned_account_id=None,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_topics_command(update: Any, context: Any) -> None:
    try:
        await _send_engagement_topics(update, context, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_topic_command(update: Any, context: Any) -> None:
    topic_id = _first_arg(context)
    if topic_id is None:
        await _reply(update, "Usage: /engagement_topic <topic_id>")
        return
    try:
        await _send_engagement_topic(update, context, topic_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def create_engagement_topic_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    parsed = _parse_create_engagement_topic_args(context)
    if parsed is None:
        await _reply(update, _create_engagement_topic_usage())
        return

    name, guidance, keywords = parsed
    client = _api_client(context)
    try:
        data = await client.create_engagement_topic(
            name=name,
            stance_guidance=guidance,
            trigger_keywords=keywords,
            active=True,
            operator_user_id=_telegram_user_id(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    topic_id = str(data.get("id", "unknown"))
    await _reply(
        update,
        "Engagement topic created.\n\n" + format_engagement_topic_card(data, detail=True),
        reply_markup=engagement_topic_actions_markup(topic_id, active=bool(data.get("active"))),
    )


async def toggle_engagement_topic_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 2:
        await _reply(update, "Usage: /toggle_engagement_topic <topic_id> <on|off>")
        return

    topic_id = str(context.args[0]).strip()
    active = _parse_on_off(str(context.args[1]))
    if not topic_id or active is None:
        await _reply(update, "Usage: /toggle_engagement_topic <topic_id> <on|off>")
        return

    try:
        await _toggle_engagement_topic(update, context, topic_id, active=active)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def topic_good_reply_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    await _topic_example_command(update, context, example_type="good")


async def topic_bad_reply_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    await _topic_example_command(update, context, example_type="bad")


async def topic_remove_example_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 3:
        await _reply(update, "Usage: /topic_remove_example <topic_id> <good|bad> <index>")
        return
    topic_id = str(context.args[0]).strip()
    example_type = str(context.args[1]).strip().casefold()
    if example_type not in {"good", "bad"}:
        await _reply(update, "Usage: /topic_remove_example <topic_id> <good|bad> <index>")
        return
    try:
        operator_index = int(str(context.args[2]).strip())
    except ValueError:
        operator_index = 0
    if not topic_id or operator_index <= 0:
        await _reply(update, "Usage: /topic_remove_example <topic_id> <good|bad> <index>")
        return
    try:
        await _remove_topic_example(
            update,
            context,
            topic_id,
            example_type=example_type,
            index=operator_index - 1,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def topic_keywords_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 3:
        await _reply(update, "Usage: /topic_keywords <topic_id> <trigger|negative> <comma_keywords>")
        return
    topic_id = str(context.args[0]).strip()
    keyword_type = str(context.args[1]).strip().casefold()
    field = TOPIC_KEYWORD_FIELDS.get(keyword_type)
    raw_keywords = " ".join(str(arg) for arg in context.args[2:]).strip()
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    if not topic_id or field is None:
        await _reply(update, "Usage: /topic_keywords <topic_id> <trigger|negative> <comma_keywords>")
        return
    try:
        await _update_topic_keywords(update, context, topic_id, field=field, keywords=keywords)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def edit_topic_guidance_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    topic_id = _first_arg(context)
    if topic_id is None:
        await _reply(update, "Usage: /edit_topic_guidance <topic_id>")
        return
    await _start_config_edit(update, context, entity="topic", object_id=topic_id, field="stance_guidance")


__all__ = [
    "engagement_prompts_command",
    "engagement_prompt_command",
    "engagement_prompt_versions_command",
    "engagement_prompt_preview_command",
    "create_engagement_prompt_command",
    "activate_engagement_prompt_command",
    "duplicate_engagement_prompt_command",
    "edit_engagement_prompt_command",
    "rollback_engagement_prompt_command",
    "engagement_style_command",
    "engagement_style_rule_command",
    "create_style_rule_command",
    "edit_style_rule_command",
    "toggle_style_rule_command",
    "engagement_settings_command",
    "set_engagement_command",
    "join_community_command",
    "detect_engagement_command",
    "set_engagement_limits_command",
    "set_engagement_quiet_hours_command",
    "clear_engagement_quiet_hours_command",
    "assign_engagement_account_command",
    "clear_engagement_account_command",
    "engagement_topics_command",
    "engagement_topic_command",
    "create_engagement_topic_command",
    "toggle_engagement_topic_command",
    "topic_good_reply_command",
    "topic_bad_reply_command",
    "topic_remove_example_command",
    "topic_keywords_command",
    "edit_topic_guidance_command",
]
