# Queue Seed Community And Collection Jobs

Detailed seed, expansion, snapshot, collection, and analysis job contracts.

### `seed.resolve`

Triggered when the operator wants imported manual seed rows resolved into real communities.

Payload:

```json
{
  "seed_group_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "limit": 100,
  "retry_failed": false
}
```

Uses:

- `account_manager.acquire_account(purpose="expansion")`

Reads:

- `seed_groups`
- `seed_channels` with `status = 'pending'`
- `seed_channels` with `status IN ('failed', 'inaccessible')` when `retry_failed = true`

Writes:

- `communities` rows for resolved public channels or groups
- `seed_channels.status`
- `seed_channels.community_id`

May enqueue:

- `community.snapshot` with `reason = "initial"` for each unique resolved seed community

Rules:

- No OpenAI calls.
- No retired external index calls.
- No expansion graph crawling.
- No raw message collection.
- Existing operator decisions on `communities.status` must be preserved.
- Resolution may update community metadata, but it must not reset rejected, approved, monitoring, or dropped communities back to candidate.
### `expansion.run`

Optional/future generic expansion job triggered after discovery or manually for selected
communities. Seed-first MVP expansion uses `seed.expand` instead.

Payload:

```json
{
  "brief_id": "uuid-or-null",
  "community_ids": ["uuid"],
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

Generic expansion may use `brief_id = null` when communities are not attached to a processed
audience brief.

Uses:

- `account_manager.acquire_account(purpose="expansion")`

Writes:

- additional `communities` rows with `source = 'expansion'`
- updated metadata for inspected communities

May enqueue:

- no automatic collection. Operator approval is required first.
### `telegram_entity.resolve`

Triggered when the operator sends one public Telegram username or link directly to the bot.

Payload:

```json
{
  "intake_id": "uuid",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="entity_intake")`

Reads:

- `telegram_entity_intakes`

Writes:

- `telegram_entity_intakes.status`
- `telegram_entity_intakes.entity_type`
- `telegram_entity_intakes.community_id` for channels/groups
- `telegram_entity_intakes.user_id` for users/bots
- `communities` for channels/groups
- `users` for users/bots

Rules:

- No OpenAI calls.
- Private invite links are rejected before enqueue.
- Users and bots must not receive person-level scores or phone fields.
- Communities remain candidates until operator review.
### `seed.expand`

Triggered when the operator wants graph expansion from an imported manual seed batch. This is the
primary MVP discovery job after seed resolution.

Payload:

```json
{
  "seed_group_id": "uuid",
  "brief_id": "uuid-or-null",
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="expansion")`

Reads:

- `seed_groups`
- `seed_channels` with `status = 'resolved'` and `community_id IS NOT NULL`
- the linked resolved `communities` rows

Writes:

- additional `communities` rows with `source = 'expansion'`
- updated metadata for inspected communities
- batch-aware `match_reason` values that include the seed group name and graph evidence
- `community_discovery_edges` provenance rows

Graph evidence:

- linked discussions
- forwarded-from channels/groups
- public Telegram links in text, captions, descriptions, and pinned messages
- public `@username` mentions

Candidate ordering:

- deterministic, evidence-based, and community-level only
- strengthened when the same candidate is found from multiple seeds in the same seed group
- used for operator review sorting, not as a stored person-level or outreach score

Rules:

- No OpenAI calls.
- No retired external index calls.
- No raw message collection.
- No expansion from unresolved seed rows.
- Existing operator decisions on `communities.status` must be preserved.
- The seed group is the expansion target; the worker must not treat `/expandseeds` as a generic
  arbitrary-community expansion request after resolving the initial community IDs.
- Expansion work must be capped per seed and per seed group to protect Telegram account health.
### `community.snapshot`

Discovery-side snapshot job triggered after seed resolution or manually by the operator.

Payload:

```json
{
  "community_id": "uuid",
  "reason": "manual|initial",
  "requested_by": "telegram_user_id_or_operator|null",
  "window_days": 90
}
```

Uses:

- `account_manager.acquire_account(purpose="community_snapshot")`

Writes:

- `users`
- `community_members`
- `community_snapshots`
- `collection_runs`

Rules:

- No OpenAI calls.
- No raw message intake.
- No reply opportunity detection.
- No analysis enqueue in the bare seed snapshot path.
- Phone numbers are never read or persisted.
- The job may write a `collection_runs` row as the durable run record for compatibility, with
  `analysis_status = 'skipped'`.
### `collection.run`

Engagement message-intake job triggered by the engagement collection scheduler or manually for an
approved engagement target.

Payload:

```json
{
  "community_id": "uuid",
  "reason": "engagement|manual",
  "requested_by": "telegram_user_id_or_operator|null",
  "window_days": 90
}
```

Uses:

- `account_manager.acquire_account(purpose="collection")`

Writes:

- `users`
- `community_members`
- `community_snapshots`
- `messages` only when `communities.store_messages = true`
- `collection_runs`

May enqueue:

- `analysis.run` with `{ "collection_run_id": "uuid" }` after message collection
- `engagement.detect` with `{ "community_id": "uuid", "collection_run_id": "uuid" }` after
  successful engagement collection

Important:

Collection does not pass raw message batches through Redis. It writes durable `collection_runs`
artifacts and enqueues analysis or detection by ID. For analysis, it writes a compact, capped
`collection_runs.analysis_input` artifact. For engagement detection, it writes an exact
new-message batch in the collection artifact or raw `messages` rows and passes `collection_run_id`.
Discovery community snapshots are handled by `community.snapshot`, not `collection.run`.
### `analysis.run`

Triggered after successful collection or manually for a collection run.

Payload:

```json
{
  "collection_run_id": "uuid",
  "requested_by": "telegram_user_id_or_operator|null"
}
```

Reads:

- `collection_runs.analysis_input`
- `communities`
- `audience_briefs` when a brief context is attached
- seed-group provenance when analysis later needs to explain how a community entered review

Writes:

- `analysis_summaries`
- updates `collection_runs.analysis_status`

Rules:

- OpenAI calls happen only in `brief.process` and `analysis.run`.
- Analysis creates community-level summaries and relevance scores only.
- No person-level scoring or ranking.
