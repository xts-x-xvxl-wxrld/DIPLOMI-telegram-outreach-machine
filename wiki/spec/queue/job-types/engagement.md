# Queue Engagement Jobs

Active engagement queue and worker seam contract extracted from code and
tests.

This doc is part of the extracted active contract set:

- `wiki/spec/api/engagement.md`
- `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`
- `wiki/spec/queue/job-types/engagement.md`
- `wiki/spec/database/engagement.md`

## Scope

Active engagement queue seams are:

- engagement collection via the generic `collection` job family
- community join
- manual target resolve
- detect
- send
- the detection and collection schedulers that enqueue those jobs

Legacy admin-only engagement jobs outside this path are not part of this
extracted set.

## Payloads, Queues, And Job IDs

### `collection` with `reason = "engagement"`

Queue:

- `default`

Payload:

```json
{
  "community_id": "uuid",
  "reason": "engagement",
  "requested_by": "string|null",
  "window_days": 90
}
```

Deterministic job ID:

- `collection:engagement:{community_id}:{YYYYMMDDHHMM}`

Contract:

- this is the active collection seam for engagement communities
- duplicate minute-bucket collection jobs are safe and reported as
  `status = "duplicate"`
- the collection worker may choose the assigned engagement account when one is
  configured
- after a successful engagement collection run, the collection worker enqueues
  `engagement.detect`

### `community.join`

Queue:

- `default`

Payload:

```json
{
  "community_id": "uuid",
  "telegram_account_id": "uuid|null",
  "requested_by": "string"
}
```

Worker seam:

- preferred account order:
  - payload `telegram_account_id`
  - engagement settings `assigned_account_id`
  - any already joined membership for send
- worker records membership state in `community_account_memberships`
- worker also writes an `engagement_actions` join action row

Result mapping:

- `joined` or `already_joined`
  - membership -> `joined`
  - action -> `sent`
- failure
  - membership -> `failed`
  - action -> `failed` or `skipped` depending on failure mode

### `engagement_target.resolve`

Queue:

- `engagement`

Payload:

```json
{
  "target_id": "uuid",
  "requested_by": "string"
}
```

Deterministic job ID:

- `engagement_target.resolve:{target_id}`

Contract:

- resolves a manual engagement target into `community_id`
- does not create seed rows
- does not send messages

### `engagement.detect`

Queue:

- `engagement`

Payload:

```json
{
  "community_id": "uuid",
  "collection_run_id": "uuid|null",
  "window_minutes": 60,
  "requested_by": "string|null"
}
```

Job ID rules:

- with `collection_run_id`:
  - `{prefix}:{community_id}:{collection_run_id}`
- without `collection_run_id`:
  - hourly bucket `{prefix}:{community_id}:{YYYYMMDDHH}`

Prefixes in active use:

- scheduled or collection-triggered: `engagement.detect`
- manual confirm path: `engagement.detect.manual`

Contract:

- detection never sends messages
- detection creates or updates reply-opportunity rows in
  `engagement_candidates`
- collection-triggered detect prefers the exact collected message batch when
  `collection_run_id` is present

### `engagement.send`

Queue:

- `engagement`

Payload:

```json
{
  "candidate_id": "uuid",
  "approved_by": "string"
}
```

Deterministic job ID:

- `engagement.send:{candidate_id}`

Scheduling:

- the approval path reserves an `engagement_actions` reply row first
- send jobs are scheduled with a stable per-candidate jitter
- current jitter range is 45 to 120 seconds

Contract:

- one candidate maps to one idempotency key:
  - `engagement.send:{candidate_id}`
- retries must reuse the same action row when present
- already-sent actions must mark the candidate `sent` without a second network
  send

## Send Worker Preflight

`backend/workers/engagement_send.py` is authoritative for send eligibility.

Required candidate state:

- candidate exists
- candidate status is `approved`
- candidate is not expired by `expires_at`
- candidate is not stale by `reply_deadline_at`

Required engagement state:

- effective settings mode is not `disabled`
- posting is allowed either because:
  - settings `allow_post = true`
  - or the task-first operator-approved path is active
- approved target post permission is required unless the task-first operator
  send shortcut applies
- `require_approval = true`
- if `reply_only = true`, the candidate must have `source_tg_message_id`

Required membership/account state:

- a joined membership must exist
- post-join warmup must have elapsed
- worker acquires the exact joined account with `purpose = "engagement_send"`

Rate-limit and cadence checks:

- daily community send cap
- daily account send cap
- root/continuation opportunity cadence check
- community spacing window
- account spacing window

Outcome mapping:

- success
  - action -> `sent`
  - candidate -> `sent`
- send-limit skip
  - action -> `skipped`
  - candidate stays `approved`
- validation failure or empty final reply
  - action -> `skipped`
  - candidate -> `failed`
- message not replyable
  - action -> `skipped`
  - candidate -> `expired`
- account banned or unexpected worker failure
  - action -> `failed`

## Scheduler Seams

### Detection scheduler

Summary job type:

- `engagement.scheduler`

Current defaults:

- detection window: `60` minutes
- scheduler interval setting: `3600` seconds

Detection scheduler enqueues `engagement.detect` with:

- `requested_by = null`
- `window_minutes = settings.engagement_detection_window_minutes`

Detection target is eligible only when:

- effective mode is one of:
  - `observe`
  - `suggest`
  - `require_approval`
- a recent engagement collection exists within the detection window
- no active candidate currently exists
- community is not inside quiet hours

### Collection scheduler

Summary job type:

- `engagement.collection_scheduler`

Current default:

- active collection interval setting: `180` seconds

Collection scheduler enqueues `collection` with:

- `reason = "engagement"`
- `requested_by = null`

Collection target is eligible only when:

- effective settings are not disabled
- at least one approved target for the community has detect permission
- no active engagement collection run is already open
- due-state says the community is due
- community is not inside quiet hours

Duplicate collection jobs:

- are treated as safe
- increment `duplicate_jobs`
- still record the deterministic job ID
