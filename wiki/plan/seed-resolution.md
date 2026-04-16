# Seed Resolution Plan

## Goal

Turn imported manual seed rows into real `communities` rows that can be collected directly.

This is the bridge between CSV seed import and bare seed collection. Expansion is paused for now.

## Seed Field Contract

CSV import accepts one row per public Telegram community seed.

Required CSV fields:

- `group_name` - operator-facing bucket for related seeds.
- `channel` - public Telegram username or public Telegram link.

Optional CSV fields:

- `title` - operator-provided label before Telegram resolution.
- `notes` - operator-provided reason or context.

Accepted aliases:

- `group_name`: `group`, `seed_group`, `seed_group_name`, `name`
- `channel`: `username`, `link`, `url`, `telegram`, `telegram_link`
- `title`: `label`
- `notes`: `note`, `reason`

Accepted channel values:

- `@example_channel`
- `example_channel`
- `https://t.me/example_channel`
- `http://t.me/example_channel`
- `t.me/example_channel`
- `telegram.me/example_channel`
- `t.me/s/example_channel`

Rejected channel values:

- private invite links such as `https://t.me/+abc123`
- `joinchat` invite links
- non-public usernames
- malformed usernames
- phone numbers
- arbitrary URLs outside Telegram public username forms

Normalized seed fields:

- `raw_value` preserves the CSV value after trimming surrounding whitespace.
- `normalized_key` is `username:<casefolded_username>` and is unique within a seed group.
- `username` preserves the Telegram username spelling supplied by the operator, minus `@` or URL wrappers.
- `telegram_url` is `https://t.me/<username>`.
- `title` and `notes` remain operator metadata and must not override Telegram metadata unless the resolver cannot fetch a Telegram title.

## Seed Row Statuses

`seed_channels.status` is a text field with these application-level values:

- `pending` - imported and waiting for resolver work.
- `resolved` - resolver linked the row to `communities.id`.
- `invalid` - the row cannot be resolved because the seed format or target is unsupported.
- `inaccessible` - the target looked valid but Telegram could not access it.
- `not_community` - the target resolves to a user, bot, or other non-community entity.
- `failed` - transient resolver failure; retry may succeed later.

`community_id` must be set when status is `resolved`.

## Queue Contract

Add `seed.resolve`:

```json
{
  "seed_group_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "limit": 100,
  "retry_failed": false
}
```

The job resolves pending seed rows for one seed group. When `retry_failed = true`, it may also retry
rows in `failed` or `inaccessible` status.

## Resolver Writes

For each resolved seed row, write or update one `communities` row:

- `tg_id` from Telegram
- `username`
- `title`
- `description` when available
- `member_count` when available
- `is_group`
- `is_broadcast`
- `source = 'manual'`
- `status = 'candidate'` for new communities
- `match_reason = 'Imported manual seed: <seed_group.name>'`

Existing operator decisions must be preserved. If the community already exists as `rejected`,
`approved`, `monitoring`, or `dropped`, the resolver updates metadata but does not reset the status.

Then update the seed row:

- `status = 'resolved'`
- `community_id = communities.id`

## API Contract

Add:

- `POST /api/seed-groups/{seed_group_id}/resolve-jobs`

Request:

```json
{
  "limit": 100,
  "retry_failed": false
}
```

Response:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "seed.resolve",
    "status": "queued"
  }
}
```

If no rows are eligible, return `400` with `no_seed_channels_to_resolve`.

## Bot Contract

Add:

```text
/resolveseeds <seed_group_id>
```

This queues `seed.resolve`. `/seeds` should show both:

- resolve command for imported seed groups
- expand command for groups with resolved communities

## Non-Goals

- No retired external index dependency.
- No OpenAI calls.
- No expansion graph crawling during resolution.
- No raw message collection.
- No person-level scoring.
- No automatic joining of private communities.

## Current Seed Collection Behavior

After `seed.resolve` commits resolved communities, the worker queues one `collection.run` job per
unique resolved community with `reason = "initial"`. That collection job fetches metadata and
visible members, writes `users`, `community_members`, `community_snapshots`, and a completed
`collection_runs` row with analysis skipped.

## Implementation Steps

1. Add queue payload and enqueue helper for `seed.resolve`. Done.
2. Add API endpoint to queue seed resolution for a seed group. Done.
3. Add bot client method, command, and formatting. Done.
4. Implement Telethon resolver worker with account lease handling. Done.
5. Add tests for normalization, queue payloads, API command surface, and resolver persistence. Done.

## Implementation Notes

- `backend/services/seed_resolution.py` owns resolver persistence and is testable with a fake
  Telegram resolver adapter.
- `backend/workers/seed_resolve.py` leases one Telegram account with `purpose="expansion"` and
  releases it in success, error, rate-limit, and banned-session paths.
- `backend/workers/telegram_resolver.py` implements the Telethon adapter for public username
  entity resolution.
- `/seeds` now displays unresolved, resolved, and failed seed counts to make the operator path
  clearer before `/resolveseeds` and `/expandseeds`.
