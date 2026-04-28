# Engagement Task-First Cockpit Phases 0-4

Detailed early implementation phases for the task-first `Engagements` cockpit.

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
