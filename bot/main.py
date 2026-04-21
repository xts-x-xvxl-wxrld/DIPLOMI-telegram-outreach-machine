from __future__ import annotations

import csv
import io
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
    format_engagement_semantic_rollout,
    format_engagement_style_rule_card,
    format_engagement_style_rules,
    format_engagement_target_card,
    format_engagement_target_mutation,
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
    ACTION_ENGAGEMENT_TARGET_ARCHIVE,
    ACTION_ENGAGEMENT_TARGET_DETECT,
    ACTION_ENGAGEMENT_TARGET_JOIN,
    ACTION_ENGAGEMENT_TARGET_OPEN,
    ACTION_ENGAGEMENT_TARGET_PERMISSION,
    ACTION_ENGAGEMENT_TARGET_REJECT,
    ACTION_ENGAGEMENT_TARGET_RESOLVE,
    ACTION_ENGAGEMENT_TARGETS,
    ACTION_ENGAGEMENT_TOPIC_EDIT,
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
    discovery_seeds_markup,
    engagement_action_pager_markup,
    engagement_admin_advanced_markup,
    engagement_admin_home_markup,
    engagement_admin_limits_markup,
    engagement_admin_pager_markup,
    engagement_candidate_actions_markup,
    engagement_candidate_detail_markup,
    engagement_candidate_filter_markup,
    engagement_candidate_pager_markup,
    engagement_candidate_revisions_markup,
    engagement_candidate_send_markup,
    engagement_home_markup,
    engagement_prompt_actions_markup,
    engagement_prompt_activation_confirm_markup,
    engagement_prompt_rollback_confirm_markup,
    engagement_prompt_versions_markup,
    engagement_job_markup,
    engagement_settings_markup,
    engagement_style_list_markup,
    engagement_style_rule_actions_markup,
    engagement_target_actions_markup,
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
ENGAGEMENT_TARGET_PERMISSIONS = {"join": "allow_join", "detect": "allow_detect", "post": "allow_post"}
ENGAGEMENT_TARGET_PERMISSION_ALIASES = {"j": "join", "d": "detect", "p": "post"}
ENGAGEMENT_SETTING_PRESETS = {"off", "observe", "suggest", "ready"}
ENGAGEMENT_ADMIN_ONLY_MESSAGE = (
    "This engagement admin control is limited to admin operators."
)


async def start_command(update: Any, context: Any) -> None:
    await _reply(update, "Opening the operator cockpit.", reply_markup=reply_keyboard_remove())
    await _reply(update, format_operator_cockpit(), reply_markup=operator_cockpit_markup())


async def help_command(update: Any, context: Any) -> None:
    await _send_help(update)


async def whoami_command(update: Any, context: Any) -> None:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    if user_id is None:
        await _reply(update, "Telegram did not include a user ID on this update.")
        return

    await _reply(update, format_whoami(user_id, username=_telegram_username(user)))


async def briefs_command(update: Any, context: Any) -> None:
    await _reply(update, format_briefs_unavailable())


async def brief_command(update: Any, context: Any) -> None:
    raw_input = " ".join(context.args).strip()
    if not raw_input:
        await _reply(update, "Usage: /brief <audience description>")
        return

    client = _api_client(context)
    try:
        data = await client.create_brief(raw_input)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_created_brief(data))


async def job_command(update: Any, context: Any) -> None:
    job_id = _first_arg(context)
    if job_id is None:
        await _reply(update, "Usage: /job <job_id>")
        return

    await _send_job_status(update, context, job_id)


async def entity_command(update: Any, context: Any) -> None:
    intake_id = _first_arg(context)
    if intake_id is None:
        await _reply(update, "Usage: /entity <intake_id>")
        return

    client = _api_client(context)
    try:
        data = await client.get_telegram_entity(intake_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_telegram_entity_intake(data))


async def candidates_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /candidates <seed_group_id>")
        return

    await _send_seed_group_candidates(update, context, seed_group_id, offset=0)


async def approve_command(update: Any, context: Any) -> None:
    await _review(update, context, decision="approve")


async def reject_command(update: Any, context: Any) -> None:
    await _review(update, context, decision="reject")


async def accounts_command(update: Any, context: Any) -> None:
    try:
        await _send_accounts(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def seeds_command(update: Any, context: Any) -> None:
    try:
        await _send_seed_groups(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def seed_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /seed <seed_group_id>")
        return

    await _send_seed_group_detail(update, context, seed_group_id)


async def channels_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /channels <seed_group_id>")
        return

    await _send_seed_group_channels(update, context, seed_group_id, offset=0)


async def resolveseeds_command(update: Any, context: Any) -> None:
    seed_group_id = _first_arg(context)
    if seed_group_id is None:
        await _reply(update, "Usage: /resolveseeds <seed_group_id>")
        return

    await _start_seed_group_resolution(update, context, seed_group_id)


async def community_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /community <community_id>")
        return

    await _send_community_detail(update, context, community_id)


async def snapshot_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /snapshot <community_id>")
        return

    await _start_snapshot(update, context, community_id)


async def members_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /members <community_id>")
        return

    await _send_community_members(update, context, community_id, offset=_second_arg_as_offset(context))


async def exportmembers_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, "Usage: /exportmembers <community_id>")
        return

    client = _api_client(context)
    try:
        detail = await client.get_community(community_id)
        export_data = await _fetch_all_community_members(client, community_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    community = detail.get("community") or {}
    title = community.get("title") or community.get("username") or community_id
    csv_bytes = _members_csv_bytes(export_data.get("items") or [])
    file_name = f"community-{community_id}-members.csv"
    await _reply_document(
        update,
        document_bytes=csv_bytes,
        file_name=file_name,
        caption=format_member_export(export_data, community_title=title),
    )


async def engagement_candidates_command(update: Any, context: Any) -> None:
    status = _engagement_candidate_status_arg(context)
    try:
        await _send_engagement_candidates(update, context, status=status, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_candidate_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /engagement_candidate <candidate_id>")
        return
    try:
        await _send_engagement_candidate_detail(update, context, candidate_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_command(update: Any, context: Any) -> None:
    try:
        await _send_engagement_home(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_admin_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    try:
        await _send_engagement_admin(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_targets_command(update: Any, context: Any) -> None:
    try:
        await _send_engagement_targets(
            update,
            context,
            status=_engagement_target_status_arg(context),
            offset=0,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_target_command(update: Any, context: Any) -> None:
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /engagement_target <target_id>")
        return
    try:
        await _send_engagement_target(update, context, target_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def add_engagement_target_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    target_ref = _first_arg(context)
    if target_ref is None:
        await _reply(update, "Usage: /add_engagement_target <telegram_link_or_username_or_community_id>")
        return
    client = _api_client(context)
    try:
        data = await client.create_engagement_target(
            target_ref=target_ref,
            added_by=_reviewer_label(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(
        update,
        "Engagement target added.\n\n" + format_engagement_target_card(data),
        reply_markup=engagement_target_actions_markup(
            str(data.get("id", "unknown")),
            status=str(data.get("status") or "pending"),
        ),
    )


async def approve_engagement_target_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /approve_engagement_target <target_id>")
        return
    try:
        await _approve_engagement_target(update, context, target_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def resolve_engagement_target_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /resolve_engagement_target <target_id>")
        return
    try:
        await _resolve_engagement_target(update, context, target_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def reject_engagement_target_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /reject_engagement_target <target_id>")
        return
    try:
        await _set_engagement_target_status(update, context, target_id, status="rejected")
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def archive_engagement_target_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /archive_engagement_target <target_id>")
        return
    try:
        await _set_engagement_target_status(update, context, target_id, status="archived")
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def target_permission_command(update: Any, context: Any) -> None:
    if not await _require_engagement_admin(update, context):
        return
    if len(context.args) < 3:
        await _reply(update, "Usage: /target_permission <target_id> <join|detect|post> <on|off>")
        return

    target_id = str(context.args[0]).strip()
    permission = _normalize_target_permission(str(context.args[1]))
    enabled = _parse_on_off(str(context.args[2]))
    if not target_id or permission is None or enabled is None:
        await _reply(update, "Usage: /target_permission <target_id> <join|detect|post> <on|off>")
        return
    try:
        await _set_engagement_target_permission(
            update,
            context,
            target_id,
            permission=permission,
            enabled=enabled,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def target_join_command(update: Any, context: Any) -> None:
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /target_join <target_id>")
        return
    try:
        await _start_engagement_target_join(update, context, target_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def target_detect_command(update: Any, context: Any) -> None:
    target_id = _first_arg(context)
    if target_id is None:
        await _reply(update, "Usage: /target_detect <target_id> [window_minutes]")
        return
    window_minutes = _optional_window_minutes(context)
    if window_minutes is None:
        await _reply(update, "Usage: /target_detect <target_id> [window_minutes]")
        return
    try:
        await _start_engagement_target_detection(
            update,
            context,
            target_id,
            window_minutes=window_minutes,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


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
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(
        update,
        "Prompt profile duplicated.\n\n" + format_engagement_prompt_profile_card(data),
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
        await _reply(
            update,
            "Usage: /create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>",
        )
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
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    rule_id = str(data.get("id", "unknown"))
    await _reply(
        update,
        "Style rule created.\n\n" + format_engagement_style_rule_card(data),
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
        await _update_engagement_settings_from_current(
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
        await _update_engagement_settings_from_current(
            update,
            context,
            community_id,
            assigned_account_id=None,
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_actions_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    try:
        await _send_engagement_actions(update, context, community_id=community_id, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_rollout_command(update: Any, context: Any) -> None:
    window_days = _positive_int_arg(context, default=14)
    client = _api_client(context)
    try:
        data = await client.get_engagement_semantic_rollout(window_days=window_days)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(update, format_engagement_semantic_rollout(data))


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
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    topic_id = str(data.get("id", "unknown"))
    await _reply(
        update,
        "Engagement topic created.\n\n" + format_engagement_topic_card(data),
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


async def approve_reply_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /approve_reply <candidate_id>")
        return

    try:
        await _review_engagement_candidate(
            update,
            context,
            candidate_id,
            action="approve",
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def reject_reply_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /reject_reply <candidate_id>")
        return

    try:
        await _review_engagement_candidate(
            update,
            context,
            candidate_id,
            action="reject",
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def send_reply_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /send_reply <candidate_id>")
        return

    try:
        await _send_engagement_reply(update, context, candidate_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def candidate_revisions_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /candidate_revisions <candidate_id>")
        return
    try:
        await _send_engagement_candidate_revisions(update, context, candidate_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def expire_candidate_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /expire_candidate <candidate_id>")
        return
    try:
        await _expire_engagement_candidate(update, context, candidate_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def retry_candidate_command(update: Any, context: Any) -> None:
    candidate_id = _first_arg(context)
    if candidate_id is None:
        await _reply(update, "Usage: /retry_candidate <candidate_id>")
        return
    try:
        await _retry_engagement_candidate(update, context, candidate_id)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def edit_reply_command(update: Any, context: Any) -> None:
    parsed = _parse_edit_reply_args(context)
    if parsed is None and len(context.args) == 1:
        await _start_config_edit(
            update,
            context,
            entity="candidate",
            object_id=str(context.args[0]).strip(),
            field="final_reply",
        )
        return
    if parsed is None:
        await _reply(
            update,
            "Usage: /edit_reply <candidate_id> | <new final reply>\n"
            "Or start a guided edit with: /edit_reply <candidate_id>",
        )
        return
    candidate_id, final_reply = parsed
    client = _api_client(context)
    try:
        data = await client.edit_engagement_candidate(
            candidate_id,
            final_reply=final_reply,
            edited_by=_reviewer_label(update),
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(
        update,
        "Reply edited.\n\n" + format_engagement_candidate_card(data),
        reply_markup=_engagement_candidate_detail_markup(candidate_id, data),
    )


async def cancel_edit_command(update: Any, context: Any) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).cancel(operator_id)
    await _reply(update, render_edit_cancelled(pending))


async def seed_csv_document(update: Any, context: Any) -> None:
    if update.message is None or update.message.document is None:
        return

    document = update.message.document
    file_name = document.file_name or "seeds.csv"
    if not file_name.lower().endswith(".csv"):
        await _reply(update, "Please upload a .csv file with group_name,channel columns.")
        return

    try:
        telegram_file = await document.get_file()
        data = await telegram_file.download_as_bytearray()
        csv_text = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError:
        await _reply(update, "Could not read the CSV. Please upload UTF-8 text.")
        return

    client = _api_client(context)
    try:
        response = await client.import_seed_csv(csv_text, file_name=file_name)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    await _reply(update, format_seed_import(response))
    for group in (response.get("groups") or [])[:5]:
        await _reply(
            update,
            format_seed_group_card(group),
            reply_markup=seed_group_actions_markup(str(group.get("id", "unknown"))),
        )


async def telegram_entity_text(update: Any, context: Any) -> None:
    if update.message is None or update.message.text is None:
        return

    raw_text = update.message.text.strip()
    if await _handle_config_edit_text(update, context, raw_text):
        return

    if not _looks_like_telegram_reference(raw_text):
        return

    client = _api_client(context)
    try:
        response = await client.submit_telegram_entity(raw_text)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    job_id = str((response.get("job") or {}).get("id", "unknown"))
    await _reply(
        update,
        format_telegram_entity_submission(response),
        reply_markup=job_actions_markup(job_id),
    )


async def callback_query(update: Any, context: Any) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    await query.answer()
    action, parts = parse_callback_data(query.data)

    if _callback_action_requires_engagement_admin(action, parts) and not _is_engagement_admin(
        update, context
    ):
        await _callback_reply(update, ENGAGEMENT_ADMIN_ONLY_MESSAGE)
        return

    try:
        if action == ACTION_OPEN_SEED_GROUP and len(parts) == 1:
            await _send_seed_group_detail(update, context, parts[0])
            return
        if action == ACTION_RESOLVE_SEED_GROUP and len(parts) == 1:
            await _start_seed_group_resolution(update, context, parts[0])
            return
        if action == ACTION_SEED_CHANNELS and len(parts) == 2:
            await _send_seed_group_channels(
                update,
                context,
                parts[0],
                offset=_parse_offset(parts[1]),
            )
            return
        if action == ACTION_SEED_CANDIDATES and len(parts) == 2:
            await _send_seed_group_candidates(
                update,
                context,
                parts[0],
                offset=_parse_offset(parts[1]),
            )
            return
        if action == ACTION_OPEN_COMMUNITY and len(parts) == 1:
            await _send_community_detail(update, context, parts[0])
            return
        if action == ACTION_SNAPSHOT_COMMUNITY and len(parts) == 1:
            await _start_snapshot(update, context, parts[0])
            return
        if action == ACTION_COMMUNITY_MEMBERS and len(parts) == 2:
            await _send_community_members(
                update,
                context,
                parts[0],
                offset=_parse_offset(parts[1]),
            )
            return
        if action == ACTION_JOB_STATUS and len(parts) == 1:
            await _send_job_status(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_HOME:
            await _send_engagement_home(update, context)
            return
        if action == ACTION_ENGAGEMENT_ADMIN:
            await _send_engagement_admin(update, context)
            return
        if action == ACTION_ENGAGEMENT_ADMIN_LIMITS:
            await _send_engagement_admin_limits(update)
            return
        if action == ACTION_ENGAGEMENT_ADMIN_ADVANCED:
            await _send_engagement_admin_advanced(update)
            return
        if action == ACTION_CONFIG_EDIT_SAVE:
            await _save_config_edit_callback(update, context)
            return
        if action == ACTION_CONFIG_EDIT_CANCEL:
            await _cancel_config_edit_callback(update, context)
            return
        if action == ACTION_ENGAGEMENT_TARGETS and parts:
            status, offset = _engagement_target_callback_status_and_offset(parts)
            await _send_engagement_targets(update, context, status=status, offset=offset)
            return
        if action == ACTION_ENGAGEMENT_TARGET_ADD:
            await _callback_reply(
                update,
                "Add an engagement community with:\n/add_engagement_target <telegram_link_or_username_or_community_id>",
            )
            return
        if action == ACTION_ENGAGEMENT_TARGET_OPEN and len(parts) == 1:
            await _send_engagement_target(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_RESOLVE and len(parts) == 1:
            await _resolve_engagement_target(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_APPROVE and len(parts) == 1:
            await _approve_engagement_target(update, context, parts[0], edit_callback=True)
            return
        if action == ACTION_ENGAGEMENT_TARGET_REJECT and len(parts) == 1:
            await _set_engagement_target_status(
                update,
                context,
                parts[0],
                status="rejected",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_TARGET_ARCHIVE and len(parts) == 1:
            await _set_engagement_target_status(
                update,
                context,
                parts[0],
                status="archived",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_TARGET_PERMISSION and len(parts) == 3:
            permission = _normalize_target_permission(parts[1])
            enabled = _parse_callback_bool(parts[2])
            if permission is not None and enabled is not None:
                await _set_engagement_target_permission(
                    update,
                    context,
                    parts[0],
                    permission=permission,
                    enabled=enabled,
                    edit_callback=True,
                )
                return
        if action == ACTION_ENGAGEMENT_TARGET_JOIN and len(parts) == 1:
            await _start_engagement_target_join(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_DETECT and len(parts) == 2:
            await _start_engagement_target_detection(
                update,
                context,
                parts[0],
                window_minutes=_parse_positive_int(parts[1], default=60),
            )
            return
        if action == ACTION_ENGAGEMENT_PROMPTS and parts:
            await _send_engagement_prompts(update, context, offset=_parse_offset(parts[0]))
            return
        if action == ACTION_ENGAGEMENT_PROMPT_OPEN and len(parts) == 1:
            await _send_engagement_prompt_detail(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_PROMPT_PREVIEW and len(parts) == 1:
            await _send_engagement_prompt_preview(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_PROMPT_VERSIONS and len(parts) == 1:
            await _send_engagement_prompt_versions(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_PROMPT_EDIT and len(parts) == 2:
            field = _normalize_prompt_profile_edit_field(parts[1])
            if field is not None:
                await _start_config_edit(
                    update,
                    context,
                    entity="prompt_profile",
                    object_id=parts[0],
                    field=field,
                )
                return
        if action == ACTION_ENGAGEMENT_PROMPT_DUPLICATE and len(parts) == 1:
            await _duplicate_engagement_prompt_default(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_PROMPT_ACTIVATE and len(parts) == 1:
            await _confirm_engagement_prompt_activation(
                update,
                context,
                parts[0],
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM and len(parts) == 1:
            await _activate_engagement_prompt(update, context, parts[0], edit_callback=True)
            return
        if action == ACTION_ENGAGEMENT_PROMPT_ROLLBACK and len(parts) == 2:
            await _confirm_engagement_prompt_rollback(
                update,
                context,
                parts[0],
                _parse_positive_int(parts[1], default=0),
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_PROMPT_ROLLBACK_CONFIRM and len(parts) == 2:
            await _rollback_engagement_prompt(
                update,
                context,
                parts[0],
                _parse_positive_int(parts[1], default=0),
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_STYLE and parts:
            scope_type, scope_id, offset = _parse_style_callback_parts(parts)
            await _send_engagement_style_rules(
                update,
                context,
                scope_type=scope_type,
                scope_id=scope_id,
                offset=offset,
            )
            return
        if action == ACTION_ENGAGEMENT_STYLE_CREATE:
            await _callback_reply(
                update,
                "Create a rule with /create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>",
            )
            return
        if action == ACTION_ENGAGEMENT_STYLE_OPEN and len(parts) == 1:
            await _send_engagement_style_rule(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_STYLE_EDIT and len(parts) == 1:
            await _start_config_edit(
                update,
                context,
                entity="style_rule",
                object_id=parts[0],
                field="rule_text",
            )
            return
        if action == ACTION_ENGAGEMENT_STYLE_TOGGLE and len(parts) == 2:
            await _toggle_style_rule(
                update,
                context,
                parts[0],
                active=parts[1] == "1",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_CANDIDATES and parts:
            status, offset = _engagement_callback_status_and_offset(parts)
            await _send_engagement_candidates(update, context, status=status, offset=offset)
            return
        if action == ACTION_ENGAGEMENT_SETTINGS_OPEN and len(parts) == 1:
            await _send_engagement_settings(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_SETTINGS_PRESET and len(parts) == 2:
            preset = parts[1] if parts[1] in ENGAGEMENT_SETTING_PRESETS else "off"
            await _apply_engagement_preset(
                update,
                context,
                parts[0],
                preset=preset,
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_SETTINGS_JOIN and len(parts) == 2:
            await _toggle_engagement_setting(
                update,
                context,
                parts[0],
                field="allow_join",
                value=parts[1] == "1",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_SETTINGS_POST and len(parts) == 2:
            await _toggle_engagement_setting(
                update,
                context,
                parts[0],
                field="allow_post",
                value=parts[1] == "1",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_JOIN and len(parts) == 1:
            await _start_engagement_join(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_DETECT and len(parts) == 2:
            await _start_engagement_detection(
                update,
                context,
                parts[0],
                window_minutes=max(_parse_offset(parts[1]), 1),
            )
            return
        if action == ACTION_ENGAGEMENT_ACTIONS and parts:
            community_id, offset = _engagement_actions_filter_and_offset(parts)
            await _send_engagement_actions(
                update,
                context,
                community_id=community_id,
                offset=offset,
            )
            return
        if action == ACTION_ENGAGEMENT_TOPIC_LIST and parts:
            await _send_engagement_topics(update, context, offset=_parse_offset(parts[0]))
            return
        if action == ACTION_ENGAGEMENT_TOPIC_OPEN and len(parts) == 1:
            await _send_engagement_topic(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TOPIC_EDIT and len(parts) == 2:
            field = parts[1]
            if field not in {"stance_guidance", "trigger_keywords", "negative_keywords"}:
                await _callback_reply(update, "That topic field is not editable from this button.")
                return
            await _start_config_edit(
                update,
                context,
                entity="topic",
                object_id=parts[0],
                field=field,
            )
            return
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
            return
        if action == ACTION_ENGAGEMENT_TOPIC_TOGGLE and len(parts) == 2:
            await _toggle_engagement_topic(
                update,
                context,
                parts[0],
                active=parts[1] == "1",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_CANDIDATE_OPEN and len(parts) == 1:
            await _send_engagement_candidate_detail(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_CANDIDATE_EDIT and len(parts) == 1:
            await _start_config_edit(
                update,
                context,
                entity="candidate",
                object_id=parts[0],
                field="final_reply",
            )
            return
        if action == ACTION_ENGAGEMENT_CANDIDATE_REVISIONS and len(parts) == 1:
            await _send_engagement_candidate_revisions(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_CANDIDATE_EXPIRE and len(parts) == 1:
            await _expire_engagement_candidate(
                update,
                context,
                parts[0],
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_CANDIDATE_RETRY and len(parts) == 1:
            await _retry_engagement_candidate(
                update,
                context,
                parts[0],
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_APPROVE and len(parts) == 1:
            await _review_engagement_candidate(
                update,
                context,
                parts[0],
                action="approve",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_REJECT and len(parts) == 1:
            await _review_engagement_candidate(
                update,
                context,
                parts[0],
                action="reject",
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_SEND and len(parts) == 1:
            await _send_engagement_reply(update, context, parts[0])
            return
        if action in {ACTION_APPROVE_COMMUNITY, ACTION_REJECT_COMMUNITY} and len(parts) == 1:
            decision = "approve" if action == ACTION_APPROVE_COMMUNITY else "reject"
            await _review_callback(update, context, parts[0], decision=decision)
            return
        if action == ACTION_OP_HOME:
            await _send_operator_cockpit(update)
            return
        if action in {ACTION_OP_DISCOVERY, ACTION_DISC_HOME}:
            await _send_discovery_cockpit(update)
            return
        if action == ACTION_OP_ACCOUNTS:
            await _send_accounts(update, context)
            return
        if action == ACTION_OP_HELP:
            await _send_help(update)
            return
        if action in {ACTION_DISC_ALL, ACTION_DISC_ATTENTION, ACTION_DISC_WATCHING}:
            await _send_seed_groups(update, context)
            return
        if action == ACTION_DISC_REVIEW:
            await _send_seed_groups(update, context)
            return
        if action == ACTION_DISC_START:
            await _callback_reply(
                update,
                "Start search\n\n"
                "Upload a CSV with group_name,channel columns.\n"
                "Or send @username or a public t.me link directly.",
                reply_markup=discovery_cockpit_markup(),
            )
            return
        if action == ACTION_DISC_ACTIVITY:
            await _callback_reply(
                update,
                "Recent activity\n\n"
                "Check background jobs with /job <job_id>.\n"
                "Seed resolution, snapshots, and expansion jobs appear here when available.",
                reply_markup=discovery_cockpit_markup(),
            )
            return
        if action == ACTION_DISC_HELP:
            await _callback_reply(
                update,
                format_discovery_help(),
                reply_markup=discovery_cockpit_markup(),
            )
            return
    except BotApiError as exc:
        await _callback_reply(update, format_api_error(exc.message))
        return

    await _callback_reply(update, "That action is no longer available. Try /seeds or /community.")


async def access_gate(update: Any, context: Any) -> None:
    settings: BotSettings = context.application.bot_data["settings"]
    if _is_identity_command(update) or _is_authorized_update(update, settings):
        _clear_pending_edit_if_command(update, context)
        return

    await _deny_access(update)
    from telegram.ext import ApplicationHandlerStop

    raise ApplicationHandlerStop


async def _review(update: Any, context: Any, *, decision: str) -> None:
    community_id = _first_arg(context)
    if community_id is None:
        await _reply(update, f"Usage: /{decision} <community_id>")
        return

    client = _api_client(context)
    try:
        data = await client.review_community(community_id, decision=decision)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return

    job = data.get("job") or {}
    await _reply(
        update,
        format_review(decision, data),
        reply_markup=review_result_markup(
            str((data.get("community") or {}).get("id", community_id)),
            str(job.get("id")) if job.get("id") else None,
        ),
    )


async def _review_callback(update: Any, context: Any, community_id: str, *, decision: str) -> None:
    client = _api_client(context)
    data = await client.review_community(community_id, decision=decision)
    job = data.get("job") or {}
    await _edit_callback_message(
        update,
        format_review(decision, data),
        reply_markup=review_result_markup(
            str((data.get("community") or {}).get("id", community_id)),
            str(job.get("id")) if job.get("id") else None,
        ),
    )


async def _send_seed_group_detail(update: Any, context: Any, seed_group_id: str) -> None:
    client = _api_client(context)
    data = await client.get_seed_group(seed_group_id)
    await _callback_reply(
        update,
        format_seed_group(data),
        reply_markup=seed_group_actions_markup(seed_group_id),
    )


async def _send_seed_group_channels(
    update: Any,
    context: Any,
    seed_group_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    group = await client.get_seed_group(seed_group_id)
    data = await client.list_seed_group_channels(seed_group_id)
    await _callback_reply(
        update,
        format_seed_channels(
            data,
            group_name=(group.get("group") or {}).get("name"),
            offset=offset,
            page_size=CHANNEL_PAGE_SIZE,
        ),
        reply_markup=seed_group_pager_markup(
            seed_group_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=CHANNEL_PAGE_SIZE,
            action=ACTION_SEED_CHANNELS,
        ),
    )


async def _send_seed_group_candidates(
    update: Any,
    context: Any,
    seed_group_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    group = await client.get_seed_group(seed_group_id)
    data = await client.list_seed_group_candidates(
        seed_group_id,
        limit=CANDIDATE_PAGE_SIZE,
        offset=offset,
    )
    group_name = (group.get("group") or {}).get("name")
    await _callback_reply(
        update,
        format_candidates(data, seed_group_name=group_name, offset=offset),
        reply_markup=seed_group_pager_markup(
            seed_group_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=CANDIDATE_PAGE_SIZE,
            action=ACTION_SEED_CANDIDATES,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        community_id = str((_candidate_community(item)).get("id", "unknown"))
        await _callback_reply(
            update,
            format_candidate_card(item, index=index),
            reply_markup=candidate_actions_markup(community_id),
        )


async def _send_community_detail(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    detail = await client.get_community(community_id)
    snapshot_runs = await client.list_snapshot_runs(community_id)
    await _callback_reply(
        update,
        format_community_detail(detail, snapshot_runs),
        reply_markup=community_actions_markup(community_id),
    )


async def _send_community_members(
    update: Any,
    context: Any,
    community_id: str,
    *,
    offset: int,
) -> None:
    client = _api_client(context)
    detail = await client.get_community(community_id)
    data = await client.list_community_members(
        community_id,
        limit=MEMBER_PAGE_SIZE,
        offset=offset,
    )
    community = detail.get("community") or {}
    title = community.get("title") or community.get("username") or community_id
    await _callback_reply(
        update,
        format_members(data, community_title=title, offset=offset),
        reply_markup=member_pager_markup(
            community_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=MEMBER_PAGE_SIZE,
        ),
    )


async def _send_operator_cockpit(update: Any) -> None:
    await _callback_reply(update, format_operator_cockpit(), reply_markup=operator_cockpit_markup())


async def _send_discovery_cockpit(update: Any) -> None:
    await _callback_reply(update, format_discovery_cockpit(), reply_markup=discovery_cockpit_markup())


async def _send_accounts(update: Any, context: Any) -> None:
    client = _api_client(context)
    data = await client.get_accounts()
    await _callback_reply(update, format_accounts(data), reply_markup=operator_cockpit_markup())


async def _send_seed_groups(update: Any, context: Any) -> None:
    client = _api_client(context)
    data = await client.list_seed_groups()
    await _callback_reply(update, format_seed_groups(data), reply_markup=discovery_seeds_markup())
    for group in (data.get("items") or [])[:10]:
        await _callback_reply(
            update,
            format_seed_group_card(group),
            reply_markup=seed_group_actions_markup(str(group.get("id", "unknown"))),
        )
    remaining = max((data.get("total", 0) or 0) - 10, 0)
    if remaining:
        await _callback_reply(
            update,
            f"...and {remaining} more seed groups. Open one with /seed <seed_group_id>.",
        )


async def _send_help(update: Any) -> None:
    await _callback_reply(update, format_help(), reply_markup=operator_cockpit_markup())


async def _send_engagement_home(update: Any, context: Any) -> None:
    client = _api_client(context)
    pending = await client.list_engagement_candidates(
        status="needs_review",
        limit=1,
        offset=0,
    )
    approved = await client.list_engagement_candidates(
        status="approved",
        limit=1,
        offset=0,
    )
    failed = await client.list_engagement_candidates(
        status="failed",
        limit=1,
        offset=0,
    )
    topics = await client.list_engagement_topics()
    active_topic_count = sum(1 for topic in topics.get("items") or [] if topic.get("active"))
    data = {
        "pending_reply_count": pending.get("total", 0),
        "approved_reply_count": approved.get("total", 0),
        "failed_candidate_count": failed.get("total", 0),
        "active_topic_count": active_topic_count,
    }
    await _callback_reply(
        update,
        format_engagement_home(data),
        reply_markup=engagement_home_markup(show_admin=_is_engagement_admin(update, context)),
    )


async def _send_engagement_admin(update: Any, context: Any) -> None:
    client = _api_client(context)
    targets = await client.list_engagement_targets(limit=1, offset=0)
    prompts = await client.list_engagement_prompt_profiles(limit=1, offset=0)
    styles = await client.list_engagement_style_rules(limit=1, offset=0)
    topics = await client.list_engagement_topics()
    topic_items = topics.get("items") or []
    data = {
        "target_count": targets.get("total", 0),
        "prompt_profile_count": prompts.get("total", 0),
        "style_rule_count": styles.get("total", 0),
        "topic_count": topics.get("total", len(topic_items)),
        "active_topic_count": sum(1 for item in topic_items if item.get("active")),
    }
    await _callback_reply(
        update,
        format_engagement_admin_home(data),
        reply_markup=engagement_admin_home_markup(),
    )


async def _send_engagement_admin_limits(update: Any) -> None:
    await _callback_reply(
        update,
        format_engagement_admin_limits_home(),
        reply_markup=engagement_admin_limits_markup(),
    )


async def _send_engagement_admin_advanced(update: Any) -> None:
    await _callback_reply(
        update,
        format_engagement_admin_advanced_home(),
        reply_markup=engagement_admin_advanced_markup(),
    )


async def _send_engagement_targets(
    update: Any,
    context: Any,
    *,
    status: str | None = None,
    offset: int,
) -> None:
    client = _api_client(context)
    can_manage = _is_engagement_admin(update, context)
    data = await client.list_engagement_targets(
        status=status,
        limit=ENGAGEMENT_ADMIN_PAGE_SIZE,
        offset=offset,
    )
    data = {**data, "status": status}
    await _callback_reply(
        update,
        format_engagement_targets(data, offset=offset),
        reply_markup=engagement_target_list_markup(
            status=status,
            offset=offset,
            total=data.get("total", 0),
            page_size=ENGAGEMENT_ADMIN_PAGE_SIZE,
            can_manage=can_manage,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        await _callback_reply(
            update,
            format_engagement_target_card(item, index=index),
            reply_markup=engagement_target_actions_markup(
                str(item.get("id", "unknown")),
                status=str(item.get("status") or "pending"),
                allow_join=bool(item.get("allow_join")),
                allow_detect=bool(item.get("allow_detect")),
                allow_post=bool(item.get("allow_post")),
                can_manage=can_manage,
            ),
        )


async def _send_engagement_target(update: Any, context: Any, target_id: str) -> None:
    client = _api_client(context)
    data = await client.get_engagement_target(target_id)
    await _callback_reply(
        update,
        format_engagement_target_card(data),
        reply_markup=_engagement_target_markup(
            target_id,
            data,
            can_manage=_is_engagement_admin(update, context),
        ),
    )


async def _approve_engagement_target(
    update: Any,
    context: Any,
    target_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    before = await client.get_engagement_target(target_id)
    data = await client.update_engagement_target(
        target_id,
        status="approved",
        allow_join=True,
        allow_detect=True,
        allow_post=True,
        updated_by=_reviewer_label(update),
    )
    message = format_engagement_target_mutation(action="approved", before=before, after=data)
    markup = _engagement_target_markup(target_id, data)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _set_engagement_target_status(
    update: Any,
    context: Any,
    target_id: str,
    *,
    status: str,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    before = await client.get_engagement_target(target_id)
    data = await client.update_engagement_target(
        target_id,
        status=status,
        updated_by=_reviewer_label(update),
    )
    message = format_engagement_target_mutation(action=status, before=before, after=data)
    markup = _engagement_target_markup(target_id, data)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _set_engagement_target_permission(
    update: Any,
    context: Any,
    target_id: str,
    *,
    permission: str,
    enabled: bool,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    before = await client.get_engagement_target(target_id)
    field_name = ENGAGEMENT_TARGET_PERMISSIONS[permission]
    data = await client.update_engagement_target(
        target_id,
        **{field_name: enabled, "updated_by": _reviewer_label(update)},
    )
    action = f"{permission} {'enabled' if enabled else 'disabled'}"
    message = format_engagement_target_mutation(action=action, before=before, after=data)
    markup = _engagement_target_markup(target_id, data)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _resolve_engagement_target(update: Any, context: Any, target_id: str) -> None:
    client = _api_client(context)
    data = await client.resolve_engagement_target(target_id, requested_by=_reviewer_label(update))
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(data, label="Engagement target resolution"),
        reply_markup=job_actions_markup(job_id),
    )


async def _start_engagement_target_join(update: Any, context: Any, target_id: str) -> None:
    client = _api_client(context)
    data = await client.start_engagement_target_join(
        target_id,
        requested_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(data, label="Target join"),
        reply_markup=job_actions_markup(job_id),
    )


async def _start_engagement_target_detection(
    update: Any,
    context: Any,
    target_id: str,
    *,
    window_minutes: int,
) -> None:
    client = _api_client(context)
    data = await client.start_engagement_target_detection(
        target_id,
        window_minutes=window_minutes,
        requested_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(data, label="Target engagement detection"),
        reply_markup=job_actions_markup(job_id),
    )


async def _send_engagement_prompts(update: Any, context: Any, *, offset: int) -> None:
    client = _api_client(context)
    data = await client.list_engagement_prompt_profiles(
        limit=ENGAGEMENT_ADMIN_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_engagement_prompt_profiles(data, offset=offset),
        reply_markup=engagement_admin_pager_markup(
            action=ACTION_ENGAGEMENT_PROMPTS,
            offset=offset,
            total=data.get("total", 0),
            page_size=ENGAGEMENT_ADMIN_PAGE_SIZE,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        await _callback_reply(
            update,
            format_engagement_prompt_profile_card(item, index=index),
            reply_markup=engagement_prompt_actions_markup(
                str(item.get("id", "unknown")),
                active=bool(item.get("active")),
            ),
        )


async def _send_engagement_prompt_detail(update: Any, context: Any, profile_id: str) -> None:
    client = _api_client(context)
    data = await client.get_engagement_prompt_profile(profile_id)
    await _callback_reply(
        update,
        format_engagement_prompt_profile_card(data),
        reply_markup=engagement_prompt_actions_markup(profile_id, active=bool(data.get("active"))),
    )


async def _send_engagement_prompt_preview(update: Any, context: Any, profile_id: str) -> None:
    client = _api_client(context)
    data = await client.preview_engagement_prompt_profile(profile_id)
    await _callback_reply(update, format_engagement_prompt_preview(data))


async def _send_engagement_prompt_versions(update: Any, context: Any, profile_id: str) -> None:
    client = _api_client(context)
    data = await client.list_engagement_prompt_profile_versions(profile_id)
    await _callback_reply(
        update,
        format_engagement_prompt_versions(data, profile_id=profile_id),
        reply_markup=engagement_prompt_versions_markup(profile_id, data.get("items") or []),
    )


async def _confirm_engagement_prompt_activation(
    update: Any,
    context: Any,
    profile_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.get_engagement_prompt_profile(profile_id)
    message = format_engagement_prompt_activation_confirmation(data)
    markup = engagement_prompt_activation_confirm_markup(profile_id)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _activate_engagement_prompt(
    update: Any,
    context: Any,
    profile_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.activate_engagement_prompt_profile(
        profile_id,
        updated_by=_reviewer_label(update),
    )
    message = format_engagement_prompt_profile_card(data)
    markup = engagement_prompt_actions_markup(profile_id, active=bool(data.get("active")))
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _duplicate_engagement_prompt_default(update: Any, context: Any, profile_id: str) -> None:
    client = _api_client(context)
    data = await client.duplicate_engagement_prompt_profile(
        profile_id,
        created_by=_reviewer_label(update),
    )
    await _callback_reply(
        update,
        "Prompt profile duplicated.\n\n" + format_engagement_prompt_profile_card(data),
        reply_markup=engagement_prompt_actions_markup(
            str(data.get("id", profile_id)),
            active=bool(data.get("active")),
        ),
    )


async def _confirm_engagement_prompt_rollback(
    update: Any,
    context: Any,
    profile_id: str,
    version_number: int,
    *,
    edit_callback: bool = False,
) -> None:
    if version_number <= 0:
        await _callback_reply(update, "Choose a valid prompt profile version.")
        return
    client = _api_client(context)
    profile = await client.get_engagement_prompt_profile(profile_id)
    version = await _prompt_profile_version_by_number(client, profile_id, version_number)
    if version is None:
        await _callback_reply(update, f"Prompt profile version {version_number} was not found.")
        return
    message = format_engagement_prompt_rollback_confirmation(profile, version)
    markup = engagement_prompt_rollback_confirm_markup(profile_id, version_number)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _rollback_engagement_prompt(
    update: Any,
    context: Any,
    profile_id: str,
    version_number: int,
    *,
    edit_callback: bool = False,
) -> None:
    if version_number <= 0:
        await _callback_reply(update, "Choose a valid prompt profile version.")
        return
    client = _api_client(context)
    version = await _prompt_profile_version_by_number(client, profile_id, version_number)
    if version is None:
        await _callback_reply(update, f"Prompt profile version {version_number} was not found.")
        return
    data = await client.rollback_engagement_prompt_profile(
        profile_id,
        version_id=str(version.get("id")),
        updated_by=_reviewer_label(update),
    )
    message = "Prompt profile rolled back.\n\n" + format_engagement_prompt_profile_card(data)
    markup = engagement_prompt_actions_markup(profile_id, active=bool(data.get("active")))
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _prompt_profile_version_by_number(
    client: Any,
    profile_id: str,
    version_number: int,
) -> dict[str, Any] | None:
    versions = await client.list_engagement_prompt_profile_versions(profile_id)
    for version in versions.get("items") or []:
        if int(version.get("version_number") or 0) == version_number:
            return version
    return None


async def _send_engagement_style_rules(
    update: Any,
    context: Any,
    *,
    scope_type: str | None,
    scope_id: str | None,
    offset: int,
) -> None:
    client = _api_client(context)
    can_manage = _is_engagement_admin(update, context)
    data = await client.list_engagement_style_rules(
        scope_type=scope_type,
        scope_id=scope_id,
        limit=ENGAGEMENT_ADMIN_PAGE_SIZE,
        offset=offset,
    )
    header_data = {
        **data,
        "scope_type": scope_type,
        "scope_id": scope_id,
    }
    await _callback_reply(
        update,
        format_engagement_style_rules(header_data, offset=offset),
        reply_markup=engagement_style_list_markup(
            scope_type=scope_type,
            scope_id=scope_id,
            offset=offset,
            total=data.get("total", 0),
            page_size=ENGAGEMENT_ADMIN_PAGE_SIZE,
            can_manage=can_manage,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        rule_id = str(item.get("id", "unknown"))
        await _callback_reply(
            update,
            format_engagement_style_rule_card(item, index=index),
            reply_markup=engagement_style_rule_actions_markup(
                rule_id,
                active=bool(item.get("active")),
                can_manage=can_manage,
            ),
        )


async def _send_engagement_style_rule(update: Any, context: Any, rule_id: str) -> None:
    client = _api_client(context)
    data = await client.get_engagement_style_rule(rule_id)
    await _callback_reply(
        update,
        format_engagement_style_rule_card(data),
        reply_markup=engagement_style_rule_actions_markup(
            rule_id,
            active=bool(data.get("active")),
            can_manage=_is_engagement_admin(update, context),
        ),
    )


async def _toggle_style_rule(
    update: Any,
    context: Any,
    rule_id: str,
    *,
    active: bool,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.update_engagement_style_rule(
        rule_id,
        active=active,
        updated_by=_reviewer_label(update),
    )
    message = "Style rule updated.\n\n" + format_engagement_style_rule_card(data)
    reply_markup = engagement_style_rule_actions_markup(rule_id, active=bool(data.get("active")))
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _send_engagement_candidates(
    update: Any,
    context: Any,
    *,
    status: str,
    offset: int,
) -> None:
    client = _api_client(context)
    data = await client.list_engagement_candidates(
        status=status,
        limit=ENGAGEMENT_CANDIDATE_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_engagement_candidates(data, offset=offset, status=status),
        reply_markup=engagement_candidate_filter_markup(status=status),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        candidate_id = str(item.get("id", "unknown"))
        candidate_status = str(item.get("status") or status)
        reply_markup = None
        if candidate_status == "approved":
            reply_markup = engagement_candidate_send_markup(candidate_id)
        elif candidate_status == "needs_review":
            reply_markup = engagement_candidate_actions_markup(candidate_id)
        elif candidate_status == "failed":
            reply_markup = engagement_candidate_detail_markup(candidate_id, status=candidate_status)
        await _callback_reply(
            update,
            format_engagement_candidate_card(item, index=index),
            reply_markup=reply_markup,
        )
    pager_markup = engagement_candidate_pager_markup(
        offset=offset,
        total=data.get("total", 0),
        page_size=ENGAGEMENT_CANDIDATE_PAGE_SIZE,
        status=status,
    )
    if pager_markup is not None:
        await _callback_reply(update, "Reply page controls", reply_markup=pager_markup)


async def _send_engagement_candidate_detail(
    update: Any,
    context: Any,
    candidate_id: str,
) -> None:
    client = _api_client(context)
    data = await client.get_engagement_candidate(candidate_id)
    await _callback_reply(
        update,
        format_engagement_candidate_card(data),
        reply_markup=_engagement_candidate_detail_markup(candidate_id, data),
    )


async def _send_engagement_candidate_revisions(
    update: Any,
    context: Any,
    candidate_id: str,
) -> None:
    client = _api_client(context)
    data = await client.list_engagement_candidate_revisions(candidate_id)
    await _callback_reply(
        update,
        format_engagement_candidate_revisions(data, candidate_id=candidate_id),
        reply_markup=engagement_candidate_revisions_markup(candidate_id),
    )


async def _expire_engagement_candidate(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.expire_engagement_candidate(
        candidate_id,
        expired_by=_reviewer_label(update),
    )
    message = "Candidate expired.\n\n" + format_engagement_candidate_card(data)
    reply_markup = _engagement_candidate_detail_markup(candidate_id, data)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _retry_engagement_candidate(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.retry_engagement_candidate(
        candidate_id,
        retried_by=_reviewer_label(update),
    )
    message = "Candidate reopened for review.\n\n" + format_engagement_candidate_card(data)
    reply_markup = _engagement_candidate_detail_markup(candidate_id, data)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _send_engagement_settings(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    data = await client.get_engagement_settings(community_id)
    await _reply_with_engagement_settings(update, context, community_id, data)


async def _apply_engagement_preset(
    update: Any,
    context: Any,
    community_id: str,
    *,
    preset: str,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.update_engagement_settings(
        community_id,
        **_engagement_preset_payload(preset),
    )
    await _reply_with_engagement_settings(
        update,
        context,
        community_id,
        data,
        edit_callback=edit_callback,
    )


async def _toggle_engagement_setting(
    update: Any,
    context: Any,
    community_id: str,
    *,
    field: str,
    value: bool,
    edit_callback: bool = False,
) -> None:
    await _update_engagement_settings_from_current(
        update,
        context,
        community_id,
        edit_callback=edit_callback,
        **{field: value},
    )


async def _update_engagement_settings_from_current(
    update: Any,
    context: Any,
    community_id: str,
    *,
    edit_callback: bool = False,
    **updates: Any,
) -> None:
    client = _api_client(context)
    current = await client.get_engagement_settings(community_id)
    payload = _engagement_settings_payload_from_current(current, **updates)
    data = await client.update_engagement_settings(community_id, **payload)
    await _reply_with_engagement_settings(
        update,
        context,
        community_id,
        data,
        edit_callback=edit_callback,
    )


async def _reply_with_engagement_settings(
    update: Any,
    context: Any,
    community_id: str,
    data: dict[str, Any],
    *,
    edit_callback: bool = False,
) -> None:
    message = await _format_engagement_settings_message(context, data)
    reply_markup = _engagement_settings_markup(
        community_id,
        data,
        can_manage=_is_engagement_admin(update, context),
    )
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _callback_reply(update, message, reply_markup=reply_markup)


async def _format_engagement_settings_message(context: Any, data: dict[str, Any]) -> str:
    assigned_account_label: str | None = None
    assigned_account_id = data.get("assigned_account_id")
    if assigned_account_id:
        assigned_account_label = await _lookup_masked_account_label(
            _api_client(context),
            str(assigned_account_id),
        )
    return format_engagement_settings(data, assigned_account_label=assigned_account_label)


async def _lookup_masked_account_label(client: BotApiClient, account_id: str) -> str | None:
    try:
        accounts = await client.get_accounts()
    except BotApiError:
        return None

    for item in accounts.get("items") or []:
        if str(item.get("id") or "") != account_id:
            continue
        masked_phone = str(item.get("phone") or "").strip()
        if masked_phone:
            return f"{account_id} | {masked_phone}"
        status = str(item.get("status") or "").strip()
        if status:
            return f"{account_id} | {status}"
        return account_id
    return account_id


async def _start_engagement_join(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    data = await client.start_community_join(community_id, requested_by=_reviewer_label(update))
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(data, label="Community join", community_id=community_id),
        reply_markup=engagement_job_markup(job_id, community_id=community_id),
    )


async def _start_engagement_detection(
    update: Any,
    context: Any,
    community_id: str,
    *,
    window_minutes: int,
) -> None:
    client = _api_client(context)
    data = await client.start_engagement_detection(
        community_id,
        window_minutes=window_minutes,
        requested_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(
            data,
            label="Engagement detection",
            community_id=community_id,
        ),
        reply_markup=engagement_job_markup(job_id, community_id=community_id),
    )


async def _send_engagement_actions(
    update: Any,
    context: Any,
    *,
    community_id: str | None,
    offset: int,
) -> None:
    client = _api_client(context)
    data = await client.list_engagement_actions(
        community_id=community_id,
        limit=ENGAGEMENT_ACTION_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_engagement_actions(data, offset=offset),
        reply_markup=engagement_action_pager_markup(
            offset=offset,
            total=data.get("total", 0),
            page_size=ENGAGEMENT_ACTION_PAGE_SIZE,
            community_id=community_id,
        ),
    )
    for index, item in enumerate(data.get("items") or [], start=offset + 1):
        await _callback_reply(update, format_engagement_action_card(item, index=index))


async def _send_engagement_topics(update: Any, context: Any, *, offset: int) -> None:
    client = _api_client(context)
    can_manage = _is_engagement_admin(update, context)
    data = await client.list_engagement_topics()
    items = data.get("items") or []
    total = int(data.get("total", len(items)) or 0)
    page = items[offset : offset + ENGAGEMENT_TOPIC_PAGE_SIZE]
    page_data = {"items": page, "total": total}

    await _callback_reply(
        update,
        format_engagement_topics(page_data, offset=offset),
        reply_markup=engagement_topic_pager_markup(
            offset=offset,
            total=total,
            page_size=ENGAGEMENT_TOPIC_PAGE_SIZE,
        ),
    )
    for index, item in enumerate(page, start=offset + 1):
        topic_id = str(item.get("id", "unknown"))
        await _callback_reply(
            update,
            format_engagement_topic_card(item, index=index),
            reply_markup=engagement_topic_actions_markup(
                topic_id,
                active=bool(item.get("active")),
                good_count=len(item.get("example_good_replies") or []),
                bad_count=len(item.get("example_bad_replies") or []),
                can_manage=can_manage,
            ),
        )


async def _send_engagement_topic(update: Any, context: Any, topic_id: str) -> None:
    client = _api_client(context)
    data = await client.get_engagement_topic(topic_id)
    await _callback_reply(
        update,
        format_engagement_topic_card(data),
        reply_markup=engagement_topic_actions_markup(
            topic_id,
            active=bool(data.get("active")),
            good_count=len(data.get("example_good_replies") or []),
            bad_count=len(data.get("example_bad_replies") or []),
            can_manage=_is_engagement_admin(update, context),
        ),
    )


async def _toggle_engagement_topic(
    update: Any,
    context: Any,
    topic_id: str,
    *,
    active: bool,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.update_engagement_topic(topic_id, active=active)
    message = format_engagement_topic_card(data)
    reply_markup = engagement_topic_actions_markup(
        topic_id,
        active=bool(data.get("active")),
        good_count=len(data.get("example_good_replies") or []),
        bad_count=len(data.get("example_bad_replies") or []),
    )
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _remove_topic_example(
    update: Any,
    context: Any,
    topic_id: str,
    *,
    example_type: str,
    index: int,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    data = await client.remove_engagement_topic_example(
        topic_id,
        example_type=example_type,
        index=index,
    )
    message = (
        f"Removed {example_type} example #{index + 1}.\n\n" + format_engagement_topic_card(data)
    )
    reply_markup = engagement_topic_actions_markup(
        topic_id,
        active=bool(data.get("active")),
        good_count=len(data.get("example_good_replies") or []),
        bad_count=len(data.get("example_bad_replies") or []),
    )
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _update_topic_keywords(
    update: Any,
    context: Any,
    topic_id: str,
    *,
    field: str,
    keywords: list[str],
) -> None:
    client = _api_client(context)
    data = await client.update_engagement_topic(topic_id, **{field: keywords})
    label = "triggers" if field == "trigger_keywords" else "negative keywords"
    await _reply(
        update,
        f"Topic {label} updated.\n\n" + format_engagement_topic_card(data),
        reply_markup=engagement_topic_actions_markup(
            topic_id,
            active=bool(data.get("active")),
            good_count=len(data.get("example_good_replies") or []),
            bad_count=len(data.get("example_bad_replies") or []),
        ),
    )


async def _review_engagement_candidate(
    update: Any,
    context: Any,
    candidate_id: str,
    *,
    action: str,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    reviewer = _reviewer_label(update)
    if action == "approve":
        data = await client.approve_engagement_candidate(candidate_id, reviewed_by=reviewer)
    else:
        data = await client.reject_engagement_candidate(candidate_id, reviewed_by=reviewer)

    message = format_engagement_candidate_review(action, data)
    reply_markup = None
    if data.get("status") == "approved":
        reply_markup = engagement_candidate_send_markup(candidate_id)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


async def _send_engagement_reply(update: Any, context: Any, candidate_id: str) -> None:
    client = _api_client(context)
    data = await client.send_engagement_candidate(
        candidate_id,
        approved_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(
            data,
            label="Reply send",
            candidate_id=candidate_id,
        ),
        reply_markup=engagement_job_markup(job_id, candidate_id=candidate_id),
    )


async def _start_seed_group_resolution(update: Any, context: Any, seed_group_id: str) -> None:
    client = _api_client(context)
    data = await client.start_seed_group_resolution(seed_group_id)
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_seed_group_resolution(data),
        reply_markup=job_actions_markup(job_id),
    )


async def _start_snapshot(update: Any, context: Any, community_id: str) -> None:
    client = _api_client(context)
    detail = await client.get_community(community_id)
    data = await client.start_snapshot(community_id)
    community = detail.get("community") or {}
    title = community.get("title") or community.get("username")
    await _callback_reply(
        update,
        format_snapshot_job(data, community_title=title),
        reply_markup=review_result_markup(
            community_id,
            str((data.get("job") or {}).get("id", "unknown")),
        ),
    )


async def _send_job_status(update: Any, context: Any, job_id: str) -> None:
    client = _api_client(context)
    data = await client.get_job(job_id)
    await _callback_reply(update, format_job_status(data), reply_markup=job_actions_markup(job_id))


async def post_init(application: Any) -> None:
    settings: BotSettings = application.bot_data["settings"]
    application.bot_data[API_CLIENT_KEY] = BotApiClient(
        base_url=settings.api_base_url,
        api_token=settings.api_token,
        timeout_seconds=settings.request_timeout_seconds,
    )
    application.bot_data[CONFIG_EDIT_STORE_KEY] = PendingEditStore()


async def post_shutdown(application: Any) -> None:
    client = application.bot_data.get(API_CLIENT_KEY)
    if client is not None:
        await client.aclose()


def create_application(settings: BotSettings | None = None) -> Any:
    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            CallbackQueryHandler,
            CommandHandler,
            MessageHandler,
            TypeHandler,
            filters,
        )
    except ImportError as exc:
        raise RuntimeError("python-telegram-bot must be installed before the bot can run") from exc

    runtime_settings = settings or load_settings()
    validate_runtime_settings(runtime_settings)

    application = (
        Application.builder()
        .token(runtime_settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["settings"] = runtime_settings
    application.add_handler(TypeHandler(Update, access_gate), group=-1)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami_command))
    application.add_handler(CommandHandler("brief", brief_command))
    application.add_handler(CommandHandler("briefs", briefs_command))
    application.add_handler(CommandHandler("entity", entity_command))
    application.add_handler(CommandHandler("candidates", candidates_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))
    application.add_handler(CommandHandler("job", job_command))
    application.add_handler(CommandHandler("accounts", accounts_command))
    application.add_handler(CommandHandler("seeds", seeds_command))
    application.add_handler(CommandHandler("seed", seed_command))
    application.add_handler(CommandHandler("channels", channels_command))
    application.add_handler(CommandHandler("resolveseeds", resolveseeds_command))
    application.add_handler(CommandHandler("community", community_command))
    application.add_handler(CommandHandler("snapshot", snapshot_command))
    application.add_handler(CommandHandler("members", members_command))
    application.add_handler(CommandHandler("exportmembers", exportmembers_command))
    application.add_handler(CommandHandler("engagement", engagement_command))
    application.add_handler(CommandHandler("engagement_admin", engagement_admin_command))
    application.add_handler(CommandHandler("engagement_targets", engagement_targets_command))
    application.add_handler(CommandHandler("engagement_target", engagement_target_command))
    application.add_handler(CommandHandler("add_engagement_target", add_engagement_target_command))
    application.add_handler(CommandHandler("approve_engagement_target", approve_engagement_target_command))
    application.add_handler(CommandHandler("resolve_engagement_target", resolve_engagement_target_command))
    application.add_handler(CommandHandler("reject_engagement_target", reject_engagement_target_command))
    application.add_handler(CommandHandler("archive_engagement_target", archive_engagement_target_command))
    application.add_handler(CommandHandler("target_permission", target_permission_command))
    application.add_handler(CommandHandler("target_join", target_join_command))
    application.add_handler(CommandHandler("target_detect", target_detect_command))
    application.add_handler(CommandHandler("engagement_prompts", engagement_prompts_command))
    application.add_handler(CommandHandler("engagement_prompt", engagement_prompt_command))
    application.add_handler(CommandHandler("engagement_prompt_versions", engagement_prompt_versions_command))
    application.add_handler(CommandHandler("engagement_prompt_preview", engagement_prompt_preview_command))
    application.add_handler(CommandHandler("activate_engagement_prompt", activate_engagement_prompt_command))
    application.add_handler(CommandHandler("duplicate_engagement_prompt", duplicate_engagement_prompt_command))
    application.add_handler(CommandHandler("edit_engagement_prompt", edit_engagement_prompt_command))
    application.add_handler(CommandHandler("rollback_engagement_prompt", rollback_engagement_prompt_command))
    application.add_handler(CommandHandler("engagement_style", engagement_style_command))
    application.add_handler(CommandHandler("engagement_style_rule", engagement_style_rule_command))
    application.add_handler(CommandHandler("create_style_rule", create_style_rule_command))
    application.add_handler(CommandHandler("edit_style_rule", edit_style_rule_command))
    application.add_handler(CommandHandler("toggle_style_rule", toggle_style_rule_command))
    application.add_handler(CommandHandler("engagement_settings", engagement_settings_command))
    application.add_handler(CommandHandler("set_engagement", set_engagement_command))
    application.add_handler(CommandHandler("set_engagement_limits", set_engagement_limits_command))
    application.add_handler(CommandHandler("set_engagement_quiet_hours", set_engagement_quiet_hours_command))
    application.add_handler(CommandHandler("clear_engagement_quiet_hours", clear_engagement_quiet_hours_command))
    application.add_handler(CommandHandler("assign_engagement_account", assign_engagement_account_command))
    application.add_handler(CommandHandler("clear_engagement_account", clear_engagement_account_command))
    application.add_handler(CommandHandler("join_community", join_community_command))
    application.add_handler(CommandHandler("detect_engagement", detect_engagement_command))
    application.add_handler(CommandHandler("engagement_actions", engagement_actions_command))
    application.add_handler(CommandHandler("engagement_rollout", engagement_rollout_command))
    application.add_handler(CommandHandler("engagement_topics", engagement_topics_command))
    application.add_handler(CommandHandler("engagement_topic", engagement_topic_command))
    application.add_handler(CommandHandler("create_engagement_topic", create_engagement_topic_command))
    application.add_handler(CommandHandler("toggle_engagement_topic", toggle_engagement_topic_command))
    application.add_handler(CommandHandler("topic_good_reply", topic_good_reply_command))
    application.add_handler(CommandHandler("topic_bad_reply", topic_bad_reply_command))
    application.add_handler(CommandHandler("topic_remove_example", topic_remove_example_command))
    application.add_handler(CommandHandler("topic_keywords", topic_keywords_command))
    application.add_handler(CommandHandler("edit_topic_guidance", edit_topic_guidance_command))
    application.add_handler(CommandHandler("engagement_candidates", engagement_candidates_command))
    application.add_handler(CommandHandler("engagement_candidate", engagement_candidate_command))
    application.add_handler(CommandHandler("approve_reply", approve_reply_command))
    application.add_handler(CommandHandler("edit_reply", edit_reply_command))
    application.add_handler(CommandHandler("candidate_revisions", candidate_revisions_command))
    application.add_handler(CommandHandler("expire_candidate", expire_candidate_command))
    application.add_handler(CommandHandler("retry_candidate", retry_candidate_command))
    application.add_handler(CommandHandler("cancel_edit", cancel_edit_command))
    application.add_handler(CommandHandler("reject_reply", reject_reply_command))
    application.add_handler(CommandHandler("send_reply", send_reply_command))
    application.add_handler(CallbackQueryHandler(callback_query))
    application.add_handler(MessageHandler(filters.Regex(f"^{SEEDS_MENU_LABEL}$"), seeds_command))
    application.add_handler(
        MessageHandler(filters.Regex(f"^{ACCOUNTS_MENU_LABEL}$"), accounts_command)
    )
    application.add_handler(
        MessageHandler(filters.Regex(f"^{ENGAGEMENT_MENU_LABEL}$"), engagement_command)
    )
    application.add_handler(MessageHandler(filters.Regex(f"^{HELP_MENU_LABEL}$"), help_command))
    application.add_handler(MessageHandler(filters.Document.FileExtension("csv"), seed_csv_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_entity_text))
    return application


def main() -> None:
    application = create_application()
    application.run_polling()


def _api_client(context: Any) -> BotApiClient:
    return context.application.bot_data[API_CLIENT_KEY]


def _config_edit_store(context: Any) -> PendingEditStore:
    store = context.application.bot_data.get(CONFIG_EDIT_STORE_KEY)
    if store is None:
        store = PendingEditStore()
        context.application.bot_data[CONFIG_EDIT_STORE_KEY] = store
    return store


def _clear_pending_edit_if_command(update: Any, context: Any) -> None:
    command = _message_command_name(update)
    if command is None or command == "cancel_edit":
        return
    operator_id = _telegram_user_id(update)
    if operator_id is not None:
        _config_edit_store(context).cancel(operator_id)


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


async def _handle_config_edit_text(update: Any, context: Any, raw_text: str) -> bool:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        return False
    store = _config_edit_store(context)
    pending = store.get(operator_id)
    if pending is None:
        return False
    if pending.admin_only and not _is_engagement_admin(update, context):
        store.cancel(operator_id)
        await _reply(update, ENGAGEMENT_ADMIN_ONLY_MESSAGE)
        return True
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
    if pending.admin_only and not _is_engagement_admin(update, context):
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
        )

    if pending.entity == "prompt_profile":
        return await client.update_engagement_prompt_profile(
            pending.object_id,
            **{pending.field: value, "updated_by": reviewer},
        )

    if pending.entity == "topic":
        return await client.update_engagement_topic(pending.object_id, **{pending.field: value})

    if pending.entity == "style_rule":
        return await client.update_engagement_style_rule(
            pending.object_id,
            **{pending.field: value, "updated_by": reviewer},
        )

    if pending.entity == "settings":
        current = await client.get_engagement_settings(pending.object_id)
        payload = _engagement_settings_payload_from_current(current, **{pending.field: value})
        return await client.update_engagement_settings(pending.object_id, **payload)

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
            prefix + "\n\n" + format_engagement_target_card(data),
            _engagement_target_markup(pending.object_id, data),
        )
    if pending.entity == "prompt_profile":
        return (
            prefix + "\n\n" + format_engagement_prompt_profile_card(data),
            engagement_prompt_actions_markup(pending.object_id, active=bool(data.get("active"))),
        )
    if pending.entity == "topic":
        return (
            prefix + "\n\n" + format_engagement_topic_card(data),
            engagement_topic_actions_markup(
                pending.object_id,
                active=bool(data.get("active")),
                good_count=len(data.get("example_good_replies") or []),
                bad_count=len(data.get("example_bad_replies") or []),
            ),
        )
    if pending.entity == "style_rule":
        return (
            prefix + "\n\n" + format_engagement_style_rule_card(data),
            engagement_style_rule_actions_markup(
                pending.object_id,
                active=bool(data.get("active")),
            ),
        )
    if pending.entity == "settings":
        return (
            prefix + "\n\n" + format_engagement_settings(data),
            _engagement_settings_markup(pending.object_id, data),
        )
    return prefix, None


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


def _engagement_settings_markup(
    community_id: str,
    data: dict[str, Any],
    *,
    can_manage: bool = True,
) -> Any:
    return engagement_settings_markup(
        community_id,
        allow_join=bool(data.get("allow_join")),
        allow_post=bool(data.get("allow_post")),
        can_manage=can_manage,
    )


def _engagement_target_markup(
    target_id: str,
    data: dict[str, Any],
    *,
    can_manage: bool = True,
) -> Any:
    return engagement_target_actions_markup(
        target_id,
        status=str(data.get("status") or "pending"),
        allow_join=bool(data.get("allow_join")),
        allow_detect=bool(data.get("allow_detect")),
        allow_post=bool(data.get("allow_post")),
        can_manage=can_manage,
    )


def _engagement_candidate_detail_markup(candidate_id: str, data: dict[str, Any]) -> Any:
    return engagement_candidate_detail_markup(
        candidate_id,
        status=str(data.get("status") or "needs_review"),
    )


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
    parts = [part.strip() for part in raw_value.split("|")]
    if len(parts) != 3:
        return None

    name, guidance, raw_keywords = parts
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    if not name or not guidance or not keywords:
        return None
    return name, guidance, keywords


def _parse_create_style_rule_args(
    context: Any,
) -> tuple[str, str | None, str, int, str] | None:
    raw_value = " ".join(str(arg) for arg in context.args).strip()
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
        )
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))
        return
    await _reply(
        update,
        "Topic example added.\n\n" + format_engagement_topic_card(data),
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
            "Usage: /create_engagement_topic <name> | <guidance> | <comma_keywords>",
            "Include at least one trigger keyword.",
            "Example: /create_engagement_topic Open CRM | Be factual and brief. | crm, open source",
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


def _is_authorized_update(update: Any, settings: BotSettings) -> bool:
    if not settings.allowed_user_ids:
        return True
    user_id = _telegram_user_id(update)
    return user_id in settings.allowed_user_ids if user_id is not None else False


def _is_engagement_admin(update: Any, context: Any) -> bool:
    settings = _bot_settings(context)
    if settings is None or not settings.admin_user_ids:
        return True
    user_id = _telegram_user_id(update)
    return user_id in settings.admin_user_ids if user_id is not None else False


async def _require_engagement_admin(update: Any, context: Any) -> bool:
    if _is_engagement_admin(update, context):
        return True
    await _callback_reply(update, ENGAGEMENT_ADMIN_ONLY_MESSAGE)
    return False


def _callback_action_requires_engagement_admin(action: str, parts: list[str]) -> bool:
    if action in {
        ACTION_ENGAGEMENT_ADMIN,
        ACTION_ENGAGEMENT_ADMIN_LIMITS,
        ACTION_ENGAGEMENT_ADMIN_ADVANCED,
        ACTION_ENGAGEMENT_TARGET_ADD,
        ACTION_ENGAGEMENT_TARGET_APPROVE,
        ACTION_ENGAGEMENT_TARGET_RESOLVE,
        ACTION_ENGAGEMENT_TARGET_REJECT,
        ACTION_ENGAGEMENT_TARGET_ARCHIVE,
        ACTION_ENGAGEMENT_PROMPTS,
        ACTION_ENGAGEMENT_PROMPT_OPEN,
        ACTION_ENGAGEMENT_PROMPT_PREVIEW,
        ACTION_ENGAGEMENT_PROMPT_VERSIONS,
        ACTION_ENGAGEMENT_PROMPT_EDIT,
        ACTION_ENGAGEMENT_PROMPT_DUPLICATE,
        ACTION_ENGAGEMENT_PROMPT_ACTIVATE,
        ACTION_ENGAGEMENT_PROMPT_ACTIVATE_CONFIRM,
        ACTION_ENGAGEMENT_PROMPT_ROLLBACK,
        ACTION_ENGAGEMENT_PROMPT_ROLLBACK_CONFIRM,
        ACTION_ENGAGEMENT_STYLE,
        ACTION_ENGAGEMENT_STYLE_CREATE,
        ACTION_ENGAGEMENT_STYLE_OPEN,
        ACTION_ENGAGEMENT_STYLE_EDIT,
        ACTION_ENGAGEMENT_STYLE_TOGGLE,
        ACTION_ENGAGEMENT_SETTINGS_PRESET,
        ACTION_ENGAGEMENT_SETTINGS_JOIN,
        ACTION_ENGAGEMENT_SETTINGS_POST,
        ACTION_ENGAGEMENT_TOPIC_EDIT,
        ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
        ACTION_ENGAGEMENT_TOPIC_TOGGLE,
    }:
        return True
    if action == ACTION_ENGAGEMENT_TARGET_PERMISSION:
        return True
    if action == ACTION_CONFIG_EDIT_SAVE:
        return bool(parts)
    return False


def _bot_settings(context: Any) -> BotSettings | None:
    application = getattr(context, "application", None)
    bot_data = getattr(application, "bot_data", None)
    if not isinstance(bot_data, dict):
        return None
    settings = bot_data.get("settings")
    return settings if isinstance(settings, BotSettings) else None


def _is_identity_command(update: Any) -> bool:
    return _message_command_name(update) == "whoami"


def _message_command_name(update: Any) -> str | None:
    message = getattr(update, "message", None)
    text = getattr(message, "text", None)
    if not isinstance(text, str) or not text.startswith("/"):
        return None
    first_token = text.split(maxsplit=1)[0].lstrip("/")
    command = first_token.split("@", maxsplit=1)[0].lower()
    return command or None


def _telegram_user(update: Any) -> Any | None:
    effective_user = getattr(update, "effective_user", None)
    if effective_user is not None:
        return effective_user

    message = getattr(update, "message", None)
    message_user = getattr(message, "from_user", None)
    if message_user is not None:
        return message_user

    query = getattr(update, "callback_query", None)
    return getattr(query, "from_user", None)


def _telegram_user_id(update: Any) -> int | None:
    user = _telegram_user(update)
    raw_user_id = getattr(user, "id", None)
    if raw_user_id is None:
        return None
    try:
        return int(raw_user_id)
    except (TypeError, ValueError):
        return None


def _telegram_username(user: Any | None) -> str | None:
    username = getattr(user, "username", None)
    return username if isinstance(username, str) and username else None


def _reviewer_label(update: Any) -> str:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    if user_id is None:
        return "telegram_bot"
    username = _telegram_username(user)
    if username:
        return f"telegram:{user_id}:@{username}"
    return f"telegram:{user_id}"


async def _deny_access(update: Any) -> None:
    user = _telegram_user(update)
    user_id = _telegram_user_id(update)
    message = format_access_denied(user_id, username=_telegram_username(user))

    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer(message, show_alert=True)
        return

    await _reply(update, message)


def _looks_like_telegram_reference(raw_value: str) -> bool:
    value = raw_value.strip()
    if not value or any(character.isspace() for character in value):
        return False
    lowered = value.lower()
    return value.startswith("@") or lowered.startswith(("https://t.me/", "http://t.me/", "t.me/", "telegram.me/"))


async def _callback_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = update.callback_query
    if query is not None and query.message is not None:
        await query.message.reply_text(text, reply_markup=reply_markup)
        return
    await _reply(update, text, reply_markup=reply_markup)


async def _edit_callback_message(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = update.callback_query
    if query is not None:
        await query.edit_message_text(text=text, reply_markup=reply_markup)


async def _reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    if update.message is not None:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def _reply_document(
    update: Any,
    *,
    document_bytes: bytes,
    file_name: str,
    caption: str,
) -> None:
    if update.message is None:
        return
    document = io.BytesIO(document_bytes)
    document.name = file_name
    await update.message.reply_document(document=document, filename=file_name, caption=caption)


async def _fetch_all_community_members(client: BotApiClient, community_id: str) -> dict[str, Any]:
    offset = 0
    total: int | None = None
    items: list[dict[str, Any]] = []
    while total is None or offset < total:
        page = await client.list_community_members(
            community_id,
            limit=MEMBER_EXPORT_PAGE_SIZE,
            offset=offset,
        )
        page_items = page.get("items") or []
        if not page_items:
            total = page.get("total", len(items))
            break
        items.extend(page_items)
        total = int(page.get("total", len(items)))
        offset += len(page_items)
    return {"items": items, "total": total if total is not None else len(items)}


def _members_csv_bytes(items: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    fieldnames = [
        "tg_user_id",
        "username",
        "first_name",
        "membership_status",
        "activity_status",
        "first_seen_at",
        "last_updated_at",
        "last_active_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({field: item.get(field) for field in fieldnames})
    return output.getvalue().encode("utf-8")


if __name__ == "__main__":
    main()
