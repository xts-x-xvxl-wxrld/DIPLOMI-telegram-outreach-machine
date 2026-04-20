# Timely Reply Opportunities Plan

## Goal

Strengthen engagement detection so the system finds live public discussion moments quickly, creates
time-bounded reply opportunities, and notifies the operator while a useful public reply can still
land naturally.

This plan also renames the engagement-domain concept from `candidate` to `reply opportunity`.
Current storage and API names may remain `engagement_candidates` and `candidate_id` until a later
compatibility migration.

## Design Decisions

- Use `reply opportunity` in operator-facing copy, docs, and new contracts.
- Keep collection and detection separate: collection reads Telegram and writes bounded artifacts;
  detection reads those artifacts and decides whether a reply opportunity exists.
- Queue detection after successful collection for engagement-enabled communities.
- Keep the hourly scheduler as a fallback sweep, not the primary timely path.
- Attach `source_message_date`, `detected_at`, `review_deadline_at`, and `reply_deadline_at` to reply
  opportunities.
- Treat `expires_at` as cleanup, while send preflight uses `reply_deadline_at` for conversation
  freshness.
- Draft from exactly one selected `source_post` in normal reply opportunity generation.
- Store opportunity-level `moment_strength`, `timeliness`, and `reply_value`; never score people.
- Notify the operator only for fresh or aging reply opportunities after the row is committed.

## Slice 1: Spec Contract

Status: completed.

Tasks:

- Add engagement terminology for reply opportunities.
- Explain collection versus detection.
- Add freshness SLO, reply deadlines, collection-completion-triggered detection, single-source-post
  drafting, opportunity-level strength/timeliness/value, and operator notification rules.
- Update wiki index and log.

Acceptance:

- The engagement spec describes timely reply opportunities rather than vague candidates.
- The spec preserves current legacy DB/API names while pointing future UI and API aliases toward
  reply opportunity language.
- Collection remains read-only and detection remains the only engagement decision layer.

## Slice 2: Schema And API Compatibility

Status: planned.

Tasks:

- Add reply-opportunity freshness fields to the engagement candidate model and migration.
- Add API aliases or response names that expose reply opportunity language without breaking existing
  clients.
- Keep legacy `candidate_id` accepted until callers migrate.

Acceptance:

- Existing tests keep passing for legacy endpoints.
- New API responses expose reply opportunity freshness and operator notification fields.

## Slice 3: Timely Detection Pipeline

Status: planned.

Tasks:

- Queue `engagement.detect` after successful collection for engagement-enabled communities.
- Keep the hourly scheduler as a fallback sweep.
- Implement one-trigger `source_post` model input for normal drafting.
- Persist `moment_strength`, `timeliness`, `reply_value`, deadlines, and notification state.

Acceptance:

- A fresh collection artifact can produce a reviewable reply opportunity without waiting for the
  hourly scheduler.
- Send preflight rejects stale reply opportunities based on `reply_deadline_at`.
- Operator notifications open only after committed fresh or aging opportunities.

## Slice 4: Engagement Collection Mode

Status: completed for spec, planned for code.

Tasks:

- Define engagement collection mode in the collection spec.
- Require collection to pull every new visible message since the last checkpoint for approved
  engagement communities.
- Record checkpoint ranges and expose exact `engagement_messages` batches for detection.
- Queue `engagement.detect` with `collection_run_id` after successful engagement collection.
- Clarify that collection still does not perform topic matching, OpenAI calls, reply drafting, or
  operator notification.

Acceptance:

- The collection spec describes all-new-message incremental intake for engagement-enabled
  communities.
- The engagement spec describes detection as consuming exact collection-run batches before falling
  back to sampled artifacts.
- Implementation can build checkpointing, batch persistence, and collection-triggered detection
  against named contracts.

## Open Questions

- Should the bot expose `/engagement_opportunities` immediately as an alias for
  `/engagement_candidates`?
- Should `ENGAGEMENT_ACTIVE_COLLECTION_INTERVAL_SECONDS` be a global setting or per-community
  setting?
- Should notification delivery use the existing bot chat only, or a separate operator inbox table?
- Should engagement message batches live only in `collection_runs.analysis_input`, in raw `messages`,
  or in a dedicated short-retention table?
