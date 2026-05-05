# Engagement Backend Strangler — Phases 4–6, Test Strategy, and Acceptance

## Phase 4: Move Runtime Decisions Out Of Workers

### Objective

Move reusable runtime decisions out of worker modules and into backend
services with stable ownership.

### Changes

- Extract service-owned logic for:
  - quiet-hours gating
  - send-limit checks
  - send reservation/idempotent action lookup
  - task-first operator-send eligibility
  - any issue-service logic that currently imports worker internals
- Remove the current cross-layer pain points explicitly:
  - `task_first_engagement_issues.py` importing quiet-hours logic from the
    scheduler worker
  - `task_first_engagement_issues.py` importing send-limit logic from the send
    worker
  - `engagement_cockpit.py` importing send-reservation logic from the send
    worker
- Keep workers responsible for orchestration:
  - payload validation
  - account lease lifecycle
  - adapter calls
  - final commit/result mapping
- Keep service functions pure or fakeable where practical so tests stop
  depending on worker modules for business rules.

### Exit Criteria

- Quiet-hours and send-limit semantics have one service owner.
- Cockpit issue flows do not need worker internals to explain active behavior.
- Worker files shrink toward orchestration and adapter concerns only.

## Phase 5: Narrow Cockpit Read Models

### Objective

Replace full-table cockpit loading and Python-side recomputation with scoped
read models that match actual screens.

### Changes

- Split cockpit reads by surface:
  - home summary
  - approvals queue
  - issues queue
  - engagement list/detail
  - sent feed
- Replace broad `_load_cockpit_data` style loaders with focused query helpers.
- Make issue computation depend on explicit read inputs instead of broad
  in-memory snapshots.
- Add tests for:
  - pagination
  - visibility rules
  - issue ordering
  - approval queue filtering

### Exit Criteria

- Cockpit read code no longer bulk-loads unrelated tables for every screen.
- Each screen can be understood from one query/read-model boundary.
- Issue generation has a smaller and clearer input set.

## Phase 6: Prune Compat Surfaces

### Objective

Retire compatibility surfaces after the active backend no longer depends on
them.

### Changes

- Remove active imports from compat facades.
- Collapse `backend/api/routes/engagement.py` to routing-only or replace it
  with explicit top-level wiring once tests no longer need sync shims.
- Demote or delete community-scoped engagement route/service surfaces that no
  longer back active behavior.
- Update docs to reflect the reduced contract surface.

### Exit Criteria

- Active task-first routes and workers can be understood without reading compat
  modules.
- Compat modules are either clearly historical or still justified by a live
  legacy path.
- The remaining engagement backend surface is materially smaller and less
  ambiguous.

## Test Strategy

Maintain three layers of safety while refactoring:

1. active API and cockpit mutation tests
2. worker/service regression tests for join/detect/send/scheduler decisions
3. one small real integration slice covering:
   - task-first confirm
   - join-or-detect enqueue behavior
   - approved draft send reservation and send handoff

Do not rely only on fake-heavy unit coverage once the runtime boundary starts
moving.

## Acceptance Criteria

- The backend has one documented active runtime path for task-first
  engagements.
- Active workers do not depend on legacy effective-settings resolution.
- Runtime decision logic is service-owned instead of spread across workers and
  cockpit issue code.
- Low-level permission flags are no longer the active source of truth for
  runtime behavior.
- Cockpit reads are screen-scoped instead of full-table snapshots.
- Compat surfaces are reduced to explicit legacy-only roles.
- The canonical engagement API, queue, and DB contracts still match code and
  tests after each phase.
