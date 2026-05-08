from __future__ import annotations

from typing import Any

from .engagement_quiet_hours_timezones import (
    DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
    normalize_bot_quiet_hours_timezone,
    quiet_hours_timezone_label,
)

WIZARD_LEVEL_MODE = {
    "draft": "suggest",
    "auto_send": "auto_limited",
}

LEGACY_WIZARD_LEVEL_ALIASES = {
    "watching": "draft",
    "suggesting": "draft",
    "sending": "auto_send",
    "observe": "draft",
    "suggest": "draft",
    "require_approval": "auto_send",
    "auto_limited": "auto_send",
}

WIZARD_DEFAULT_MAX_POSTS_PER_DAY = 300
WIZARD_DEFAULT_MIN_MINUTES_BETWEEN_POSTS = 1


def wizard_state(pending: Any) -> dict[str, Any]:
    return dict(pending.flow_state or {})


def wizard_state_engagement_id(state: dict[str, Any]) -> str:
    return str(state.get("engagement_id") or "")


def wizard_state_topic_id(state: dict[str, Any]) -> str | None:
    return state.get("topic_id") or None


def wizard_state_account_id(state: dict[str, Any]) -> str | None:
    return state.get("account_id") or None


def wizard_state_mode(state: dict[str, Any]) -> str | None:
    mode = state.get("mode") or None
    if mode is None:
        return None
    mode_value = str(mode)
    return LEGACY_WIZARD_LEVEL_ALIASES.get(mode_value, mode_value)


def wizard_quiet_hours_label(state: dict[str, Any]) -> str:
    start = state.get("quiet_hours_start")
    end = state.get("quiet_hours_end")
    if not start or not end:
        return "Off"
    return f"{start}-{end}"


def wizard_quiet_hours_timezone(state: dict[str, Any]) -> str:
    return normalize_bot_quiet_hours_timezone(
        state.get("quiet_hours_timezone"),
        default=DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
    )


def wizard_quiet_hours_timezone_display(state: dict[str, Any]) -> str:
    return quiet_hours_timezone_label(
        state.get("quiet_hours_timezone"),
        default=DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
    )


def sync_wizard_settings_state(state: dict[str, Any], payload: dict[str, Any]) -> None:
    settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    if not isinstance(settings, dict):
        return
    for key in (
        "assigned_account_id",
        "max_posts_per_day",
        "min_minutes_between_posts",
        "quiet_hours_start",
        "quiet_hours_end",
        "quiet_hours_timezone",
    ):
        if key in settings:
            state[key] = settings.get(key)
    if "mode" in settings and settings.get("mode") is not None:
        state["mode"] = LEGACY_WIZARD_LEVEL_ALIASES.get(str(settings["mode"]), str(settings["mode"]))


def fresh_wizard_state() -> dict[str, Any]:
    return {
        "engagement_id": None,
        "target_id": None,
        "community_id": None,
        "target_ref": None,
        "topic_id": None,
        "account_id": None,
        "mode": None,
        "max_posts_per_day": WIZARD_DEFAULT_MAX_POSTS_PER_DAY,
        "min_minutes_between_posts": WIZARD_DEFAULT_MIN_MINUTES_BETWEEN_POSTS,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
        "quiet_hours_timezone": DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
        "join_status": None,
        "join_message": None,
        "join_job_id": None,
        "return_callback": None,
    }
