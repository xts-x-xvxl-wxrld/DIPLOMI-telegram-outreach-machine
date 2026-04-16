# Member Access + Account Onboarding

## Goal

Make collected visible community members accessible to the operator and unblock real Telegram
collection by adding a safe local Telethon account onboarding path.

## Scope

- Add a paginated community members API that joins `community_members` to `users`.
- Return only allowed fields: Telegram user id, public username, first name, membership/activity
  status, and timestamps.
- Add bot commands for member viewing and CSV export.
- Add a local script that creates or validates a Telethon `.session` file and registers the account
  in `telegram_accounts`.
- Preserve collection-worker boundaries: no business logic, no phone collection from community
  members, and no person-level scores.

## API Contract

`GET /api/communities/{community_id}/members`

Query parameters:

- `limit` default 20, max 1000.
- `offset` default 0.
- `username_present` optional boolean.
- `has_public_username` optional boolean alias for `username_present`.
- `activity_status` optional string: `inactive`, `passive`, or `active`.

Response:

```json
{
  "items": [
    {
      "tg_user_id": 123,
      "username": "public_user",
      "first_name": "First",
      "membership_status": "member",
      "activity_status": "inactive",
      "first_seen_at": "iso_datetime",
      "last_updated_at": "iso_datetime",
      "last_active_at": null
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

## Bot Contract

- `/members <community_id>` shows the first page of visible collected members.
- `/exportmembers <community_id>` exports the allowed member fields as CSV.
- Bot output must not include phone numbers or person-level scores.

## Onboarding Contract

`scripts/onboard_telegram_account.py`:

- Reads `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `SESSIONS_DIR`, and `DATABASE_URL`.
- Prompts for the Telegram account phone if not supplied.
- Uses Telethon interactive login to create or validate a local session file.
- Upserts one `telegram_accounts` row with `status = available`, `session_file_path`, and notes.
- Refuses path traversal for the stored session file name.

## Operator Runbook

Before onboarding:

- Use dedicated Telegram accounts, not the operator's main personal account.
- Set a username, profile name, strong 2FA password, and recovery email on each account.
- Keep accounts human-plausible and stable before automation: do not repeatedly recreate accounts or
  sessions during setup.
- Fill `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env`.
- Start the database stack so `telegram_accounts` can be updated.

Onboard the first account from the worker container:

```powershell
docker compose run --rm worker python scripts/onboard_telegram_account.py --phone +10000000000 --session-name research-account-1 --notes "primary research account"
```

Onboard a second starter account as a warm spare:

```powershell
docker compose run --rm worker python scripts/onboard_telegram_account.py --phone +10000000001 --session-name research-account-2 --notes "warm spare research account"
```

The onboarding script is intentionally interactive. Telegram still sends a login code and may ask for
the account's 2FA password. After that first login, the `.session` file in `SESSIONS_DIR` lets the
worker use the account through services without manual login on each run.

Operational checks:

- Run `/accounts` in the Telegram bot after onboarding. The account list should show masked phone
  numbers and `available` status.
- Keep the first seed-resolution test tiny, then inspect `/job <job_id>` and `/accounts`.
- If an account becomes `rate_limited`, leave it alone until `flood_wait_until`.
- If an account becomes `banned`, do not mark it available automatically. Check the account manually
  in official Telegram clients and `@SpamBot`.
- Keep `.env`, Docker volumes, and `.session` files private. A copied session file can act as the
  logged-in Telegram account.

Starter pool guidance:

- Begin with two accounts: one active and one spare.
- Keep worker concurrency low while the pool is small.
- Add more accounts only after a few successful small collection cycles without repeated
  `FloodWaitError` or session/auth errors.
- Prefer slower recurring collection over large bursts. The goal is steady account health, not peak
  throughput.

Official Telegram references:

- `core.telegram.org/api/obtaining_api_id` - API app creation and abuse-monitoring warning.
- `core.telegram.org/api/errors` - `FLOOD_WAIT` behavior.
- `telegram.org/faq_spam` - account limitation and `@SpamBot` workflow.

## Verification

- Add tests for member API filtering and allowed fields.
- Add tests for bot API client and formatting member/export behavior.
- Add a unit-level test for onboarding path normalization/upsert helpers.
- Run focused tests plus the existing suite if available.
