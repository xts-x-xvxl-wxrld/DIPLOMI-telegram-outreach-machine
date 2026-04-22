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
from .discovery_handlers import *
from .engagement_handlers import *
from .callback_handlers import *


async def post_init(application: Any) -> None:
    settings: BotSettings = application.bot_data["settings"]
    application.bot_data[API_CLIENT_KEY] = BotApiClient(
        base_url=settings.api_base_url,
        api_token=settings.api_token,
        timeout_seconds=settings.request_timeout_seconds,
    )
    application.bot_data[CONFIG_EDIT_STORE_KEY] = PendingEditStore()
    application.bot_data[ACCOUNT_CONFIRM_STORE_KEY] = {}


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
    application.add_handler(CommandHandler("create_engagement_prompt", create_engagement_prompt_command))
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


__all__ = [
    "post_init",
    "post_shutdown",
    "create_application",
    "main",
]
