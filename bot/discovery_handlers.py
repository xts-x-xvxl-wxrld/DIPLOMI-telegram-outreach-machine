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


__all__ = [
    "start_command",
    "help_command",
    "whoami_command",
    "briefs_command",
    "brief_command",
    "job_command",
    "entity_command",
    "candidates_command",
    "approve_command",
    "reject_command",
    "accounts_command",
    "seeds_command",
    "seed_command",
    "channels_command",
    "resolveseeds_command",
    "community_command",
    "snapshot_command",
    "members_command",
    "exportmembers_command",
    "seed_csv_document",
    "telegram_entity_text",
    "_review",
    "_review_callback",
    "_send_seed_group_detail",
    "_send_seed_group_channels",
    "_send_seed_group_candidates",
    "_send_community_detail",
    "_send_community_members",
    "_send_operator_cockpit",
    "_send_discovery_cockpit",
    "_send_accounts",
    "_send_seed_groups",
    "_send_help",
    "_start_seed_group_resolution",
    "_start_snapshot",
    "_send_job_status",
]
