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

## Phase 0 — Readiness

Outcome:

- repo owners agree this plan is the active delivery sequence
- all task-first specs stay source of truth during implementation

Tasks:

- link this plan from the relevant cockpit and wizard plan pages
- identify the current bot entrypoints, handlers, services, and schemas that
  will be touched
- define a small implementation checklist for every phase before code starts

Exit criteria:

- one implementation doc exists and is accepted as the active sequence

## Phase 1 — Data Model And Migration Base

Outcome:

- first-class `engagement` storage supports the new wizard and cockpit read
  model

Tasks:

- add or finalize `engagements` table shape with `target_id`, `community_id`,
  `topic_id`, `status`, and audit fields
- finalize `engagement_settings` support for assigned account, mode, and quiet
  hours
- remove the old multi-topic direction from code paths and align to one topic
  per engagement
- write idempotent backfill logic from legacy community-scoped setup into one
  engagement per target
- ensure incomplete draft engagements stay hidden from normal operator lists

Dependencies:

- none; this is the base phase

Exit criteria:

- migrations apply cleanly
- backfill can run repeatedly without duplicating engagements
- one engagement per target is enforced

## Phase 2 — Engagement-Scoped Write Services

Outcome:

- backend can create/update/confirm/retry engagement wizard state through the
  documented contracts

Tasks:

- implement `POST /api/engagements`
- implement `PATCH /api/engagements/{engagement_id}`
- implement `PUT /api/engagements/{engagement_id}/settings`
- implement `POST /api/engagements/{engagement_id}/wizard-confirm`
- implement `POST /api/engagements/{engagement_id}/wizard-retry`
- enforce single-topic validation and `Auto send -> auto_limited` support
- remove the guard that rejects `auto_limited`

Dependencies:

- Phase 1

Exit criteria:

- wizard step writes are idempotent
- confirm can validate, approve target when needed, enqueue detect, and
  activate atomically from the operator point of view
- retry resets wizard-owned state without deleting the durable engagement row

## Phase 3 — Cockpit Read Models

Outcome:

- backend serves the full task-first cockpit from explicit read-model endpoints

Tasks:

- implement `GET /api/engagement/cockpit/home`
- implement global and scoped approvals read endpoints
- implement global and scoped issues read endpoints
- implement engagement list, engagement detail, and sent-message feed endpoints
- compute `pending_task` on detail with the defined priority order
- generate issue rows from explicit backend rules instead of bot-side inference

Dependencies:

- Phase 1
- partial Phase 2 for engagement-scoped writes and status semantics

Exit criteria:

- every task-first screen can render from one documented read model
- bot handlers no longer need to merge low-level settings/target/candidate
  payloads to render a screen

## Phase 4 — Semantic Mutation Endpoints

Outcome:

- backend exposes stable operator-facing actions for approvals, issues, and
  quiet-hours/rate-limit subflows

Tasks:

- implement semantic draft action endpoints for approve/reject/edit
- implement semantic issue-action endpoint and action-key mapping
- implement semantic helper mutations for resume sending, target approval, and
  permission sync
- implement rate-limit detail read endpoint
- implement quiet-hours read/write endpoints

Dependencies:

- Phase 2
- Phase 3 for queue/item identity

Exit criteria:

- every action from `Approve draft` and `Top issues` maps to a concrete
  endpoint with the documented result DTOs

## Phase 5 — Bot Routing And Handler Rewrite

Outcome:

- bot surfaces run on the new `op:*` and `eng:*` callback families

Tasks:

- replace old home entrypoints with the `Engagements` home controller
- implement callback routing for approvals, issues, lists, detail, sent
  messages, and wizard flows
- wire each callback to the documented read-model or mutation endpoint
- respect returned `next_callback` values instead of recomputing routing
- store return-context state for early exits from draft-edit and issue-fix
  subflows

Dependencies:

- Phase 3
- Phase 4

Exit criteria:

- bot handler code follows the documented callback-to-endpoint matrix
- old primary home/nav path is no longer the default operator path

## Phase 6 — Wizard UI And Edit Reentry

Outcome:

- operators can create and edit engagements through the new five-step wizard

Tasks:

- implement target, topic, account, sending-mode, and final-review screens
- implement single-topic selection UX
- implement inline topic-create and account-create return behavior where needed
- implement edit reentry from engagement detail into topic/account/mode steps
- implement `Retry`, `Cancel`, and confirm/review behavior from the new DTOs

Dependencies:

- Phase 2
- Phase 5 for callback routing

Exit criteria:

- `Add engagement` and detail edits both use the same wizard contract
- incomplete drafts remain hidden from `My engagements`

## Phase 7 — Approval And Issue Queues

Outcome:

- one-by-one approval and issue work runs from the new task-first queue
  controllers

Tasks:

- implement approval queue controller, confirmation screens, and update
  placeholder behavior
- implement issue queue controller, skip behavior, and direct-fix actions
- implement rate-limit detail and quiet-hours edit subflows
- implement scoped queue behavior launched from engagement detail

Dependencies:

- Phase 4
- Phase 5

Exit criteria:

- approvals and issues can be completed end-to-end without dropping back into
  legacy screens

## Phase 8 — Legacy Surface Retirement

Outcome:

- the new cockpit is primary and the old community-scoped operator path is no
  longer competing with it

Tasks:

- remove or hide old primary bot entrypoints that conflict with `Engagements`
- keep legacy admin/review screens only where still needed as compatibility
  tools
- stop routing new operator work through community-scoped engagement settings
  screens
- remove legacy writes once no active callback depends on them

Dependencies:

- Phase 5
- Phase 6
- Phase 7

Exit criteria:

- no competing old/new primary operator flows remain

## Phase 9 — Testing And Rollout

Outcome:

- the new cockpit can ship with confidence and rollback visibility

Tasks:

- add service tests for backfill, confirm/retry, issue generation, and semantic
  action endpoints
- add bot tests for the home controller, wizard, approvals, issues, detail, and
  sent messages
- add regression tests for stale/blocked/noop edge states
- verify migration behavior on partially legacy data
- run targeted manual operator walkthroughs for:
  - first engagement create
  - edit existing engagement
  - approve draft
  - reject draft
  - edit draft and wait for replacement
  - resolve each confirmed issue type

Exit criteria:

- documented happy-path and edge-path flows pass in bot tests
- rollout can proceed without exposing mixed-source UI

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
