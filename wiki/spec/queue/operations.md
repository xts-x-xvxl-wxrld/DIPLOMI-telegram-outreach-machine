# Queue Operations

Job chains, scheduling, duplicate prevention, retry, failure, metadata, retention, and worker boundary contracts.

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
| `default` | seed resolution, seed batch expansion, direct handle classification, query-driven search planning/retrieval/ranking, optional brief processing, optional discovery, expansion | Normal |
| `scheduled` | recurring collection | Lower |
| `analysis` | analysis jobs | Normal, isolated from Telegram account usage |
| `engagement` | engagement target resolution, optional topic detection, and operator-approved sends | Conservative, isolated outbound behavior |

Analysis has its own queue because it uses OpenAI API calls and does not need Telegram accounts.
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
search.plan:{search_run_id}
search.retrieve:{search_run_id}:{search_query_id}
search.rank:{search_run_id}:{ranking_version_or_reason}
```

Before enqueueing a snapshot or collection job, the scheduler checks whether an active RQ job already
exists for the same community.
## Retry Policy

| Job | Retry count | Backoff | Notes |
|---|---:|---|---|
| `brief.process` | 3 | 1m, 5m, 15m | OpenAI/network/structured-output failures. |
| `discovery.run` | 3 | 1m, 5m, 15m | Web-search, Telegram search, or network failures. |
| `search.plan` | 2 | 1m, 5m | Deterministic validation should fail fast without retry. |
| `search.retrieve` | 3 | 5m, 15m, 60m | Telegram account, flood wait, and network failures. |
| `search.normalize` | 2 | 1m, 5m | Reserved until raw-output normalization is split out. |
| `search.rank` | 2 | 1m, 5m | Pure database recompute; should usually be deterministic. |
| `search.expand` | 3 | 5m, 15m, 60m | Deferred graph expansion from approved roots only. |
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
  "search_run_id": "uuid|null",
  "search_query_id": "uuid|null",
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
- Search planning may create deterministic queries, not OpenAI calls in the first implementation.
- Search retrieval may call Telegram search adapters through managed `search` pool accounts, not
  OpenAI or raw message collection.
- Search ranking may read search candidates/evidence/reviews, not Telegram, OpenAI, or web-search
  providers.
- Search expansion is deferred and, when enabled, may inspect graph evidence only from manual seeds
  or operator-promoted resolved search candidates.
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
