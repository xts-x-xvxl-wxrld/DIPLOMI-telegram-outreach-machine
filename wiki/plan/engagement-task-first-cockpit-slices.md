# Engagement Task-First Cockpit Slices

Detailed build slices for delivering the task-first `Engagements` cockpit from
schema through bot rollout.

## Slice Shards

- [Slices 1-6](engagement-task-first-cockpit/slices-1-6.md) - schema/backfill,
  wizard writes, cockpit read models, issue generation, semantic mutations, and
  bot API client/callback parsing.
- [Slices 7-12](engagement-task-first-cockpit/slices-7-12.md) - `Engagements`
  home/navigation, wizard UI, approval queue, issue queue, detail/feed, and
  legacy retirement hardening.

## Delivery Rules

- Keep each slice mergeable on its own.
- Prefer backend contract completion before bot-surface rewrites.
- Do not ship a mixed old/new primary operator path.
- Treat stale, blocked, noop, and empty-state behavior as first-class acceptance
  criteria, not polish.

## Current Status

- Slice 1 is complete. The schema foundation and legacy backfill landed on
  2026-04-28.
- Slice 2 is already in progress in code. The task-first create, patch,
  settings, `wizard-confirm`, and `wizard-retry` endpoints already exist, so
  the next blank-slate backend gap is not wizard writes.
- The first missing contract layer is the cockpit read-model surface. No
  task-first `GET /api/engagement/cockpit/*` endpoints are implemented yet.

## What's Next Queue

Recommended execution order from the current repo state:

1. Slice 3: Cockpit Read Models.
   Build `home`, approvals, issues, engagement list/detail, and sent-message
   DTOs first. Every later bot surface depends on these payloads.
2. Slice 4: Issue Generation Service.
   Generate the confirmed issue taxonomy before the bot queue exists, so `Top
   issues` has one stable source of truth.
3. Slice 5: Semantic Draft And Issue Mutations.
   Finish the approval actions, issue actions, rate-limit detail, and
   quiet-hours edit contract before any controller logic starts guessing.
4. Slice 6: Bot API Client And Callback Parsing.
   Wire the bot to the new backend contracts only after the read/mutation
   shapes exist.
5. Slice 8: Wizard UI And Edit Reentry.
   This can build directly on the already-landed wizard write endpoints without
   waiting for the full home cutover.
6. Slice 9: Approval Queue Controller.
   Approvals are the highest-priority operator task, so this is the first
   queue surface to build once the backend contract is stable.
7. Slice 10: Issue Queue Controller.
   Land the exact fix actions and subflows after approvals, using the Slice 4-5
   issue contract.
8. Slice 11: Engagement Detail And Sent Messages.
   Finish the lower-priority browse/read surfaces after the main queues work.
9. Slice 7: `Engagements` Home And Navigation Shell.
   Cut over the primary home only after the downstream screens already exist.
   This avoids shipping a mixed old/new main operator path.
10. Slice 12: Legacy Retirement And Release Hardening.
    Remove old paths and run the full walkthrough only after the new shell and
    all task surfaces are connected.

## Cutover Rule

Do not treat slice numbering as the same thing as release order. Slice 7 should
stay late in the execution queue because it is the shell-cutover slice, not the
first backend dependency.
