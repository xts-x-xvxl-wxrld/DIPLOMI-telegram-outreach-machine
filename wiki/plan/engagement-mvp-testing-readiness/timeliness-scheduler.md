# Engagement MVP Timeliness And Scheduler Slices

## Slice 3: Timely Reply Opportunity Fields

Status: completed.

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

Delivered:

- Added Alembic migration `20260422_0012` plus SQLAlchemy/service/API field support for reply
  opportunity freshness, timeliness, and review/send deadlines.
- Detection now derives `timeliness` from source-post timestamps, normalizes
  `moment_strength`/`reply_value`, and skips stale automatic reply opportunities before creation.
- Approval rejects stale reply opportunities, and `engagement.send` now uses `reply_deadline_at`
  as the freshness gate before Telethon work starts.
- Operator-facing candidate cards now surface freshness and review/reply deadlines.

Acceptance:

- Existing legacy candidate endpoints still work.
- New responses expose freshness/deadline fields.
- Approval and send preflight reject stale reply opportunities.
- Tests cover freshness calculation, stale skips, and no person-level scoring.

## Slice 4: Active Engagement Collection Scheduler

Status: completed.

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

Delivered:

- Added `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS` with a default 600-second active collection
  cadence.
- Extended `backend.workers.engagement_scheduler` so the existing Docker Compose scheduler process
  owns both active engagement collection ticks and low-frequency fallback detection ticks.
- Added collection target selection for enabled engagement settings, approved `allow_detect`
  targets, recent collection skips, active collection skips, quiet-hour skips, and duplicate-job
  handling.
- Added minute-bucketed engagement collection job IDs shaped as
  `collection:engagement:{community_id}:{yyyyMMddHHmm}`.
- Added scheduler and queue contract tests for collection enqueueing, duplicate handling, enqueue
  failures, and skip reasons.
