# Collection Spec

## Purpose

Collection gathers public Telegram community data from imported seed communities and
operator-approved monitored communities.

The collection worker fetches data, writes durable collection artifacts, prepares compact analysis
input, and stops. It does not decide whether a community is relevant.

## Inputs

`collection.run` receives:

```json
{
  "community_id": "uuid",
  "reason": "scheduled|manual|initial",
  "requested_by": "telegram_user_id_or_operator|null",
  "window_days": 90
}
```

For the bare seed-import slice, `reason = "initial"` is used when `seed.resolve` queues collection
for a resolved seed community.

## Responsibilities

- Acquire a Telegram account lease through the account manager.
- Fetch available metadata and visible members.
- Fetch public messages for the collection window only when the message-collection path is enabled.
- Update normalized user records when Telegram users are visible.
- Update `community_members` activity counts for the rolling window.
- Write one `community_snapshots` row.
- Write one `collection_runs` row.
- Write compact capped `collection_runs.analysis_input`.
- Write raw `messages` rows only when `communities.store_messages = true`.
- Enqueue `analysis.run` after successful message collection. For metadata/member-only seed
  collection, set `collection_runs.analysis_status = 'skipped'`.

## Non-Responsibilities

- No OpenAI calls.
- No relevance scoring.
- No final topic classification.
- No outreach behavior.
- No business logic beyond collection persistence and capped analysis input preparation.

## Default Raw Message Policy

Raw message storage is opt-in.

The bare seed-import slice does not fetch messages yet. It writes community metadata, a snapshot,
visible members, and a completed collection run with analysis skipped.

When `communities.store_messages = false`:

- messages are fetched in memory
- activity counts and compact analysis input are persisted
- raw messages are discarded
- no `messages` rows are written

When `communities.store_messages = true`:

- the same aggregation path runs
- raw message rows are also written to `messages`

## Analysis Input

The analysis input lives on `collection_runs.analysis_input` and must follow the queue spec envelope.

Rules:

- no full message history
- no phone numbers
- no person-level scores
- no unnecessary Telegram user identity
- maximum 100 message examples
- maximum 500 characters per message example
- recommended maximum serialized size: 256 KB

## Inaccessible Communities

If a monitored community becomes inaccessible:

- record the collection failure or dropped state clearly
- treat it as a community access issue, not an account-health issue
- do not mark the Telegram account unhealthy unless the error is account-level

## Safety Rules

- No business logic in collection.
- Phone numbers are never collected.
- Person-level scoring is forbidden.
- OpenAI calls happen only in analysis, not collection.
