# Community Engagement Plan

## Goal

Add an optional engagement layer that lets managed Telethon accounts join approved communities,
notice active discussion around configured topics, draft useful public replies, and send only after
operator approval.

The first implementation should be conservative and auditable:

```text
settings + topics
  -> join approved community
  -> detect topic moment
  -> draft candidate
  -> operator approves
  -> send public reply
  -> audit action
```

## Current Context

Existing boundaries:

- Discovery finds communities and does not collect raw message history.
- Collection fetches and persists community data only; it has no outreach behavior.
- Analysis produces community-level summaries only.
- Account manager leases one account per worker job and tracks flood waits.
- Raw messages are opt-in through `communities.store_messages`.

Engagement must not weaken those boundaries. It should be a new module with its own jobs, tables,
API routes, bot controls, and audit logs.

## Design Decisions

- Engagement is opt-in per community.
- MVP requires human approval before every send.
- MVP sends public replies only, not direct messages.
- MVP should not send top-level posts unless a later plan explicitly adds that mode.
- Detection may use OpenAI, but only in the engagement worker.
- Collection remains read-only.
- No person-level scoring, ranking, or persuasion targeting.
- Telethon accounts used for engagement must use the account manager and respect FloodWait.
- Every outbound action must be logged, including failed and skipped attempts.

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

Status: planned.

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

Status: planned.

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

Status: planned.

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

## Slice 7: Detection Worker

Status: planned.

Implement `engagement.detect`:

- Load active community engagement settings.
- Load active engagement topics.
- Read compact recent samples from latest collection artifacts.
- Use keyword prefiltering before any OpenAI call.
- Call OpenAI only when there is enough signal.
- Create `engagement_candidates` with capped source excerpts and suggested replies.

Acceptance:

- No send behavior exists in this worker.
- Duplicate active candidates are skipped.
- Prompt tests or fixtures cover "no reply" and "draft reply" paths.
- Candidate rows do not include sender IDs.

## Slice 8: Review API And Bot Controls

Status: planned.

Add API routes:

```http
GET  /api/engagement/candidates
POST /api/engagement/candidates/{candidate_id}/approve
POST /api/engagement/candidates/{candidate_id}/reject
```

Add bot controls:

```text
/engagement_candidates
/approve_reply <candidate_id>
/reject_reply <candidate_id>
```

Acceptance:

- Operator can list pending candidate replies.
- Approving records `reviewed_by` and `reviewed_at`.
- Rejecting records `reviewed_by` and `reviewed_at`.
- Bot cards show community, topic, source excerpt, and suggested reply.

## Slice 9: Send Worker

Status: planned.

Implement `engagement.send`:

- Verify candidate is approved.
- Verify community settings still allow posting.
- Verify account membership is `joined`.
- Check community and account rate limits.
- Send as a reply to `source_tg_message_id`.
- Write `engagement_actions` for sent, failed, and skipped outcomes.

Acceptance:

- MVP sends replies only.
- No send occurs without approval.
- Rate-limit checks prevent overposting.
- Telethon errors map through account manager outcomes.
- Sent Telegram message ID is stored when available.

## Slice 10: Scheduler

Status: planned.

Add optional scheduled detection:

- Run hourly or after successful collection for engagement-enabled communities.
- Skip disabled communities.
- Skip communities with active unreviewed candidates.
- Respect quiet hours.

Acceptance:

- Scheduler does not enqueue duplicate detection jobs.
- Detection cadence is conservative.
- No automatic sends are scheduled in MVP.

## Open Questions

- Should engagement settings be available only for `status = monitoring` communities, or also for
  approved candidates before recurring collection is enabled?
- Should each community have exactly one assigned Telegram account, or should assignment be chosen
  at send time from eligible joined accounts?
- Should edited suggested replies be stored as a separate revision table or only as final outbound
  text on `engagement_actions`?
- Should `auto_limited` ever be enabled, or remain out of scope permanently?

## Rollback Plan

If engagement creates operational risk:

- Set all `community_engagement_settings.mode = 'disabled'`.
- Disable scheduler enqueueing for `engagement.detect`.
- Keep audit tables for investigation.
- Leave discovery, collection, expansion, and analysis unaffected.
