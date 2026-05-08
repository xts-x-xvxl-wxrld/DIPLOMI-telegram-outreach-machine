from __future__ import annotations

DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE = "cet"

QUIET_HOURS_TIMEZONE_LABELS: dict[str, str] = {
    "utc": "UTC",
    "cet": "CET",
    "us_east": "US East",
    "us_west": "US West",
}

USER_SELECTABLE_QUIET_HOURS_TIMEZONES: tuple[str, ...] = ("cet", "us_east", "us_west")


def normalize_bot_quiet_hours_timezone(
    value: object,
    *,
    default: str = DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in QUIET_HOURS_TIMEZONE_LABELS:
        return raw
    return default


def quiet_hours_timezone_label(
    value: object,
    *,
    default: str = DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE,
) -> str:
    normalized = normalize_bot_quiet_hours_timezone(value, default=default)
    return QUIET_HOURS_TIMEZONE_LABELS[normalized]


__all__ = [
    "DEFAULT_WIZARD_QUIET_HOURS_TIMEZONE",
    "QUIET_HOURS_TIMEZONE_LABELS",
    "USER_SELECTABLE_QUIET_HOURS_TIMEZONES",
    "normalize_bot_quiet_hours_timezone",
    "quiet_hours_timezone_label",
]
