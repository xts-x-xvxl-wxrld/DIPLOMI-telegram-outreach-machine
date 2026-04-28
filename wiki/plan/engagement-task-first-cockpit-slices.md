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

## Current Focus

Start with Slice 1 unless a dependency already forced part of the schema into
place. Slice 1 is the foundation for all later cockpit work because it creates
the first-class engagement row, engagement-scoped settings, and legacy backfill
bridge.
