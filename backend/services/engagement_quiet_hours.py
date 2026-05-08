from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from backend.db.enums import QuietHoursTimezone

DEFAULT_QUIET_HOURS_TIMEZONE = QuietHoursTimezone.UTC.value
QUIET_HOURS_TIMEZONE_LABELS = {
    QuietHoursTimezone.UTC.value: "UTC",
    QuietHoursTimezone.CET.value: "CET/CEST",
    QuietHoursTimezone.US_EAST.value: "US Eastern",
    QuietHoursTimezone.US_WEST.value: "US Pacific",
}
QUIET_HOURS_TIMEZONE_ZONEINFO = {
    QuietHoursTimezone.UTC.value: timezone.utc,
    QuietHoursTimezone.CET.value: ZoneInfo("Europe/Berlin"),
    QuietHoursTimezone.US_EAST.value: ZoneInfo("America/New_York"),
    QuietHoursTimezone.US_WEST.value: ZoneInfo("America/Los_Angeles"),
}
USER_SELECTABLE_QUIET_HOURS_TIMEZONES = (
    QuietHoursTimezone.CET.value,
    QuietHoursTimezone.US_EAST.value,
    QuietHoursTimezone.US_WEST.value,
)


def normalize_quiet_hours_timezone(value: str | QuietHoursTimezone | None) -> str:
    raw_value = DEFAULT_QUIET_HOURS_TIMEZONE if value is None else getattr(value, "value", value)
    timezone_value = str(raw_value).strip().lower()
    if timezone_value not in QUIET_HOURS_TIMEZONE_ZONEINFO:
        raise ValueError(f"unsupported quiet-hours timezone: {raw_value}")
    return timezone_value


def quiet_hours_timezone_label(value: str | QuietHoursTimezone | None) -> str:
    return QUIET_HOURS_TIMEZONE_LABELS[normalize_quiet_hours_timezone(value)]


def is_quiet_time(
    now: datetime,
    *,
    quiet_hours_start: time | None,
    quiet_hours_end: time | None,
    quiet_hours_timezone: str | QuietHoursTimezone | None = None,
) -> bool:
    if quiet_hours_start is None or quiet_hours_end is None:
        return False
    current_time = (
        _ensure_aware_utc(now)
        .astimezone(QUIET_HOURS_TIMEZONE_ZONEINFO[normalize_quiet_hours_timezone(quiet_hours_timezone)])
        .time()
        .replace(tzinfo=None)
    )
    if quiet_hours_start == quiet_hours_end:
        return True
    if quiet_hours_start < quiet_hours_end:
        return quiet_hours_start <= current_time < quiet_hours_end
    return current_time >= quiet_hours_start or current_time < quiet_hours_end


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "DEFAULT_QUIET_HOURS_TIMEZONE",
    "QUIET_HOURS_TIMEZONE_LABELS",
    "USER_SELECTABLE_QUIET_HOURS_TIMEZONES",
    "is_quiet_time",
    "normalize_quiet_hours_timezone",
    "quiet_hours_timezone_label",
]
