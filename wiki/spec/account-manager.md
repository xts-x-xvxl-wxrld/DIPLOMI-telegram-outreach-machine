# Account Manager Spec

## Purpose
The account manager coordinates small pools of Telegram user accounts used by Telethon-based workers.

It is a Python utility module, not a separate service. Expansion, community snapshots, collection,
entity-intake, and future engagement workers call it directly before making Telegram API calls.

Account pool separation is specified in `wiki/spec/telegram-account-pools.md`. Search/read-only work
and public engagement work must use separate Telegram identities.

## Responsibilities

- Lease one healthy Telegram account to one worker job at a time.
- Prevent concurrent use of the same account.
- Enforce account pool separation for search/read-only work and engagement work.
- Track account health and rate-limit state.
- Convert Telegram account failures into deterministic worker outcomes.
- Recover stale leases left behind by crashed workers.

## Non-Responsibilities

- It does not decide which communities to collect.
- It does not analyze messages or score relevance.
- It does not send Telegram bot messages directly, except through a higher-level alert hook/event.
- It does not create new Telegram accounts automatically.

## Database Table

Uses `telegram_accounts`.

Required account pools:

- `search` - read-only account for seed resolution, expansion, entity intake, community snapshots, and any future legacy read-only collection.
- `engagement` - public-facing account for engagement-target resolution, approved engagement collection, approved engagement joins, and approved public replies.
- `disabled` - never leased automatically.

Required statuses:

- `available` - account may be leased.
- `in_use` - account is currently leased by a worker job.
- `rate_limited` - account hit a Telegram flood wait and cannot be used until `flood_wait_until`.
- `banned` - account is unusable until manually resolved.

The database spec defines the table and lease-related columns.

## Public Interface

```python
@dataclass
class AccountLease:
    account_id: UUID
    phone: str
    session_file_path: str
    lease_owner: str
    lease_expires_at: datetime

def acquire_account(
    *,
    job_id: str,
    purpose: Literal[
        "expansion",
        "community_snapshot",
        "collection",
        "engagement_collection",
        "entity_intake",
        "engagement_target_resolve",
        "engagement_join",
        "engagement_send",
    ],
    lease_seconds: int = 900,
) -> AccountLease:
    ...

def release_account(
    *,
    account_id: UUID,
    job_id: str,
    outcome: Literal["success", "error", "rate_limited", "banned"],
    flood_wait_seconds: int | None = None,
    error_message: str | None = None,
) -> None:
    ...

def recover_stale_leases(now: datetime | None = None) -> int:
    ...
```

## Acquire Flow

`acquire_account()` runs in a database transaction.

Before selecting an account, it may recover expired leases:

```sql
UPDATE telegram_accounts
SET status = 'available',
    lease_owner = NULL,
    lease_expires_at = NULL
WHERE status = 'in_use'
  AND lease_expires_at < now();
```

It then selects one account:

```sql
SELECT *
FROM telegram_accounts
WHERE account_pool = :required_pool
  AND (
    status = 'available'
    OR (status = 'rate_limited' AND flood_wait_until <= now())
  )
ORDER BY last_used_at NULLS FIRST, added_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

The required pool is derived from the account purpose. Broad discovery/read-only purposes use
`search`; engagement-target resolution, approved engagement collection, join, and send use
`engagement`. There is no fallback between pools.

If an account is found, it is marked:

```sql
status = 'in_use'
lease_owner = job_id
lease_expires_at = now() + lease_seconds
last_used_at = now()
```

If no account is available, raise `NoAccountAvailable`.

## Release Flow

`release_account()` only releases the account when `lease_owner = job_id`.

Outcomes:

| Outcome | Status after release | Notes |
|---|---|---|
| `success` | `available` | Clears lease fields and error fields. |
| `error` | `available` | Clears lease fields, stores `last_error`. |
| `rate_limited` | `rate_limited` | Requires `flood_wait_seconds`; sets `flood_wait_until`. |
| `banned` | `banned` | Clears lease fields and stores `last_error`. |

Releasing with a mismatched `job_id` is a no-op and should be logged as a warning.

Workers must call `release_account()` in a `finally` block when a lease was acquired.

## Telegram Error Mapping

| Error | Account outcome | Worker outcome |
|---|---|---|
| `FloodWaitError` | `rate_limited` with wait seconds | Requeue or retry later according to queue spec. |
| banned/deauthorized session | `banned` | Fail job and alert operator. |
| auth key invalid | `banned` or `error` depending on cause | Fail job and alert operator if manual action needed. |
| transient network error | `error` | Retry job according to queue spec. |
| community inaccessible/private | `success` | Worker records community state; account is healthy. |

## Lease Duration

Default lease duration: 15 minutes.

Long collection jobs may extend leases by calling a future `heartbeat_account_lease()` helper. MVP workers should keep jobs small enough that the default lease is sufficient.

## No Account Available

`NoAccountAvailable` means all accounts in the required pool are currently leased, banned,
rate-limited, disabled, or missing.

The worker must not busy-loop. Queue behavior:

- expansion: retry later with backoff.
- community snapshot or collection: retry later or let the next scheduler tick pick it up.
- engagement join/send: retry later or alert the operator that no engagement account is available.

## Operator Alerts

The account manager emits alert events or logs for:

- account banned/deauthorized.
- all accounts unavailable.
- repeated stale lease recovery for the same account.

The bot may expose these alerts through API debug/status endpoints.

## Local Account Onboarding

Telegram user accounts can be onboarded from the bot or manually by the operator. The bot workflow
is the primary operator path; `scripts/onboard_telegram_account.py` remains a safe local fallback.

Bot workflow:

1. The accounts cockpit `Add search` and `Add engagement` buttons start a guided flow that prompts
   for phone number, optional account name, and optional notes. `/add_account <search|engagement> <phone>
   [session_name] [notes...]` remains available for fast operator entry.
2. The bot validates the pool and safe session name.
3. The backend sends the Telegram login code through Telethon and creates the session under
   `SESSIONS_DIR`.
4. The bot consumes the next operator text message as the login code. If Telegram requires 2FA, it
   consumes the next text message as the 2FA password.
5. Optional account-name and notes prompts expose a `Skip` button; prompts keep copy limited to the
   current required action and one human-readable example.
6. After successful registration, the bot waits about 3 seconds, then attempts to delete the setup,
   login-code, and password messages from the completed flow.
7. The backend validates authorization and upserts the `telegram_accounts` row with
   `status = 'available'`.

Sensitive-message deletion is best-effort. Operators must still use dedicated Telegram accounts and
only run onboarding in allowlisted operator chats.

The local workflow:

1. Read `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `SESSIONS_DIR`, and `DATABASE_URL`.
2. Prompt for or accept a phone number.
3. Create or validate a Telethon `.session` file under `SESSIONS_DIR`.
4. Upsert the matching `telegram_accounts` row with `status = 'available'`.
5. Store the intended `account_pool`; default to `search` unless the operator explicitly chooses
   `engagement`.

The script stores only the operational account phone and session path in `telegram_accounts`.
It must not collect Telegram community member phone numbers.

Session file rules:

- Store relative session file names in `telegram_accounts.session_file_path`.
- Reject path separators and traversal in operator-provided session names.
- Keep session files inside `SESSIONS_DIR`.

## Account Safety And Health

Telegram user accounts used by Telethon should be treated as scarce operational identities, not
throwaway credentials. Telegram's official API docs state that API client libraries are monitored
for abuse, `FLOOD_WAIT` means the client must wait before repeating an action, and API access must
not be used for spam, flooding, fake subscriber/view activity, or unauthorized data aggregation.

Baseline operating rules:

- Use dedicated Telegram accounts, never the operator's main personal account.
- Keep search-pool accounts read-only for discovery, expansion, entity intake, community snapshots,
  and any future legacy read-only collection.
- Keep engagement-pool accounts out of broad search and discovery snapshot work. Approved
  engagement collection and `engagement_target.resolve` are the engagement-specific read-only
  exceptions because they depend on the same public-facing identity later used to join or reply.
- Engagement is the only planned exception to read-only use. It must be explicitly enabled through
  the engagement module, stay public, require operator approval in the MVP, and write audit logs.
- No outreach DMs, promotional mass joins, vote manipulation, or subscriber/view inflation.
- Enable a strong Telegram 2FA password and recovery email before onboarding.
- Keep each Telethon `.session` file private. Treat it like an account password.
- Use stable infrastructure. Avoid repeatedly logging the same account in from many hosts, IPs, or
  regenerated session files.
- Start new accounts slowly with a tiny seed batch before larger resolution or snapshot runs.
- Do not join many groups quickly. Prefer public username/link resolution and snapshots from
  communities where access is already allowed.
- Never collect phone numbers, never assign person-level scores, and never use collected data to
  train, fine-tune, or build machine-learning models.

Healthy account behavior:

- One leased job per account at a time.
- Conservative snapshot windows and member limits.
- Let `rate_limited` accounts rest until `flood_wait_until`.
- Investigate repeated `last_error` values before retrying more work.
- Keep at least one spare `available` account when running recurring snapshots or collection.
- Keep engagement send limits much lower than collection/expansion throughput.

Risk indicators:

- Frequent `FloodWaitError` or long `flood_wait_until` values.
- Repeated auth/session errors such as revoked, deauthorized, duplicated, or invalid auth keys.
- Sudden private/inaccessible results across many unrelated communities.
- Telegram `@SpamBot` reports that the account is limited.

Manual recovery:

- `rate_limited`: do not replace the session or keep retrying. Wait until the recorded time.
- `banned` or deauthorized: log in manually with official Telegram clients, check `@SpamBot`, and
  resolve the account before returning it to `available`.
- compromised session suspicion: revoke the session in Telegram settings, delete the local session
  file, mark the database row unusable, and onboard a fresh session only after the account is safe.

Recommended pool size for the beginning:

- Start with at least one search account and one warm spare search account for read-only work.
- Add at least one separate engagement account before enabling joins or sends.
- Add all accounts through `scripts/onboard_telegram_account.py` so each has a session, a row in
  `telegram_accounts`, and the correct `account_pool`.
- Keep worker concurrency low enough that the pool normally has at least one account not `in_use`.
- Scale only after observing several successful seed-resolution and snapshot cycles without
  `rate_limited` or account-level auth errors.

## Safety Rules

- Never lease banned accounts automatically.
- Never lease an account from the wrong pool for a job purpose.
- Never lease disabled accounts automatically.
- Never collect phone numbers.
- Never share a Telethon session across concurrent jobs.
- Never mark a Telegram account healthy after account-level auth errors.
