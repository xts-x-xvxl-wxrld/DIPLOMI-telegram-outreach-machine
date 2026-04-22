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


async def _send_engagement_prompts(update: Any, context: Any, *, offset: int) -> None:
    client = _api_client(context)
    data = await client.list_engagement_prompt_profiles(
        limit=ENGAGEMENT_ADMIN_PAGE_SIZE,
        offset=offset,
    )
    await _callback_reply(
        update,
        format_engagement_prompt_profiles(data, offset=offset),
        reply_markup=engagement_prompt_list_markup(
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
        format_engagement_prompt_profile_card(data, detail=True),
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
        operator_user_id=_telegram_user_id(update),
    )
    message = format_engagement_prompt_profile_card(data, detail=True)
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
        operator_user_id=_telegram_user_id(update),
    )
    await _callback_reply(
        update,
        "Prompt profile duplicated.\n\n" + format_engagement_prompt_profile_card(data, detail=True),
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
        operator_user_id=_telegram_user_id(update),
    )
    message = "Prompt profile rolled back.\n\n" + format_engagement_prompt_profile_card(data, detail=True)
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
    can_manage = await _is_engagement_admin_async(update, context)
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
        format_engagement_style_rule_card(data, detail=True),
        reply_markup=engagement_style_rule_actions_markup(
            rule_id,
            active=bool(data.get("active")),
            can_manage=await _is_engagement_admin_async(update, context),
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
        operator_user_id=_telegram_user_id(update),
    )
    message = "Style rule updated.\n\n" + format_engagement_style_rule_card(data, detail=True)
    reply_markup = engagement_style_rule_actions_markup(rule_id, active=bool(data.get("active")))
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=reply_markup)
        return
    await _reply(update, message, reply_markup=reply_markup)


__all__ = [
    "_send_engagement_prompts",
    "_send_engagement_prompt_detail",
    "_send_engagement_prompt_preview",
    "_send_engagement_prompt_versions",
    "_confirm_engagement_prompt_activation",
    "_activate_engagement_prompt",
    "_duplicate_engagement_prompt_default",
    "_confirm_engagement_prompt_rollback",
    "_rollback_engagement_prompt",
    "_prompt_profile_version_by_number",
    "_send_engagement_style_rules",
    "_send_engagement_style_rule",
    "_toggle_style_rule",
]
