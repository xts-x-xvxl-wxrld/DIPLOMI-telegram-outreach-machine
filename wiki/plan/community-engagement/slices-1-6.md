# Community Engagement Slices 1-6

Detailed early slices for contracts, schema, queue, account manager, API, and join worker.

## Slice 1: Wiki And Contracts

Status: completed.

Tasks:

- Add `wiki/spec/engagement.md`.
- Add this plan.
- Update `wiki/index.md`.
- Cross-link account manager, queue, API, and database specs so engagement is a known future module.

Acceptance:

- Future agents can see engagement as a separate module.
- Existing collection and analysis boundaries still forbid outbound behavior.
- Account safety rules explain that engagement is an explicit exception to read-only account use.
- The engagement spec defines status values, state transitions, DTOs, worker contracts,
  idempotency, rate limits, adapter interfaces, and testing expectations.
## Slice 2: Schema Foundation

Status: completed.

Add Alembic migration and SQLAlchemy models for:

- `community_engagement_settings`
- `community_account_memberships`
- `engagement_topics`
- `engagement_candidates`
- `engagement_actions`

Indexes:

- `community_engagement_settings(community_id)`
- `community_account_memberships(community_id, telegram_account_id)`
- `engagement_topics(active)`
- `engagement_candidates(status, created_at)`
- `engagement_candidates(community_id, topic_id, status)`
- `engagement_actions(community_id, created_at)`
- `engagement_actions(telegram_account_id, created_at)`

Acceptance:

- Migration upgrades and downgrades cleanly.
- Models validate known status values through Python enums.
- Tests cover default settings and uniqueness constraints.
## Slice 3: Queue Contracts

Status: completed.

Add payloads and enqueue helpers for:

- `community.join`
- `engagement.detect`
- `engagement.send`

Queue placement:

- `community.join`: default queue
- `engagement.detect`: engagement queue
- `engagement.send`: engagement queue

Acceptance:

- Payload tests cover required fields and JSON serialization.
- Worker dispatch recognizes the new job types.
- Job metadata includes community ID, candidate ID where relevant, and short status messages.
## Slice 4: Account Manager Extension

Status: completed.

Extend account manager purposes:

- `engagement_join`
- `engagement_send`

Optional later:

- `engagement_detect` only if the detector needs a live Telegram lease; MVP should read collection
  artifacts instead.

Acceptance:

- Existing expansion and collection tests still pass.
- Engagement workers release accounts in `finally` blocks.
- FloodWait maps to `rate_limited`.
- Banned/deauthorized sessions map to `banned`.
## Slice 5: API Settings And Topics

Status: completed.

Add API routes:

```http
GET  /api/communities/{community_id}/engagement-settings
PUT  /api/communities/{community_id}/engagement-settings
GET  /api/engagement/topics
POST /api/engagement/topics
PATCH /api/engagement/topics/{topic_id}
```

Acceptance:

- Settings are disabled by default.
- `allow_post` cannot be true when `require_approval` is false in MVP.
- Topic guidance fields are stored and returned.
- API tests cover auth, validation, defaults, and updates.
## Slice 6: Join Worker

Status: completed.

Implement `community.join`:

- Load community and engagement settings.
- Verify `allow_join = true`.
- Acquire an engagement join account lease.
- Resolve the Telegram community entity.
- Join the community if not already joined.
- Upsert `community_account_memberships`.
- Release account with correct outcome.

Acceptance:

- Fakeable Telethon adapter tests cover success, already joined, inaccessible community, FloodWait,
  and banned/deauthorized account behavior.
- The worker never joins when `allow_join` is false.
- Membership state is durable.
