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
    format_engagement_collection_runs,
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
        reply_markup=engagement_home_markup(
            show_admin=await _is_engagement_admin_async(update, context),
        ),
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


async def _send_engagement_settings_lookup(update: Any, context: Any, *, offset: int) -> None:
    client = _api_client(context)
    data = await client.list_engagement_targets(
        status="approved",
        limit=ENGAGEMENT_ADMIN_PAGE_SIZE,
        offset=offset,
    )
    items = data.get("items") or []
    await _callback_reply(
        update,
        format_engagement_settings_lookup(data, offset=offset),
        reply_markup=engagement_settings_lookup_markup(
            items,
            offset=offset,
            total=data.get("total", 0),
            page_size=ENGAGEMENT_ADMIN_PAGE_SIZE,
        ),
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
    can_manage = await _is_engagement_admin_async(update, context)
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
                community_id=str(item["community_id"]) if item.get("community_id") else None,
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
        format_engagement_target_card(data, detail=True),
        reply_markup=_engagement_target_markup(
            target_id,
            data,
            can_manage=await _is_engagement_admin_async(update, context),
        ),
    )


async def _confirm_engagement_target_approval(
    update: Any,
    context: Any,
    target_id: str,
    *,
    edit_callback: bool = False,
) -> None:
    client = _api_client(context)
    before = await client.get_engagement_target(target_id)
    after = {
        **before,
        "status": "approved",
        "allow_join": True,
        "allow_detect": True,
        "allow_post": True,
    }
    message = format_engagement_target_approval_confirmation(before=before, after=after)
    markup = engagement_target_approval_confirm_markup(target_id)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


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
        operator_user_id=_telegram_user_id(update),
    )
    message = format_engagement_target_mutation(action="approved", before=before, after=data)
    markup = _engagement_target_markup(target_id, data)
    if edit_callback:
        await _edit_callback_message(update, message, reply_markup=markup)
        return
    await _reply(update, message, reply_markup=markup)


async def _confirm_engagement_target_permission(
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
    after = {**before, field_name: enabled}
    message = format_engagement_target_permission_confirmation(
        permission=permission,
        before=before,
        after=after,
    )
    markup = engagement_target_permission_confirm_markup(
        target_id,
        permission_code=permission[0],
        enabled=enabled,
    )
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
        operator_user_id=_telegram_user_id(update),
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
        operator_user_id=_telegram_user_id(update),
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
    data = await client.resolve_engagement_target(
        target_id,
        requested_by=_reviewer_label(update),
        operator_user_id=_telegram_user_id(update),
    )
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


async def _start_engagement_target_collection(update: Any, context: Any, target_id: str) -> None:
    client = _api_client(context)
    data = await client.start_engagement_target_collection(
        target_id,
        requested_by=_reviewer_label(update),
    )
    job_id = str((data.get("job") or {}).get("id", "unknown"))
    await _callback_reply(
        update,
        format_engagement_job_response(data, label="Target engagement collection"),
        reply_markup=job_actions_markup(job_id),
    )


async def _send_engagement_target_collection_runs(
    update: Any,
    context: Any,
    target_id: str,
) -> None:
    client = _api_client(context)
    data = await client.list_engagement_target_collection_runs(target_id)
    await _callback_reply(
        update,
        format_engagement_collection_runs(data, target_id=target_id),
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


__all__ = [
    "_send_engagement_home",
    "_send_engagement_admin",
    "_send_engagement_admin_limits",
    "_send_engagement_settings_lookup",
    "_send_engagement_admin_advanced",
    "_send_engagement_targets",
    "_send_engagement_target",
    "_confirm_engagement_target_approval",
    "_approve_engagement_target",
    "_confirm_engagement_target_permission",
    "_set_engagement_target_status",
    "_set_engagement_target_permission",
    "_resolve_engagement_target",
    "_start_engagement_target_join",
    "_start_engagement_target_collection",
    "_send_engagement_target_collection_runs",
    "_start_engagement_target_detection",
]
