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
    ACTION_ENGAGEMENT_CANDIDATE_STYLE,
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
    engagement_candidate_style_scope_markup,
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


def _candidate_timeliness_rank(item: dict[str, Any]) -> int:
    return {"fresh": 0, "aging": 1, "stale": 2}.get(str(item.get("timeliness") or "").casefold(), 3)


def _candidate_moment_rank(item: dict[str, Any]) -> int:
    return {"strong": 0, "good": 1, "weak": 2}.get(str(item.get("moment_strength") or "").casefold(), 3)


def _candidate_value_rank(item: dict[str, Any]) -> int:
    return {
        "practical_tip": 0,
        "correction": 1,
        "resource": 2,
        "clarifying_question": 3,
        "other": 4,
        "none": 5,
    }.get(str(item.get("reply_value") or "").casefold(), 6)


def _sorted_candidate_items(items: list[dict[str, Any]], *, status: str) -> list[dict[str, Any]]:
    if status == "needs_review":
        return sorted(
            items,
            key=lambda item: (
                _candidate_timeliness_rank(item),
                str(item.get("review_deadline_at") or item.get("reply_deadline_at") or "9999-99-99"),
                _candidate_moment_rank(item),
                _candidate_value_rank(item),
                str(item.get("created_at") or "9999-99-99"),
            ),
        )
    if status == "approved":
        return sorted(
            items,
            key=lambda item: (
                _candidate_timeliness_rank(item),
                str(item.get("reply_deadline_at") or item.get("review_deadline_at") or "9999-99-99"),
                _candidate_moment_rank(item),
                str(item.get("created_at") or "9999-99-99"),
            ),
        )
    if status in {"failed", "expired"}:
        return sorted(
            items,
            key=lambda item: (
                _candidate_timeliness_rank(item),
                str(item.get("reply_deadline_at") or item.get("review_deadline_at") or "9999-99-99"),
                str(item.get("created_at") or "9999-99-99"),
            ),
        )
    return items


def _candidate_with_settings_context(candidate: dict[str, Any], settings: dict[str, Any] | None) -> dict[str, Any]:
    if not settings:
        return candidate
    merged = {**candidate}
    status = str(candidate.get("status") or "")
    if settings.get("quiet_hours_active") is True:
        merged["send_block_reason"] = "Blocked: quiet hours active"
    elif settings.get("rate_limit_active") is True or settings.get("rate_limited") is True:
        merged["send_block_reason"] = "Blocked: rate limit active"
    elif settings.get("has_joined_engagement_account") is False:
        merged["send_block_reason"] = "Blocked: no joined engagement account"
    elif status in {"approved", "failed"} and not bool(settings.get("allow_post")):
        merged["send_block_reason"] = "Blocked: posting permission off"
    elif settings.get("assigned_account_status") in {"rate_limited", "banned"}:
        merged["send_block_reason"] = (
            f"Blocked: account {str(settings['assigned_account_status']).replace('_', ' ')}"
        )
    if merged.get("send_block_reason") and candidate.get("community_id"):
        merged["fix_settings_command"] = f"/engagement_settings {candidate['community_id']}"
        merged["fix_actions_command"] = f"/engagement_actions {candidate['community_id']}"
        merged["fix_community_command"] = f"/community {candidate['community_id']}"
        merged["fix_join_command"] = f"/join_community {candidate['community_id']}"
    return merged


async def _candidate_detail_context(client: Any, candidate_id: str) -> dict[str, Any]:
    data = await client.get_engagement_candidate(candidate_id)
    community_id = data.get("community_id")
    if not community_id:
        return data
    try:
        settings = await client.get_engagement_settings(str(community_id))
    except BotApiError:
        return data
    return _candidate_with_settings_context(data, settings)


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
    items = _sorted_candidate_items(list(data.get("items") or []), status=status)
    await _callback_reply(
        update,
        format_engagement_candidates(data, offset=offset, status=status),
        reply_markup=engagement_candidate_filter_markup(status=status),
    )
    for index, item in enumerate(items, start=offset + 1):
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
        await _callback_reply(update, "Reply queue page controls", reply_markup=pager_markup)


async def _send_engagement_candidate_detail(
    update: Any,
    context: Any,
    candidate_id: str,
) -> None:
    client = _api_client(context)
    data = await _candidate_detail_context(client, candidate_id)
    await _callback_reply(
        update,
        format_engagement_candidate_card(data, detail=True),
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
    data = await _candidate_detail_context(client, candidate_id) if data.get("community_id") else data
    message = "Reply opportunity expired.\n\n" + format_engagement_candidate_card(data, detail=True)
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
    data = await _candidate_detail_context(client, candidate_id) if data.get("community_id") else data
    message = "Reply opportunity reopened for review.\n\n" + format_engagement_candidate_card(data, detail=True)
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
        operator_user_id=_telegram_user_id(update),
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
    data = await client.update_engagement_settings(
        community_id,
        **payload,
        operator_user_id=_telegram_user_id(update),
    )
    await _reply_with_engagement_settings(
        update,
        context,
        community_id,
        data,
        edit_callback=edit_callback,
    )


async def _confirm_engagement_account_assignment(
    update: Any,
    context: Any,
    community_id: str,
    *,
    assigned_account_id: str | None,
    edit_callback: bool = False,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _callback_reply(update, "Telegram did not include a user ID on this update.")
        return

    client = _api_client(context)
    current = await client.get_engagement_settings(community_id)
    current_account_id = current.get("assigned_account_id")
    before_label = await _format_account_assignment_label(
        client,
        str(current_account_id) if current_account_id else None,
    )
    after_label = await _format_account_assignment_label(client, assigned_account_id)
    _account_confirm_store(context)[operator_id] = {
        "community_id": community_id,
        "assigned_account_id": assigned_account_id,
    }
    message = format_engagement_account_assignment_confirmation(
        current,
        before_account_label=before_label,
        after_account_label=after_label,
    )
    if edit_callback:
        await _edit_callback_message(
            update,
            message,
            reply_markup=engagement_account_confirm_markup(),
        )
        return
    await _reply(update, message, reply_markup=engagement_account_confirm_markup())


async def _apply_confirmed_engagement_account_assignment(
    update: Any,
    context: Any,
    *,
    edit_callback: bool = False,
) -> None:
    operator_id = _telegram_user_id(update)
    pending = (
        _account_confirm_store(context).pop(operator_id, None)
        if operator_id is not None
        else None
    )
    if not pending:
        await _callback_reply(update, "No pending engagement account change to confirm.")
        return
    await _update_engagement_settings_from_current(
        update,
        context,
        str(pending["community_id"]),
        assigned_account_id=pending.get("assigned_account_id"),
        edit_callback=edit_callback,
    )


async def _cancel_engagement_account_assignment(
    update: Any,
    context: Any,
    *,
    edit_callback: bool = False,
) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is not None:
        _account_confirm_store(context).pop(operator_id, None)
    message = "Cancelled engagement account assignment change."
    if edit_callback:
        await _edit_callback_message(update, message)
        return
    await _reply(update, message)


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
        can_manage=await _is_engagement_admin_async(update, context),
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


async def _format_account_assignment_label(
    client: BotApiClient,
    account_id: str | None,
) -> str:
    if not account_id:
        return "none"
    return await _lookup_masked_account_label(client, account_id) or account_id


async def _lookup_masked_account_label(client: BotApiClient, account_id: str) -> str | None:
    try:
        accounts = await client.get_accounts()
    except BotApiError:
        return None

    for item in accounts.get("items") or []:
        if str(item.get("id") or "") != account_id:
            continue
        phone = str(item.get("phone") or "").strip()
        if phone:
            return f"{account_id} | {_safe_masked_phone(phone)}"
        status = str(item.get("status") or "").strip()
        if status:
            return f"{account_id} | {status}"
        return account_id
    return account_id


def _safe_masked_phone(value: str) -> str:
    if "*" in value:
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 7:
        return value
    prefix = "+" if value.strip().startswith("+") else ""
    return f"{prefix}{digits[:3]}*****{digits[-2:]}"


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


__all__ = [
    "_send_engagement_candidates",
    "_send_engagement_candidate_detail",
    "_send_engagement_candidate_revisions",
    "_expire_engagement_candidate",
    "_retry_engagement_candidate",
    "_send_engagement_settings",
    "_apply_engagement_preset",
    "_toggle_engagement_setting",
    "_update_engagement_settings_from_current",
    "_confirm_engagement_account_assignment",
    "_apply_confirmed_engagement_account_assignment",
    "_cancel_engagement_account_assignment",
    "_reply_with_engagement_settings",
    "_format_engagement_settings_message",
    "_format_account_assignment_label",
    "_lookup_masked_account_label",
    "_safe_masked_phone",
    "_start_engagement_join",
    "_start_engagement_detection",
    "_send_engagement_actions",
]
