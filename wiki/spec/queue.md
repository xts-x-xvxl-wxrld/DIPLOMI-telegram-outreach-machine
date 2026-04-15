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
| `default` | discovery, expansion | Normal |
| `scheduled` | recurring collection | Lower |
| `analysis` | analysis jobs | Normal, isolated from Telegram account usage |

Analysis has its own queue because it uses OpenAI API calls and does not need Telegram accounts.

## Job Types

### `discovery.run`

Triggered by the API after an audience brief is created or when the operator manually starts discovery.

Payload:

```json
{
  "brief_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "limit": 50
}
```

Writes:

- `communities` rows with `status = 'candidate'`
- `source = 'tgstat'`
- `brief_id`
- `match_reason`

May enqueue:

- `expansion.run` for promising seed communities, if enabled by API request or config.

### `expansion.run`

Triggered after discovery or manually for selected communities.

Payload:

```json
{
  "brief_id": "uuid",
  "community_ids": ["uuid"],
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="expansion")`

Writes:

- additional `communities` rows with `source = 'expansion'`
- updated metadata for inspected communities

May enqueue:

- no automatic collection. Operator approval is required first.

### `collection.run`

Triggered by scheduler for monitored communities or manually by the operator.

Payload:

```json
{
  "community_id": "uuid",
  "reason": "scheduled|manual|initial",
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

- `analysis.run` with `{ "collection_run_id": "uuid" }`

Important:

Collection does not pass raw message batches through Redis. It writes a compact, capped `collection_runs.analysis_input` artifact and enqueues analysis by ID.

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
- `audience_briefs`

Writes:

- `analysis_summaries`
- updates `collection_runs.analysis_status`

Rules:

- OpenAI calls happen only in analysis jobs.
- Analysis creates community-level summaries and relevance scores only.
- No person-level scoring or ranking.

## Job Chain

```text
brief created
  -> discovery.run
  -> optional expansion.run
  -> operator approves communities
  -> collection.run
  -> analysis.run
```

Recurring monitored flow:

```text
scheduler tick
  -> collection.run for due monitored communities
  -> analysis.run for each successful collection run
```

## Collection Runs

`collection_runs` is the durable boundary between collection and analysis.

Collection stores:

- community ID
- brief ID
- collection window
- aggregate counts
- compact analysis input
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

Approved communities enter `status = 'monitoring'`.

Scheduler runs every 30-60 minutes and enqueues `collection.run` for communities where:

- `status = 'monitoring'`
- no collection job is currently queued/running for that community
- `last_snapshot_at` is older than the configured interval

Default interval: 60 minutes.

Manual collection uses the `high` queue and bypasses the interval check, but still avoids duplicate active jobs for the same community.

## Duplicate Prevention

Job IDs should be deterministic where useful:

```text
collection:{community_id}:{yyyyMMddHH}
analysis:{collection_run_id}
```

Before enqueueing collection, the scheduler checks whether an active RQ job already exists for the same community.

## Retry Policy

| Job | Retry count | Backoff | Notes |
|---|---:|---|---|
| `discovery.run` | 3 | 1m, 5m, 15m | TGStat/network failures. |
| `expansion.run` | 3 | 5m, 15m, 60m | Telegram account and network failures. |
| `collection.run` | 2 | 10m, 30m | Scheduler will also retry on future ticks. |
| `analysis.run` | 3 | 1m, 5m, 30m | OpenAI/network failures. |

## Special Failures

### `NoAccountAvailable`

No account is healthy and available.

- expansion: retry with backoff.
- scheduled collection: retry once, then let future scheduler ticks handle it.
- manual collection: retry with backoff and expose status to API.

### `FloodWaitError`

Worker releases the account as `rate_limited` with `flood_wait_seconds`.

The job is rescheduled after the larger of:

- the flood wait duration
- the normal retry backoff

### Banned or Deauthorized Account

Worker releases the account as `banned`.

The current job may retry if other accounts are available. The account issue is exposed through API debug/status endpoints.

### Community Inaccessible

Collection records the community as inaccessible or dropped according to the worker spec.

This is not an account failure.

## Job Metadata

RQ job `meta` should include:

```json
{
  "job_type": "collection.run",
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

- Discovery may call TGStat, not Telethon.
- Expansion may call Telethon and uses the account manager.
- Collection may call Telethon and uses the account manager.
- Analysis may call OpenAI, not Telethon.
- Collection performs fetching and persistence only; relevance decisions happen in analysis.
