# Slice 8: Account Health Refresh

Status: implemented.

## Goal

Refresh Telegram account health every 8 hours so join, collection, detection, and send workers make
selection decisions from current account state.

## Scope

- Add a scheduled health-refresh job for managed Telegram accounts.
- Check Telegram connection, session authorization, `get_me()`, FloodWait, banned/deactivated, and
  session-revoked states.
- Optionally spot-check a small number of joined engagement communities.
- Update account status and last error with deterministic mapping.
- Avoid leasing disabled accounts.
- Do not check accounts that are currently leased by another worker.

## Code Areas

- `backend/workers/account_manager.py`
- New worker module for account health refresh.
- `backend/workers/telegram_engagement.py` or a shared Telethon account adapter.
- `backend/workers/jobs.py`
- `backend/workers/engagement_scheduler.py`
- `tests/` account manager and worker coverage.

## Acceptance

- Healthy authorized sessions remain or become available when not leased.
- FloodWait updates `rate_limited` and `flood_wait_until`.
- Banned, deauthorized, deactivated, or revoked sessions become `banned`.
- Disabled accounts are not leased or automatically re-enabled.
- The scheduler runs refresh roughly every 8 hours.
- In-use accounts are skipped until a later refresh rather than stealing a lease.

## Dependencies

Best after slices 2-7 so account state is respected by the new behavior gates.
