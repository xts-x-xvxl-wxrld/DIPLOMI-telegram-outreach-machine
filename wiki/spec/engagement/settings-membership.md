# Engagements, Settings, And Membership

Engagement entity, settings, topic, and account-membership contracts
used by engagement workers and APIs.

## Engagements

Engagement is a first-class backend entity.

An engagement is not just a community plus global topics. It is the operator's
chosen target, chosen topic, chosen account, and sending mode bundled into
one durable record.

Recommended table: `engagements`

```sql
id                   uuid PRIMARY KEY
target_id            uuid NOT NULL REFERENCES engagement_targets(id)
community_id         uuid NOT NULL REFERENCES communities(id)
topic_id             uuid REFERENCES engagement_topics(id)
status               text NOT NULL DEFAULT 'draft'
                     -- draft | active | paused | archived
name                 text
created_by           text NOT NULL
created_at           timestamptz NOT NULL DEFAULT now()
updated_at           timestamptz NOT NULL DEFAULT now()

UNIQUE (target_id)
```

Rules:

- A finished operator-visible engagement row must exist before the engagement
  appears in `My engagements`.
- A draft engagement may exist during wizard setup and remain hidden from the
  operator list until confirmed.
- Target approval remains a separate allowlist concept, but the engagement row
  is the primary operator object.
- One engagement maps to one topic in the first version.
- Draft engagements may temporarily have `topic_id = null`, but activation may
  not.

## Engagement Settings

Each engagement has explicit engagement settings.

Recommended table: `engagement_settings`

```sql
id                         uuid PRIMARY KEY
engagement_id              uuid NOT NULL REFERENCES engagements(id)
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

UNIQUE (engagement_id)
```

Mode meanings:

| Mode | Meaning |
|---|---|
| `disabled` | Do not join, detect, draft, or send. |
| `observe` | Reserved observe-only mode. In the current MVP, detection exits early without drafting or creating reply opportunities. |
| `suggest` | Draft reply opportunities for operator review. |
| `require_approval` | Operator approval is required before every send. |
| `auto_limited` | Tightly capped automatic replies after explicit operator setup. |

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

- `engagement_id` must reference an existing engagement.
- `mode = disabled` forces `allow_join = false` and `allow_post = false`.
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

`get_engagement_settings` returns a disabled synthetic view when no row exists.
It should not create a database row just because the operator viewed settings.
Worker-facing community lookups should prefer the active task-first `engagement_settings`
row for that community and fall back to legacy `community_engagement_settings`
only for compatibility while old control surfaces are retired.

## Engagement Topic

Chosen topic belongs to an engagement, not just to a global active-topic pool.

Rules:

- An engagement with no chosen topic should raise `Topics not chosen`.
- Topic library rows remain reusable global topic definitions.
- Topic choice is engagement-specific even though topic definitions are shared.

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

1. If `engagement_settings.assigned_account_id` is set, use that account only if it is in
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
