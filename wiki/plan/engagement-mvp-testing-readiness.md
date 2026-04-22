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

## Slices

- [Collection and Detection](engagement-mvp-testing-readiness/collection-detection.md) - collection
  worker, exact batches, and detection payload contract.
- [Timeliness and Scheduler](engagement-mvp-testing-readiness/timeliness-scheduler.md) - reply
  opportunity freshness fields and active engagement collection cadence.
- [Operator Runbook](engagement-mvp-testing-readiness/operator-runbook.md) - bot/API controls,
  staged Telegram runbook, test gate, definition of done, and out-of-scope boundaries.

## Slice Status

| Slice | Status |
|---|---|
| Engagement Collection Worker | planned |
| Exact Batch And Detection Payload Contract | planned |
| Timely Reply Opportunity Fields | planned |
| Active Engagement Collection Scheduler | planned |
| Operator Staged-Test Controls | planned |
| Staged Telegram Runbook | planned |

## Test Gate Summary

Before any live staged Telegram engagement test:

- Collection worker tests pass.
- Queue payload tests pass.
- Engagement detection tests pass, including `collection_run_id` exact-batch loading.
- Engagement send worker tests pass, including stale reply deadline rejection.
- Engagement scheduler tests pass for collection and fallback detection.
- Bot/API engagement tests pass for manual collection, review, approval, send, and audit views.
- Docker Compose can start API, worker, scheduler, bot, Redis, and Postgres.
