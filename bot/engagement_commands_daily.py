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

from .engagement_rollout_flow import _send_engagement_rollout
from .engagement_targets_flow import *
from .engagement_prompts_flow import *
from .engagement_review_flow import *
from .engagement_topics_flow import *


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
        await _send_cockpit_home_command(update, context)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def _send_cockpit_home_command(update: Any, context: Any) -> None:
    from .formatting_engagement_home import format_cockpit_home
    from .ui_engagement_home import cockpit_home_markup

    client = _api_client(context)
    payload = await client.get_engagement_cockpit_home()
    await _reply(update, format_cockpit_home(payload), reply_markup=cockpit_home_markup(payload))


async def engagement_actions_command(update: Any, context: Any) -> None:
    community_id = _first_arg(context)
    try:
        await _send_engagement_actions(update, context, community_id=community_id, offset=0)
    except BotApiError as exc:
        await _reply(update, format_api_error(exc.message))


async def engagement_rollout_command(update: Any, context: Any) -> None:
    window_days = _positive_int_arg(context, default=14)
    await _send_engagement_rollout(update, context, window_days=window_days)


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
        "Final reply updated.\n\n" + format_engagement_candidate_card(data, detail=True),
        reply_markup=_engagement_candidate_detail_markup(candidate_id, data),
    )


async def cancel_edit_command(update: Any, context: Any) -> None:
    operator_id = _telegram_user_id(update)
    if operator_id is None:
        await _reply(update, "Telegram did not include a user ID on this update.")
        return
    pending = _config_edit_store(context).cancel(operator_id)
    if pending is not None and pending.entity == "topic_create":
        from bot.engagement_wizard_flow import _wizard_return_pop, _wizard_resume_after_topic_create

        wizard_state = _wizard_return_pop(context, operator_id)
        if wizard_state is not None:
            await _wizard_resume_after_topic_create(update, context, wizard_state, {})
            return
    await _reply(update, render_edit_cancelled(pending))


__all__ = [
    "engagement_candidates_command",
    "engagement_candidate_command",
    "engagement_command",
    "engagement_actions_command",
    "engagement_rollout_command",
    "approve_reply_command",
    "reject_reply_command",
    "send_reply_command",
    "candidate_revisions_command",
    "expire_candidate_command",
    "retry_candidate_command",
    "edit_reply_command",
    "cancel_edit_command",
]
