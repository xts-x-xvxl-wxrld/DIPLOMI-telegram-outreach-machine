# Engagement Task-First Cockpit Implementation Plan

Phased delivery plan for building the task-first engagement cockpit on top of
the finalized UX, routing, and API contracts.

## Goal

Ship the new `Engagements` home, wizard-first setup, scoped approvals/issues
flows, and engagement-scoped backend model without exposing a mixed old/new
operator experience.

Detailed mergeable delivery slices live in
`wiki/plan/engagement-task-first-cockpit-slices.md`.

## Build Principles

- Build engagement-scoped backend foundations before moving bot surfaces.
- Keep the bot thin; prefer backend semantic endpoints over handler-side
  orchestration.
- Migrate one operator flow at a time and retire old primary paths as each new
  flow lands.
- Preserve fail-closed behavior when migration state is incomplete.

## Phase Shards

- [Phases 0-4](engagement-task-first-cockpit/phases-0-4.md) - readiness,
  schema/backfill foundation, engagement-scoped writes, cockpit read models,
  and semantic mutations.
- [Phases 5-9](engagement-task-first-cockpit/phases-5-9.md) - bot routing,
  wizard UI, approval/issues queues, legacy retirement, and testing/rollout.

## Recommended Slice Order

If implementation needs smaller mergeable slices, use this order:

1. schema + backfill foundation
2. engagement-scoped wizard writes
3. cockpit read models
4. semantic draft and issue mutations
5. new home + navigation shell
6. wizard UI
7. approvals queue
8. issues queue + quiet-hours/rate-limit subflows
9. legacy path retirement
10. cleanup and regression hardening

## Risks To Watch

- mixing community-scoped and engagement-scoped state in one screen
- allowing the bot to bypass semantic mutation endpoints
- leaving `auto_limited` blocked in validation while exposing `Auto send` in UI
- keeping multi-topic assumptions alive in backend code after the single-topic
  contract is live
- exposing incomplete migrated engagements in `My engagements`

## Definition Of Done

The implementation is done when:

- `Engagements` is the primary operator home
- `Add engagement` and detail edit flows use the new wizard
- approvals and issues run through the new queue controllers
- read models and mutations are engagement-scoped
- old competing primary paths are retired
- automated tests cover the main happy paths and the documented edge states
