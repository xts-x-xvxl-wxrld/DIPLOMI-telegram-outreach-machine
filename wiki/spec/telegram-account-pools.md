# Telegram Account Pool Separation Spec

## Purpose

Telegram accounts must be separated by operational role so read-only discovery/search work never
uses the same identity that joins communities and posts public engagement replies.

The app should treat account identity as part of product safety:

```text
search account       -> read-only Telegram lookup, expansion, community snapshots, and collection
engagement account   -> approved joining and approved public replies
disabled account     -> never leased automatically
```

This spec extends `wiki/spec/account-manager.md`, `wiki/spec/database.md`, and
`wiki/spec/engagement.md`.

## Goals

- Prevent the same Telegram identity from being used for both broad search/snapshot work and public
  engagement.
- Keep search accounts read-only.
- Keep engagement accounts stable and recognizable in communities where they are approved to speak.
- Make account pool selection a hard backend rule, not a bot/UI convention.
- Default all existing accounts to the safer read-only search pool during migration.
- Keep the model simple in the first implementation: one pool field, not a large permissions matrix.

## Non-Goals

- No automatic creation of Telegram accounts.
- No automatic promotion of existing search accounts into engagement accounts.
- No per-account fine-grained capability matrix in the first implementation.
- No direct messages, mass joining, top-level posting, or auto-send behavior.
- No weakening of existing account lease, health, flood-wait, or audit rules.

## Account Pools

Add a durable `telegram_accounts.account_pool` value.

Allowed values:

| Pool | Meaning |
|---|---|
| `search` | Read-only account for seed resolution, expansion, entity intake, target resolution, community snapshots, and collection. |
| `engagement` | Public-facing account for approved community joins and approved public replies. |
| `disabled` | Account is kept in the database but is never automatically leased. |

`account_pool` is separate from `status`.

`status` answers:

```text
Is this account currently available, in use, rate-limited, or banned?
```

`account_pool` answers:

```text
What kind of work is this account allowed to perform?
```

## Purpose To Pool Mapping

The account manager must map every lease purpose to exactly one required pool.

| Purpose | Required pool | Notes |
|---|---|---|
| `expansion` | `search` | Includes seed resolution and graph expansion. |
| `community_snapshot` | `search` | Discovery metadata/member snapshots remain read-only. |
| `collection` | `search` | Engagement message collection remains read-only until a later spec routes it differently. |
| `entity_intake` | `search` | Direct Telegram handle classification is read-only. |
| `engagement_target_resolve` | `search` | Resolves engagement targets but does not join or post. |
| `engagement_join` | `engagement` | Joins only approved engagement targets. |
| `engagement_send` | `engagement` | Sends only approved public replies. |

`engagement.detect` does not require a Telegram account in the MVP. It reads recent collection
artifacts and may call OpenAI.

There must be no automatic fallback between pools. If an engagement account is unavailable,
`engagement_join` and `engagement_send` must fail or retry with `NoAccountAvailable` rather than
using a search account.

## Database Contract

Update `telegram_accounts`:

```sql
account_pool text NOT NULL DEFAULT 'search'
             -- search | engagement | disabled
```

Recommended indexes:

```sql
CREATE INDEX ON telegram_accounts (account_pool, status, last_used_at);
```

Migration rules:

- Existing accounts become `account_pool = 'search'`.
- No existing account is automatically marked `engagement`.
- `disabled` accounts are excluded from all automatic lease queries even when `status = 'available'`.
- Existing `community_account_memberships` remain historical rows, but `engagement.send` must reject
  memberships whose account is not in the `engagement` pool.

## Account Manager Contract

`acquire_account()` must:

1. Validate the purpose.
2. Resolve the required pool from the purpose.
3. Recover stale leases without changing account pools.
4. Select only accounts where:

```sql
telegram_accounts.account_pool = required_pool
AND (
  status = 'available'
  OR (status = 'rate_limited' AND flood_wait_until <= now())
)
```

5. Mark the selected account `in_use` as today.

`acquire_account_by_id()` must apply the same pool check. An explicit `account_id` must not bypass
pool separation.

`NoAccountAvailable` should include enough context for logs, for example:

```text
No Telegram account is available for pool engagement
```

The public account-manager purpose list must include `engagement_target_resolve`; that purpose is
read-only and belongs to the `search` pool.

## Engagement Assignment Contract

Engagement account selection must be stable per community.

Selection order:

1. If `community_engagement_settings.assigned_account_id` is set, use it, but only if it points to
   an `engagement` account.
2. Else if a `joined` membership exists for an `engagement` account, use that account.
3. Else acquire the least-recently-used healthy account from the `engagement` pool.
4. After a successful join, store the membership. A later implementation may also set
   `assigned_account_id` automatically after first successful join, but it must not switch identities
   silently for a community that already has a joined engagement account.

Validation rules:

- `assigned_account_id` must reference an existing non-banned account in the `engagement` pool.
- `community.join` must reject an explicitly supplied search account.
- `engagement.send` must reject a membership if the membership account is not in the `engagement`
  pool, even if that membership was created before pool separation.
- Search workers must never use `assigned_account_id`; it is engagement-only state.

## Target Resolution Contract

`engagement_target.resolve` is engagement-specific in what it writes, but read-only in how it uses
Telegram. It must use a `search` account because it only resolves a submitted username/link into a
community row and target state.

Target resolution must not:

- join the target community
- post messages
- create seed groups
- mark the target approved for engagement

## Onboarding And Admin Contract

`scripts/onboard_telegram_account.py` should require or accept an account-pool choice.

Recommended CLI:

```text
--account-pool search|engagement
```

Default behavior for non-interactive onboarding should be `search` unless the operator explicitly
passes `--account-pool engagement`.

Bot/API account admin surfaces may expose pool changes later, but pool changes should be auditable.
Changing a search account to engagement should be a deliberate operator action and should warn if
the account has recent search/collection usage.

## Safety Invariants

- A search account must never join a community for engagement.
- A search account must never send a public reply.
- An engagement account must never be used for broad seed resolution, expansion, entity intake, or
  collection.
- A disabled account must never be leased automatically.
- An explicit account ID must not bypass pool restrictions.
- A joined historical membership is not enough to send; the account must also be in the
  `engagement` pool.
- Detection remains accountless in the MVP.

## Testing Contract

Minimum tests for implementation:

- Migration defaults existing accounts to `search`.
- Account manager leases only accounts from the required pool for each purpose.
- `engagement_target_resolve` is accepted as an account purpose and uses the `search` pool.
- `acquire_account_by_id()` rejects an account from the wrong pool.
- `disabled` accounts are never leased.
- Collection/expansion/entity-intake workers do not receive engagement accounts.
- `community.join` cannot use a search account, including explicit account IDs.
- `engagement.send` rejects historical joined memberships backed by search accounts.
- Engagement settings reject `assigned_account_id` values from the search or disabled pools.
- Onboarding can create both search and engagement accounts, with search as the safe default.

## Rollout Plan

1. Add `account_pool` to the database with default `search`.
2. Update models, schemas, account-manager purpose validation, and lease filtering.
3. Add `engagement_target_resolve` to the account-manager purpose list and map it to `search`.
4. Update engagement settings validation and join/send preflights.
5. Update onboarding and any account admin output.
6. Add tests for pool routing, explicit-account rejection, and historical membership handling.
7. Manually mark intended public-facing accounts as `engagement`.

## Open Questions

- Should first successful engagement join automatically set `assigned_account_id`, or should the
  setting remain purely operator-managed?
- Should the bot expose account pool changes immediately, or should pool changes remain script/API
  only until account admin UX is broader?
- Should the app show a warning when an engagement target has only search-account historical
  memberships?
