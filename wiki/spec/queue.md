# Queue Spec

## Purpose

The queue layer runs asynchronous backend work using RQ and Redis.

The API enqueues jobs. Workers consume jobs, write durable state to Postgres, and use Redis only for queueing and short-lived job metadata.

## Technology

- Queue: RQ
- Broker/result backend: Redis
- Worker process: Python worker container
- Scheduler: RQ Scheduler or an equivalent lightweight scheduler in the worker container

## Queue Names

| Queue | Job types | Priority |
|---|---|---|
| `high` | manual collection, manual analysis, operator-requested retries | Highest |
| `default` | seed resolution, seed batch expansion, direct handle classification, optional brief processing, optional discovery, expansion | Normal |
| `scheduled` | recurring collection | Lower |
| `analysis` | analysis jobs | Normal, isolated from Telegram account usage |
| `engagement` | engagement target resolution, optional topic detection, and operator-approved sends | Conservative, isolated outbound behavior |

Analysis has its own queue because it uses OpenAI API calls and does not need Telegram accounts.

## Job Types

### `brief.process`

Optional/future job triggered by the API after an audience brief is created.

Payload:

```json
{
  "brief_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "auto_start_discovery": true
}
```

Reads:

- `audience_briefs.raw_input`

Writes:

- `audience_briefs.keywords`
- `audience_briefs.related_phrases`
- `audience_briefs.language_hints`
- `audience_briefs.geography_hints`
- `audience_briefs.exclusion_terms`
- `audience_briefs.community_types`

May enqueue:

- `discovery.run`, if `auto_start_discovery = true` in a future brief-driven workflow

Rules:

- OpenAI calls are allowed in this job.
- The API must not call OpenAI directly.
- Discovery must not start automatically if structured output validation fails.
- The output is search guidance, not a relevance score.
- Briefs are not the active MVP discovery input; seed groups are primary.

### `discovery.run`

Optional/future job triggered after `brief.process` completes or when the operator manually starts
adapter-based discovery.

Payload:

```json
{
  "brief_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "limit": 50,
  "auto_expand": false
}
```

Writes:

- `communities` rows with `status = 'candidate'`
- `source = 'web_search'`, `source = 'telegram_search'`, `source = 'manual'`, or `source = 'expansion'`
- `brief_id`
- `match_reason`

May enqueue:

- `expansion.run` for promising seed communities, if enabled by API request or config.

MVP default:

- `discovery.run` is not on the primary MVP path.
- `auto_expand = false`.

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

### `community.join`

Optional future job for the engagement module. It joins one operator-approved community with one
managed Telegram account.

Payload:

```json
{
  "community_id": "uuid",
  "telegram_account_id": "uuid-or-null",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_join")`
- The account manager must lease only an `engagement` pool account for this purpose.

Rules:

- Engagement settings must allow joining.
- Private invite links are out of scope for MVP.
- Do not join multiple accounts unless the operator explicitly requests it.
- Record membership state and account outcomes through the engagement and account-manager specs.

### `engagement_target.resolve`

Engagement-specific resolver for manually submitted targets. It may reuse the Telegram entity
resolver adapter, but it writes `engagement_targets` state and must not write seed rows.

Payload:

```json
{
  "target_id": "uuid",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_target_resolve")`
- This purpose is read-only and must lease only a `search` pool account.

Reads:

- `engagement_targets`

Writes:

- `engagement_targets.status`
- `engagement_targets.community_id`
- `engagement_targets.last_error`
- `communities` for resolved channels/groups

Rules:

- No OpenAI calls.
- No seed groups or seed channels are created.
- Users and bots fail the target as non-community entities.
- Resolved communities still require explicit target approval before join/detect/send.

### `engagement.detect`

Engagement job that detects an approved topic moment and creates a reply opportunity for operator
review.

Payload:

```json
{
  "community_id": "uuid",
  "collection_run_id": "uuid|null",
  "window_minutes": 60,
  "requested_by": "telegram_user_id_or_operator|null"
}
```

May call OpenAI because it is an engagement worker, not collection. It must not send messages.

Rules:

- Prefer the exact engagement message batch from `collection_run_id` when present.
- Fall back to recent stored messages or compact collection artifacts for manual diagnostics and
  scheduler sweeps.
- Do not include unnecessary Telegram user identity in prompts.
- Do not create person-level scores.
- Create reply opportunities only when topic fit, timing, and usefulness are strong enough.

### `engagement.send`

Optional future job for the engagement module. It sends one operator-approved public reply.

Payload:

```json
{
  "candidate_id": "uuid",
  "approved_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_send")`
- The account manager must lease only the joined `engagement` pool account for this purpose.

Rules:

- Candidate must be approved.
- Community settings must allow posting.
- MVP sends replies only.
- Enforce account and community send limits.
- Write an `engagement_actions` audit row for sent, failed, and skipped outcomes.

## Job Chain

Primary seed-first flow:

```text
CSV uploaded
  -> seed rows imported
  -> seed.resolve
  -> community.snapshot for resolved seed communities
  -> metadata, snapshots, users, and community_members persisted
  -> optional operator review/monitoring later
```

Optional future brief-driven flow:

```text
brief created
  -> brief.process
  -> discovery.run
  -> optional expansion.run
  -> operator approves communities
  -> future analysis collection or community snapshot
  -> analysis.run
```

Recurring analysis collection flow:

```text
scheduler tick
  -> future analysis collection for due monitored communities
  -> analysis.run for each successful collection run
```

Engagement monitored flow:

```text
engagement collection tick
  -> collection.run with reason = engagement
  -> collection writes exact new-message batch
  -> engagement.detect with collection_run_id
  -> reply opportunity if a topic moment is strong enough
```

## Collection Runs

`collection_runs` is the durable boundary between collection and downstream readers such as analysis
and engagement detection.

Collection or snapshot jobs store:

- community ID
- brief ID
- collection window
- aggregate counts
- compact analysis input or compact engagement batch
- optional engagement message batch and checkpoint metadata
- expiration time for the analysis input

The analysis input should be compact and capped:

- no full message history
- no phone numbers
- no person-level scores
- no unnecessary Telegram user identity
- message examples truncated and sampled
- aggregate activity and topic signals preferred over raw text volume

Recommended MVP cap:

- maximum 100 message examples
- maximum 500 characters per message example
- maximum serialized `analysis_input` size of 256 KB

If the cap is exceeded, collection samples messages deterministically by recency and engagement signals.

Initial JSON envelope:

```json
{
  "schema_version": 1,
  "community": {
    "id": "uuid",
    "title": "string|null",
    "username": "string|null",
    "description": "string|null",
    "member_count": 123,
    "language": "string|null",
    "is_group": true,
    "is_broadcast": false
  },
  "brief": {
    "id": "uuid|null",
    "raw_input": "string|null",
    "keywords": [],
    "related_phrases": [],
    "language_hints": [],
    "geography_hints": [],
    "exclusion_terms": []
  },
  "window": {
    "days": 90,
    "start": "iso_datetime|null",
    "end": "iso_datetime"
  },
  "aggregate_activity": {
    "messages_seen": 0,
    "members_seen": 0,
    "active_members": 0,
    "passive_members": 0,
    "inactive_members": 0,
    "forwards_seen": 0,
    "media_messages_seen": 0,
    "polls_seen": 0,
    "avg_messages_per_day": 0.0
  },
  "sample_messages": [
    {
      "message_type": "text",
      "text": "truncated text",
      "message_date": "iso_datetime",
      "has_forward": false,
      "views": 0,
      "reactions_count": 0
    }
  ],
  "forward_sources": [
    {
      "source_tg_id": 123,
      "source_title": "string|null",
      "count": 3
    }
  ],
  "topic_hints": ["string"],
  "collection_notes": ["string"]
}
```

Rules:

- `sample_messages` must not include sender identifiers.
- Message text is truncated before writing `analysis_input`.
- `topic_hints` are extraction hints, not final relevance decisions.
- `collection_notes` may include operational caveats such as inaccessible history or partial collection.
- Analysis must tolerate missing optional fields.

## Scheduling

Discovery-reviewed communities may enter `status = 'monitoring'`.

The discovery snapshot scheduler, when enabled, enqueues `community.snapshot` for communities where:

- `status = 'monitoring'`
- no snapshot job is currently queued/running for that community
- `last_snapshot_at` is older than the configured interval

Default interval: 60 minutes.

Manual snapshots use the `high` queue and bypass the interval check, but still avoid duplicate active
jobs for the same community.

Engagement-enabled communities may use a shorter collection cadence, currently targeted at 10
minutes. Those collection runs should use `reason = "engagement"` and enqueue detection after commit
when the batch contains new messages and `allow_detect = true`.

## Duplicate Prevention

Job IDs should be deterministic where useful:

```text
community.snapshot:{community_id}:{yyyyMMddHH}
collection:{community_id}:{yyyyMMddHH}
collection:engagement:{community_id}:{yyyyMMddHHmm}
analysis:{collection_run_id}
engagement.detect:{community_id}:{collection_run_id}
```

Before enqueueing a snapshot or collection job, the scheduler checks whether an active RQ job already
exists for the same community.

## Retry Policy

| Job | Retry count | Backoff | Notes |
|---|---:|---|---|
| `brief.process` | 3 | 1m, 5m, 15m | OpenAI/network/structured-output failures. |
| `discovery.run` | 3 | 1m, 5m, 15m | Web-search, Telegram search, or network failures. |
| `seed.resolve` | 3 | 5m, 15m, 60m | Telegram account and network failures. |
| `seed.expand` | 3 | 5m, 15m, 60m | Telegram account and network failures. |
| `telegram_entity.resolve` | 3 | 5m, 15m, 60m | Telegram account and network failures. |
| `expansion.run` | 3 | 5m, 15m, 60m | Telegram account and network failures. |
| `community.snapshot` | 2 | 10m, 30m | Scheduler will also retry on future ticks. |
| `collection.run` | 2 | 10m, 30m | Engagement collection scheduler will also retry on future ticks. |
| `analysis.run` | 3 | 1m, 5m, 30m | OpenAI/network failures. |
| `community.join` | 2 | 10m, 60m | Telegram account and community access failures. |
| `engagement_target.resolve` | 3 | 5m, 15m, 60m | Telegram account and network failures. |
| `engagement.detect` | 2 | 5m, 15m | OpenAI/network failures; scheduler can retry on future ticks. |
| `engagement.send` | 1 | 10m | Operator-approved outbound action; avoid repeated sends. |

## Special Failures

### `NoAccountAvailable`

No account is healthy and available.

- expansion: retry with backoff.
- scheduled snapshot or engagement collection: retry once, then let future scheduler ticks handle it.
- manual snapshot or collection: retry with backoff and expose status to API.

### `FloodWaitError`

Worker releases the account as `rate_limited` with `flood_wait_seconds`.

The job is rescheduled after the larger of:

- the flood wait duration
- the normal retry backoff

### Banned or Deauthorized Account

Worker releases the account as `banned`.

The current job may retry if other accounts are available. The account issue is exposed through API debug/status endpoints.

### Community Inaccessible

Snapshot or collection records the community as inaccessible or dropped according to the worker spec.

This is not an account failure.

## Job Metadata

RQ job `meta` should include:

```json
{
  "job_type": "community.snapshot",
  "community_id": "uuid",
  "brief_id": "uuid|null",
  "started_at": "iso_datetime",
  "last_heartbeat_at": "iso_datetime",
  "status_message": "human readable short status"
}
```

The API may read RQ job metadata for operator-facing debug output. Durable business state must still live in Postgres.

## Result Retention

- Successful job results: keep for 24 hours.
- Failed job metadata: keep for 7 days.
- `collection_runs.analysis_input`: expires after 7 days by default, or sooner after successful analysis if retention pressure is high.

## Worker Boundaries

- Brief processing may call OpenAI, not Telegram search or Telethon.
- Discovery may call configured source adapters, not OpenAI or raw message collection.
- Seed resolution may call Telethon and uses the account manager.
- Direct handle classification may call Telethon and uses the account manager.
- Engagement target resolution may call Telethon and uses the account manager.
- Seed batch expansion may call Telethon and uses the account manager.
- Expansion may call Telethon and uses the account manager.
- Community snapshots may call Telethon and use the account manager.
- Engagement collection may call Telethon and uses the account manager.
- Analysis may call OpenAI, not Telethon.
- Engagement detection may call OpenAI and must not call Telethon in the MVP.
- Engagement join/send may call Telethon and use the account manager.
- Community snapshots and engagement collection perform fetching and persistence only; relevance
  decisions happen in analysis or engagement detection.
- Outbound Telegram behavior belongs only to the engagement module.
