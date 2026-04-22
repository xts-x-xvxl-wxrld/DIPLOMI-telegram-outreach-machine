# Engagement MVP Timeliness And Scheduler Slices

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
