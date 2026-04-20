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

## Slice 7: Detection Worker

Status: completed.

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

Implemented notes:

- Added `backend/workers/engagement_detect.py` for `engagement.detect` orchestration.
- Added candidate creation, validation, phone redaction, and active-candidate dedupe helpers to the
  engagement service.
- Added `OPENAI_ENGAGEMENT_MODEL` so engagement drafting can be configured separately from brief
  extraction.
- Worker tests cover keyword no-signal, draft candidate creation, and duplicate active candidate
  skips with fake model output.

## Slice 8: Review API And Bot Controls

Status: completed.

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

Implemented notes:

- Added candidate list, approve, and reject service transitions with expiry and reply validation.
- Added API DTOs/routes for pending candidate review without invoking Telethon or enqueueing sends.
- Added bot client methods, `/engagement_candidates`, `/approve_reply`, `/reject_reply`, and inline
  candidate approve/reject controls.
- Added tests for API review transitions, bot HTTP contracts, card formatting, and callback data.

## Slice 9: Send Worker

Status: completed.

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

Implemented notes:

- Added `backend/workers/engagement_send.py` for approved public reply sends.
- Added final preflight checks for candidate approval, expiry, engagement settings, reply-only
  requirements, joined account membership, validated final reply text, and send limits.
- Added idempotent `engagement_actions` creation with `engagement.send:{candidate_id}` keys,
  duplicate-send avoidance for already sent actions, and fail-closed behavior for orphaned queued
  actions without Telegram confirmation.
- Extended the Telethon engagement adapter with `send_public_reply` and send-specific error mapping.
- Worker tests cover missing approval, success, rate-limit skips, sent-action idempotency, queued
  action fail-closed behavior, FloodWait release mapping, and no-longer-replyable messages.

## Slice 10: Scheduler

Status: completed.

Add optional scheduled detection:

- Run hourly or after successful collection for engagement-enabled communities.
- Skip disabled communities.
- Skip communities with active unreviewed candidates.
- Respect quiet hours.

Acceptance:

- Scheduler does not enqueue duplicate detection jobs.
- Detection cadence is conservative.
- No automatic sends are scheduled in MVP.

Implemented notes:

- Added `backend/workers/engagement_scheduler.py` as a lightweight recurring process.
- Scheduler reads engagement settings in `observe`, `suggest`, and `require_approval` modes,
  requires a completed collection run inside the configured detection window, skips active
  candidates, and respects quiet hours.
- Scheduled detection uses `engagement.detect:{community_id}:{yyyyMMddHH}` job IDs; manual
  detection has a separate `engagement.detect.manual` helper prefix for future operator-forced
  runs.
- Added `scheduler` to Docker Compose and kept send jobs out of the scheduler entirely.

## Slice 11: Manual Detection And Send Job API

Status: completed.

Add operator API endpoints:

```http
POST /api/communities/{community_id}/engagement-detect-jobs
POST /api/engagement/candidates/{candidate_id}/send-jobs
```

Acceptance:

- Manual detection uses the manual engagement detect queue helper and distinct manual job ID prefix.
- Send jobs can be queued only for approved candidates.
- API handlers enqueue jobs only; Telethon sending remains owned by `engagement.send`.
- Queue unavailability maps to `503` and missing rows map to `404`.

Implemented notes:

- Added request DTOs for manual detection windows and send-job operator labels.
- Added engagement API routes that verify the target community or candidate exists before enqueueing.
- Added an approval-state guard before send-job enqueueing so unreviewed candidates cannot be queued
  from the API.
- Added focused API tests for manual detection enqueueing, missing communities, approved send
  enqueueing, and unapproved send rejection.

## Slice 12: Instruction And Monitoring Policy

Status: completed.

Clarified the operator-facing product contract for:

- how admin instructions are assembled for the message-generation agent
- what durable configuration answers: what kind of conversation to look for, what position to take,
  how the account should sound in the community, what may be claimed, and what to avoid
- how the scheduler monitors recent public discussion through collection artifacts rather than a
  separate always-on chat listener
- how post-join trigger detection, 15-to-60-minute response timing, quiet hours, candidate expiry,
  human review, and send spacing fit together
- how broad recent message batches can support opportunity detection without being dumped into the
  normal draft-generation prompt

Acceptance:

- Future implementation work has a single spec section for prompt instruction assembly.
- Monitoring is documented as collection-driven detection, not direct outbound-worker scraping.
- Send timing remains sparse, approval-gated, reply-only, and rate-limited.
- Topic guidance and style rules have user-facing editing questions that the bot should expose.

## Slice 13: Concrete Detection Contracts

Status: completed.

Clarified the implementable detection contract before the next code slices:

- candidate-creating scheduled detection requires an approved target and a joined engagement
  membership with a usable `joined_at`
- post-join filtering prevents pre-join messages from creating fresh engagement candidates
- deterministic trigger selection runs before any model call
- trigger selection uses keyword/phrase matches, negative exclusions, message age, replyability,
  dedupe, and recent sent-action cooldowns
- scheduled triggers should normally be 15 to 60 minutes old
- draft-generation model input is one selected `source_post`, optional `reply_context`, topic
  guidance, style rules, and community summary
- stable skip reasons, detection sample shape, trigger record shape, and structured model output
  validation are documented

Acceptance:

- Implementation slices can build selector code and tests against named contracts.
- Broad recent message batches remain out of normal draft-generation prompts.
- Keyword matches are treated as model-call authorization only, not candidate/send authorization.

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
