# Engagement Settings And Membership

Community settings and account membership contracts used by engagement workers and APIs.

## Community Settings

Each community has explicit engagement settings. Absence of settings means engagement is disabled.

Recommended table: `community_engagement_settings`

```sql
id                         uuid PRIMARY KEY
community_id               uuid NOT NULL REFERENCES communities(id)
mode                       text NOT NULL DEFAULT 'suggest'
                           -- disabled | observe | suggest | require_approval | auto_limited
allow_join                 boolean NOT NULL DEFAULT false
allow_post                 boolean NOT NULL DEFAULT false
reply_only                 boolean NOT NULL DEFAULT true
require_approval           boolean NOT NULL DEFAULT true
max_posts_per_day          int NOT NULL DEFAULT 1
min_minutes_between_posts  int NOT NULL DEFAULT 240
quiet_hours_start          time
quiet_hours_end            time
assigned_account_id        uuid REFERENCES telegram_accounts(id)
created_at                 timestamptz NOT NULL DEFAULT now()
updated_at                 timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id)
```

Mode meanings:

| Mode | Meaning |
|---|---|
| `disabled` | Do not join, detect, draft, or send. |
| `observe` | Reserved observe-only mode. In the current MVP, detection exits early without drafting or creating reply opportunities. |
| `suggest` | Draft reply opportunities for operator review. |
| `require_approval` | Operator approval is required before every send. |
| `auto_limited` | Future mode for tightly capped automatic replies after policy is proven safe. |

MVP default:

```text
mode = suggest
allow_join = false
allow_post = false
reply_only = true
require_approval = true
max_posts_per_day = 1
min_minutes_between_posts = 240
```

Validation contract:

- `community_id` must reference an existing community.
- `mode = disabled` forces `allow_join = false` and `allow_post = false`.
- MVP rejects `mode = auto_limited`.
- MVP rejects `require_approval = false`.
- MVP rejects `reply_only = false`.
- `max_posts_per_day` must be between 0 and 3 in MVP.
- `min_minutes_between_posts` must be at least 60 in MVP.
- If one quiet-hour value is provided, both must be provided.
- `assigned_account_id`, when provided, must reference an account that is not banned.
- `assigned_account_id`, when provided, must reference an account in the `engagement` account pool
  defined by `wiki/spec/telegram-account-pools.md`.
- Only communities with `status IN ('approved', 'monitoring')` may enable `allow_join` or
  `allow_post`.

Service contract:

```python
def get_engagement_settings(db, community_id: UUID) -> EngagementSettingsView:
    ...

def upsert_engagement_settings(
    db,
    *,
    community_id: UUID,
    payload: EngagementSettingsUpdate,
    updated_by: str,
) -> EngagementSettingsView:
    ...
```

`get_engagement_settings` returns a disabled synthetic view when no row exists. It should not create
a database row just because the operator viewed settings.

## Account Memberships

The app must track which managed account has joined which community. It should not join every
account to every community.

Recommended table: `community_account_memberships`

```sql
id                   uuid PRIMARY KEY
community_id          uuid NOT NULL REFERENCES communities(id)
telegram_account_id   uuid NOT NULL REFERENCES telegram_accounts(id)
status                text NOT NULL DEFAULT 'not_joined'
                      -- not_joined | join_requested | joined | failed | left | banned
joined_at             timestamptz
last_checked_at       timestamptz
last_error            text
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()

UNIQUE (community_id, telegram_account_id)
```

Rules:

- One account is selected for a community unless the operator explicitly changes it.
- Joining uses the account manager with an engagement purpose.
- `FloodWaitError` marks the account rate-limited through the account manager.
- Community-level access failures update the membership row, not the account health, unless the
  error is account-level.

Selection contract:

1. If `community_engagement_settings.assigned_account_id` is set, use that account only if it is in
   the `engagement` account pool.
2. Else if a `joined` membership already exists for the community with an `engagement` account, use
   that account.
3. Else acquire any healthy `engagement` account through the account manager.
4. After a successful join, write or update the membership row.

The first implementation should prefer one joined account per community. Multiple joined accounts
are allowed in the schema for future manual operator actions, but workers must not create them
automatically.

Service contract:

```python
def mark_join_requested(
    db,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
) -> CommunityAccountMembership:
    ...

def mark_join_result(
    db,
    *,
    community_id: UUID,
    telegram_account_id: UUID,
    status: Literal["joined", "failed", "banned"],
    joined_at: datetime | None,
    error_message: str | None,
) -> CommunityAccountMembership:
    ...

def get_joined_membership_for_send(
    db,
    *,
    community_id: UUID,
) -> CommunityAccountMembership | None:
    ...
```
