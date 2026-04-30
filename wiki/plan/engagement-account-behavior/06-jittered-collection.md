# Slice 6: Jittered Collection

## Goal

Spread active engagement collection across communities using per-community Redis due times instead
of one synchronized global cadence.

## Scope

- Store due times under `engagement:collection:next:{community_id}`.
- If no due time exists, set first due time to `now + jitter(1-15 minutes)`.
- Let the scheduler wake every 60 seconds and enqueue only due communities.
- After enqueue, set next due time to `now + jitter(3-15 minutes)`.
- Keep existing permission, quiet-hours, active-collection, and mode gates.
- Store due times as UTC epoch seconds so Redis values are easy to inspect and compare.
- Implement Redis due-state in a small service helper that Slice 7 can reuse.

## Code Areas

- `backend/workers/engagement_scheduler.py`
- `backend/services/engagement_account_behavior.py` or a small Redis due-state helper.
- `tests/` scheduler coverage, likely existing engagement scheduler tests or a new focused file.

## Acceptance

- New communities receive a future due time instead of immediate synchronized collection.
- Due communities enqueue collection and receive a new due time.
- Not-yet-due communities are skipped without counting as recent-collection skips.
- Existing collection duplicate-job behavior still applies.
- Redis outages fail closed by skipping jittered auto-enqueue for that tick and logging the error,
  not by falling back to synchronized collection.

## Dependencies

Requires Slice 1 for jitter. Independent of send behavior.
