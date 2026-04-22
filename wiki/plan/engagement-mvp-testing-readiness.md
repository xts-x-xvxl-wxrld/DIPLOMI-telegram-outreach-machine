# Engagement MVP Testing Readiness

## Goal

Finish the missing engagement pieces required before staged Telegram testing.

The MVP test should prove this loop end to end, with no automatic posting:

```text
approved engagement target
  -> joined engagement account
  -> engagement collection reads fresh public messages
  -> collection writes an exact new-message batch
  -> engagement.detect creates a reply opportunity
  -> operator reviews and edits
  -> operator-approved engagement.send posts one public reply
  -> audit rows explain every step
```

## Current Blockers

- `collection.run` is still a worker stub and does not read Telegram messages.
- Detection payloads do not carry `collection_run_id`, so collection-triggered detection cannot
  inspect the exact run that just completed.
- Detection still reads sampled artifacts before exact `engagement_messages` batches.
- There is no active engagement collection scheduler for the target 10-minute cadence.
- Reply opportunity freshness fields from the timely-replies contract are not yet fully persisted.
- Manual staged testing lacks one clear readiness checklist for target setup, collection, detection,
  review, send, and audit verification.

## Design Decisions

- Keep collection read-only: no OpenAI, no topic matching, no reply drafting, no operator
  notification, no engagement table writes.
- Keep engagement decisions inside `engagement.detect`.
- Store exact MVP engagement batches in `collection_runs.analysis_input.engagement_messages` until a
  dedicated short-retention batch table is justified.
- Pass only IDs and compact timing metadata through Redis. Do not pass message text through queue
  payloads.
- Keep hourly `engagement_scheduler` as a fallback sweep. Add a separate active collection cadence
  for engagement-enabled communities.
- MVP staged testing may use a small controlled Telegram group first, but the implementation must
  also support real approved public groups/channels where the account is allowed to participate.
- Sending remains reply-only and human-approved. `auto_limited` stays out of scope.

## Slice 1: Engagement Collection Worker

Status: planned.

Tasks:

- Implement `backend/workers/collection.py` or an equivalent worker shard and wire
  `collection.run` dispatch to it.
- Add a fakeable Telegram collection adapter, separate from `telegram_snapshot.py`, that can:
  - resolve the community entity from existing `communities` fields
  - fetch new visible messages since the last successful engagement checkpoint
  - keep a small overlap and dedupe by `(community_id, tg_message_id)`
  - include text messages and media captions, while skipping media-only messages
  - include `reply_to_tg_message_id`, parent `reply_context` when available, message date, and
    `is_replyable`
  - map FloodWait and banned/deauthorized sessions to account-manager outcomes
- Acquire and release a `collection` account lease with `finally`-safe cleanup.
- Persist a completed or failed `collection_runs` row for every attempted run.
- Update `community_snapshots` metadata when available.
- Update `users` and `community_members` activity counts only from visible attributable Telegram
  users, without phone numbers or person-level scores.
- Write raw `messages` rows only when `communities.store_messages = true`.

Acceptance:

- Empty new-message batches complete successfully with `messages_seen = 0`.
- Inaccessible communities produce a failed collection run or clear dropped/access state without
  marking the account unhealthy unless the error is account-level.
- Collection worker tests cover success, empty batch, inaccessible community, FloodWait, banned
  session, `store_messages = false`, and `store_messages = true`.

## Slice 2: Exact Batch And Detection Payload Contract

Status: planned.

Tasks:

- Extend `EngagementDetectPayload` with `collection_run_id: UUID | None`.
- Extend `enqueue_engagement_detect` to accept `collection_run_id`.
- Use job IDs shaped as `engagement.detect:{community_id}:{collection_run_id}` for
  collection-triggered detection and keep hourly/manual IDs for fallback/manual runs.
- After a successful engagement collection commit, enqueue `engagement.detect` only when:
  - the batch contains at least one new text-bearing detection-eligible message
  - engagement settings are enabled for detection
  - an approved engagement target grants `allow_detect = true`
  - quiet hours do not block engagement collection-triggered detection
- Store `analysis_input.engagement_messages` and `analysis_input.engagement_checkpoint` using the
  collection spec shape.
- Update detection sample loading order:
  1. exact `collection_run_id` engagement batch
  2. recent opt-in stored `messages`
  3. compact `sample_messages` artifacts for manual diagnostics and scheduler fallback only

Acceptance:

- Queue payload tests assert `collection_run_id` is optional and serialized.
- Detection tests prove exact `engagement_messages` are preferred over latest sampled artifacts.
- Collection does not pass message text through Redis.
- Detection rejects or skips a `collection_run_id` that belongs to another community.

## Slice 3: Timely Reply Opportunity Fields

Status: planned.

Tasks:

- Add migration, models, services, and API DTO fields for:
  - `source_message_date`
  - `detected_at`
  - `review_deadline_at`
  - `reply_deadline_at`
  - `operator_notified_at`
  - `moment_strength`
  - `timeliness`
  - `reply_value`
- Update candidate creation so scheduled detection creates only fresh or aging reply opportunities.
- Use `reply_deadline_at`, not `expires_at`, as send preflight's conversation freshness gate.
- Preserve compatibility with existing `engagement_candidates` and `candidate_id` names while using
  reply opportunity language in operator-facing text.

Acceptance:

- Existing legacy candidate endpoints still work.
- New responses expose freshness/deadline fields.
- Approval and send preflight reject stale reply opportunities.
- Tests cover freshness calculation, stale skips, and no person-level scoring.

## Slice 4: Active Engagement Collection Scheduler

Status: planned.

Tasks:

- Add an engagement collection scheduler loop or extend the existing scheduler with separate
  collection-target selection.
- Select communities where:
  - engagement settings are in `observe`, `suggest`, or `require_approval`
  - an approved target grants `allow_detect = true`
  - no active collection job is already queued/running for that community
  - the last successful engagement collection is older than
    `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS`
  - current time is outside configured quiet hours
- Add `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS`, default `600`.
- Use deterministic job IDs shaped as `collection:engagement:{community_id}:{yyyyMMddHHmm}`.
- Keep the hourly detection scheduler as a fallback that only reads completed collection artifacts.

Acceptance:

- Scheduler tests cover due target, recent collection skip, active job skip, quiet hours, disabled
  settings, missing target permission, and enqueue failure.
- Docker Compose starts the needed scheduler process or documents why one process owns both loops.
- Duplicate RQ jobs are treated as safe duplicates, not hard failures.

## Slice 5: Operator Staged-Test Controls

Status: planned.

Tasks:

- Ensure the API can manually queue engagement collection for an approved target.
- Ensure the bot exposes or links the staged sequence:
  - target status
  - join job
  - manual collection job
  - manual detection job
  - reply opportunity review/edit
  - approve/send
  - action audit view
- Add concise bot copy that says `reply opportunity` even when calling legacy candidate endpoints.
- Expose collection run status enough for an operator to see whether fresh messages were collected.

Acceptance:

- A tester can run the whole MVP sequence from the bot without direct database edits.
- Manual collection refuses unapproved targets.
- Manual send still requires an approved reply opportunity and joined engagement membership.

## Slice 6: Staged Telegram Runbook

Status: planned.

Tasks:

- Add a short runbook under `wiki/plan/` or `ops/` for:
  - fake-adapter/local unit test pass
  - controlled Telegram group dry run
  - one real approved community observe-only run
  - one approved reply-only send
- Include preflight checks:
  - `telegram_accounts.account_pool = 'engagement'` for send/join account
  - engagement target is approved with only the needed permissions
  - settings require approval and reply-only mode
  - quiet hours and rate limits are conservative
  - OpenAI key/model settings are present for detection
  - raw message storage remains off unless explicitly enabled for diagnosis
- Include abort switches:
  - set engagement settings to `disabled`
  - pause collection scheduler
  - reject or expire pending reply opportunities

Acceptance:

- The runbook can be followed by an operator without reading source code.
- The runbook includes expected database/API/bot evidence for collection, detection, review, send,
  and audit.
- The runbook explicitly forbids DMs, auto-send, and bulk posting during MVP testing.

## Test Gate Before Live Staging

Before any live staged Telegram engagement test:

- Collection worker tests pass.
- Queue payload tests pass.
- Engagement detection tests pass, including `collection_run_id` exact-batch loading.
- Engagement send worker tests pass, including stale reply deadline rejection.
- Engagement scheduler tests pass for collection and fallback detection.
- Bot/API engagement tests pass for manual collection, review, approval, send, and audit views.
- Docker Compose can start API, worker, scheduler, bot, Redis, and Postgres.

## MVP Test Definition Of Done

The MVP engagement path is ready for staged Telegram testing when all of these are true:

- One approved target can be joined by a dedicated engagement account.
- A collection run can fetch fresh public messages and persist an exact engagement batch.
- Detection can create a bounded, fresh reply opportunity from that exact batch.
- The operator can review, edit, approve, and send one public reply.
- The action audit row stores the exact outbound text, target message ID, send status, and error
  details when applicable.
- No collection path calls OpenAI or writes engagement decision rows.
- No send path can bypass approval, target permission, joined membership, reply-only mode, quiet
  hours, or rate limits.

## Out Of Scope

- Automatic sending.
- Direct messages.
- Bulk joining or bulk posting.
- Dedicated engagement batch table.
- Person-level scores, user ranking, or private identity enrichment.
- Rewriting legacy `engagement_candidates` storage names.
