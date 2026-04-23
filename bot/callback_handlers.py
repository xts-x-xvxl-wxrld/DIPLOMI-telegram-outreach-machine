# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

import csv
import io
import re
from typing import Any

from bot.account_handlers import begin_account_onboarding_flow, handle_account_onboarding_skip
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
    ACTION_ENGAGEMENT_TARGET_COLLECT,
    ACTION_ENGAGEMENT_TARGET_COLLECTION_RUNS,
    ACTION_ENGAGEMENT_TARGET_OPEN,
    ACTION_ENGAGEMENT_TARGET_PERMISSION,
    ACTION_ENGAGEMENT_TARGET_PERMISSION_CONFIRM,
    ACTION_ENGAGEMENT_TARGET_REJECT,
    ACTION_ENGAGEMENT_TARGET_RESOLVE,
    ACTION_ENGAGEMENT_TARGETS,
    ACTION_ENGAGEMENT_TOPIC_CREATE,
    ACTION_ENGAGEMENT_TOPIC_EDIT,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD,
    ACTION_ENGAGEMENT_TOPIC_EXAMPLE_REMOVE,
    ACTION_ENGAGEMENT_TOPIC_LIST,
    ACTION_ENGAGEMENT_TOPIC_OPEN,
    ACTION_ENGAGEMENT_TOPIC_TOGGLE,
    ACTION_JOB_STATUS,
    ACTION_OP_ACCOUNTS,
    ACTION_OP_ADD_ACCOUNT,
    ACTION_OP_ACCOUNT_SKIP,
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
    accounts_cockpit_markup,
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
from .discovery_handlers import *
from .search_handlers import *
from .engagement_handlers import *


async def callback_query(update: Any, context: Any) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    await query.answer()
    action, parts = parse_callback_data(query.data)

    if _callback_action_requires_engagement_admin(
        action,
        parts,
    ) and not await _is_engagement_admin_async(update, context):
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
        if await _handle_search_callback(update, context, action, parts):
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
        if action == ACTION_ENGAGEMENT_ACCOUNT_CONFIRM:
            await _apply_confirmed_engagement_account_assignment(
                update,
                context,
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_ACCOUNT_CANCEL:
            await _cancel_engagement_account_assignment(update, context, edit_callback=True)
            return
        if action == ACTION_ENGAGEMENT_TARGETS and parts:
            status, offset = _engagement_target_callback_status_and_offset(parts)
            await _send_engagement_targets(update, context, status=status, offset=offset)
            return
        if action == ACTION_ENGAGEMENT_TARGET_ADD:
            await _start_target_create(update, context)
            return
        if action == ACTION_ENGAGEMENT_TARGET_OPEN and len(parts) == 1:
            await _send_engagement_target(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_RESOLVE and len(parts) == 1:
            await _resolve_engagement_target(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_APPROVE and len(parts) == 1:
            await _confirm_engagement_target_approval(
                update,
                context,
                parts[0],
                edit_callback=True,
            )
            return
        if action == ACTION_ENGAGEMENT_TARGET_APPROVE_CONFIRM and len(parts) == 1:
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
                if permission == "post":
                    await _confirm_engagement_target_permission(
                        update,
                        context,
                        parts[0],
                        permission=permission,
                        enabled=enabled,
                        edit_callback=True,
                    )
                    return
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
        if action == ACTION_ENGAGEMENT_TARGET_COLLECT and len(parts) == 1:
            await _start_engagement_target_collection(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_COLLECTION_RUNS and len(parts) == 1:
            await _send_engagement_target_collection_runs(update, context, parts[0])
            return
        if action == ACTION_ENGAGEMENT_TARGET_DETECT and len(parts) == 2:
            await _start_engagement_target_detection(
                update,
                context,
                parts[0],
                window_minutes=_parse_positive_int(parts[1], default=60),
            )
            return
        if action == ACTION_ENGAGEMENT_TARGET_EDIT and len(parts) == 2:
            if parts[1] != "notes":
                await _callback_reply(update, "That target field is not editable from this button.")
                return
            await _start_config_edit(
                update,
                context,
                entity="target",
                object_id=parts[0],
                field="notes",
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
        if action == ACTION_ENGAGEMENT_PROMPT_CREATE:
            await _start_prompt_profile_create(update, context)
            return
        if action == ACTION_ENGAGEMENT_TARGET_PERMISSION_CONFIRM and len(parts) == 3:
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
            await _start_style_rule_create(update, context)
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
        if action == ACTION_ENGAGEMENT_SETTINGS_LOOKUP and parts:
            await _send_engagement_settings_lookup(
                update,
                context,
                offset=_parse_offset(parts[0]),
            )
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
        if action == ACTION_ENGAGEMENT_SETTINGS_EDIT and len(parts) == 2:
            field = _normalize_settings_edit_field(parts[1])
            if field is None:
                await _callback_reply(update, "That settings field is not editable from this button.")
                return
            await _start_config_edit(
                update,
                context,
                entity="settings",
                object_id=parts[0],
                field=field,
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
        if action == ACTION_ENGAGEMENT_TOPIC_CREATE:
            await _start_topic_create(update, context)
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
        if action == ACTION_ENGAGEMENT_TOPIC_EXAMPLE_ADD and len(parts) == 2:
            example_type = "good" if parts[1] == "g" else "bad" if parts[1] == "b" else None
            if example_type is None:
                await _callback_reply(update, "That topic example type is not available.")
                return
            await _start_config_edit(
                update,
                context,
                entity="topic_example",
                object_id=parts[0],
                field=example_type,
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
        if action == ACTION_OP_ADD_ACCOUNT and len(parts) == 1:
            await begin_account_onboarding_flow(update, context, parts[0])
            return
        if action == ACTION_OP_ACCOUNT_SKIP:
            await handle_account_onboarding_skip(update, context)
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


__all__ = [
    "callback_query",
]
