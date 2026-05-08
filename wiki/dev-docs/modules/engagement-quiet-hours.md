# Engagement Quiet Hours

## Purpose

Document the narrow seam that stores quiet-hours windows, evaluates them at
runtime, and exposes them through the task-first wizard and cockpit issue
flows.

## Backend source of truth

- `backend/services/engagement_quiet_hours.py` owns timezone normalization,
  labels, and runtime evaluation.
- Stored values use string codes: `utc`, `cet`, `us_east`, `us_west`.
- Runtime checks must call `is_quiet_time(...)` instead of comparing raw UTC
  wall-clock times directly. The helper converts `now` into the stored
  timezone before checking the configured `time` window.

## Persistence contract

- `community_engagement_settings` and `engagement_settings` both now carry
  `quiet_hours_timezone`, defaulting to `utc`.
- Legacy rows keep that `utc` default so existing windows preserve prior
  behavior instead of silently shifting to a new local timezone.
- Task-first route payloads can update the timezone through
  `TaskFirstEngagementSettingsUpdate` and cockpit quiet-hours write requests.

## Bot surfaces

- `bot/engagement_quiet_hours_timezones.py` is the shared bot-side label and
  normalization module for timezone choices.
- New wizard sessions default to `cet`, while existing saved settings can still
  round-trip `utc`.
- Wizard quiet-hours editing is still message-based (`HH:MM-HH:MM` or `off`),
  but the review action now includes inline timezone toggles before save.
- Cockpit issue editing keeps the selected timezone in the per-user
  `QUIET_HOURS_EDIT_STORE_KEY` state so operators can change the timezone and
  then submit a new window without losing context.
