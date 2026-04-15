# Account Manager Spec

## Purpose

The account manager coordinates a small pool of Telegram user accounts used by Telethon-based workers.

It is a Python utility module, not a separate service. Expansion and collection workers call it directly before making Telegram API calls.

## Responsibilities

- Lease one healthy Telegram account to one worker job at a time.
- Prevent concurrent use of the same account.
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
    purpose: Literal["expansion", "collection"],
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
WHERE (
    status = 'available'
    OR (status = 'rate_limited' AND flood_wait_until <= now())
)
ORDER BY last_used_at NULLS FIRST, added_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

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

`NoAccountAvailable` means all accounts are currently leased, banned, or rate-limited.

The worker must not busy-loop. Queue behavior:

- expansion: retry later with backoff.
- collection: retry later or let the next scheduler tick pick it up.

## Operator Alerts

The account manager emits alert events or logs for:

- account banned/deauthorized.
- all accounts unavailable.
- repeated stale lease recovery for the same account.

The bot may expose these alerts through API debug/status endpoints.

## Safety Rules

- Never lease banned accounts automatically.
- Never collect phone numbers.
- Never share a Telethon session across concurrent jobs.
- Never mark a Telegram account healthy after account-level auth errors.
