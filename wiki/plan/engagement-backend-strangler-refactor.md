# Engagement Backend Strangler Refactor

## Goal

Stabilize the engagement backend by isolating the active task-first runtime
from legacy compatibility paths without attempting a full rewrite.

This plan is the execution guide for backend refactor work. It complements,
but does not replace:

- `wiki/plan/engagement-cockpit-stabilization.md` for active cockpit callback
  and mutation ownership
- `wiki/plan/contract-surface-rationalization.md` for keep/rewrite/demote
  contract cleanup

## Authority Order

When documents disagree during this refactor, resolve them in this order:

1. active tests
2. DB models, migrations, queue payloads, and canonical API/DB/queue specs
3. code-index engagement backend/worker maps
4. active route, service, and worker code
5. older rollout, verification, or compat docs

This plan does not supersede the canonical API, DB, or queue specs. It is the
backend execution guide for moving the runtime onto clearer ownership.

## Working Decision

Use a strangler refactor, not a rewrite.

The backend already has a working active core in the task-first write path,
cockpit APIs, queue payloads, and join/detect/send workers. The main source of
drag is that active runtime behavior still crosses compatibility seams.

## Simplification Rule

The backend should not preserve low-level permission flags as a long-term
operator model.

Target behavior should come from high-level lifecycle actions and engagement
state:

- `add`
- `edit`
- `pause`
- `archive`
- engagement `mode`

Separate `allow_join`, `allow_detect`, and `allow_post` flags should be
treated as migration-era compatibility state. The refactor may temporarily
project them for safe transition work, but the end state is that runtime
behavior is derived from status/mode/action semantics, not from hidden bot-
inaccessible permission toggles.

## Simplification Backlog

These are the main over-engineered backend elements to simplify as part of the
strangler plan. They are ranked by payoff and how much they unblock later
cleanup.

### 1. Low-Level Permission Flags

Problem:

- `allow_join`, `allow_detect`, and `allow_post` create a second control model
  that operators do not actually manage from the bot.
- Runtime behavior gets split across engagement state, target rows, worker
  checks, and compat helpers.

Direction:

- Replace permission-first behavior with lifecycle/state-driven behavior.
- High-level actions such as `add`, `edit`, `pause`, and `archive` become the
  meaningful controls.

### 2. Community-Scoped Runtime Settings As A First-Class Model

Problem:

- Active runtime behavior still inherits from community-scoped settings even
  though the product is centered on task-first engagements.
- This keeps the old community model looking canonical long after the live path
  moved elsewhere.

Direction:

- Keep community-scoped settings only as migration/fallback/compat state.
- Make engagement-scoped runtime policy the only active source of truth.

### 3. Targets As Mini Control-Plane Objects

Problem:

- Target rows currently do too much: reference, approval, permission, and
  runtime gating all mix together.
- This inflates the issue model and keeps `community_engagement_targets.py`
  heavier than it should be.

Direction:

- Reduce targets to reference and lifecycle semantics.
- Move any remaining active runtime decisions up to engagement policy/state.

### 4. Worker-Local Policy Exceptions

Problem:

- Runtime rules such as operator-send exceptions, quiet-hours checks,
  send-limit checks, and reservation behavior have been partly encoded inside
  worker modules.
- That makes workers both orchestrators and policy owners.

Direction:

- Keep workers as orchestration entrypoints only.
- Move reusable runtime decisions into backend services with direct tests.

### 5. Manual Job Concepts In The Operator Model

Problem:

- Join, detect, and send are infrastructure actions, but parts of the backend
  and compat API still treat them like first-class operator concepts.
- This exposes internal mechanics instead of the operator workflow.

Direction:

- Keep jobs and workers as implementation details.
- Keep the product model focused on engagement lifecycle and operator review
  flow, not on raw job verbs.

### 6. Split Runtime Sources For One Decision

Problem:

- A single behavior can currently depend on status, settings, target flags,
  membership state, and worker-local exceptions at the same time.
- This is a recurring cause of drift and hard-to-explain bugs.

Direction:

- Collapse each live decision onto one named owner.
- If a rule needs multiple inputs, that composition should happen in one
  runtime policy layer rather than across several modules.

### 7. Assigned-Account Ambiguity

Problem:

- Join, collection, detect, and send do not interpret assigned accounts the
  same way today.
- That means account choice is important enough to matter but not defined well
  enough to be predictable.

Direction:

- Make assigned-account behavior explicitly authoritative, or explicitly
  advisory, but not half-and-half.
- Do not “fix” this accidentally inside unrelated refactors.

### 8. Compat Facades That Still Look Canonical

Problem:

- `backend/api/routes/engagement.py` and
  `backend/services/community_engagement.py` still make the old surface look
  alive and central.
- This invites new code to land in the wrong place.

Direction:

- Fence compat facades early.
- Reduce them to assembly or migration-only roles, then prune them once active
  paths stop depending on them.

## Execution Order

Use this simplification order unless a concrete bug forces a different slice:

1. freeze and fence the active boundary
2. replace the mixed settings bridge with one active runtime layer
3. remove low-level permission state from active runtime decisions
4. extract worker-owned policy into services
5. narrow cockpit read models
6. simplify community-scoped runtime state down to compat/fallback only
7. resolve assigned-account semantics explicitly
8. prune compat facades and dead overlap

## Positive App Impact

These simplifications are not only code-health work. They should improve the
live engagement experience directly.

### 1. Permission-Triad Collapse

Expected app impact:

- fewer "why did join/detect/send not happen" failures caused by hidden flag
  drift between targets, settings, and worker checks
- no more need for repair-oriented issue flows such as permission resync just
  to restore the intended engagement state
- clearer operator behavior because lifecycle and mode become the only real
  controls

### 2. One Active Runtime Settings Model

Expected app impact:

- fewer precedence bugs where legacy community settings and task-first
  engagement settings disagree
- more predictable scheduler, collection, join, detect, and send behavior
- simpler bot edits because one write path controls the live runtime

### 3. Target Demotion

Expected app impact:

- less operator confusion because targets stop behaving like mini control-plane
  records
- fewer backend branches caused by mixing reference intake, approval, runtime
  permissions, and manual jobs on the same object
- simpler recovery flows because engagement lifecycle owns the runtime intent

### 4. Cockpit Read-Model Narrowing

Expected app impact:

- a more stable engagement cockpit because home, approvals, issues, detail, and
  sent feed stop depending on broad in-memory snapshots
- lower regression risk when changing one cockpit screen
- easier debugging of issue/approval visibility because each screen gets a
  clearer read boundary

### 5. Compat Bot/Admin Surface Reduction

Expected app impact:

- cleaner operator UX if the product remains task-first, because old
  permission-first controls stop competing with the wizard/cockpit model
- fewer support/debug situations caused by legacy manual join/detect/settings
  flows changing live behavior through side channels
- stronger product consistency across bot copy, callbacks, and backend
  semantics

### 6. Compat Facade Removal

Expected app impact:

- faster and safer engagement iteration because new work lands in the real
  active modules instead of old umbrella surfaces
- lower test and import indirection, which should reduce accidental regressions
  during follow-up engagement cleanup

## Scope

This plan covers backend-only ownership and runtime seams for:

- task-first engagement create, patch, settings, confirm, retry
- cockpit reads and cockpit mutations
- effective engagement settings used by scheduler, collection, join, detect,
  and send
- queue handoff contracts and worker preflight behavior
- compatibility-pruning once the active path is isolated

This plan does not cover:

- bot callback redesign beyond what backend ownership changes require
- prompt/profile admin redesign
- a full worker architecture rewrite
- a full product redesign beyond the lifecycle simplifications above

## Related Docs

- `wiki/code-index/engagement.md`
- `wiki/code-index/engagement/backend.md`
- `wiki/code-index/engagement/workers.md`
- `wiki/spec/api/engagement.md`
- `wiki/spec/queue/job-types/engagement.md`
- `wiki/spec/database/engagement.md`
- `wiki/spec/engagement/settings-membership.md`
- `wiki/plan/contract-surface-rationalization.md`
- `wiki/plan/engagement-cockpit-stabilization.md`
- `wiki/plan/engagement-account-behavior.md`
- `wiki/plan/engagement-send-draft-hotfix.md`

On overlap, treat backend-runtime notes in
`wiki/plan/engagement-task-first-cockpit-implementation.md` and
`wiki/plan/engagement-cockpit-stabilization.md` as secondary/history once this
plan is driving implementation.

## Active Keep-Set

Treat these as the contract-bearing backend modules during the refactor:

- `backend/api/routes/engagement_task_first.py`
- `backend/api/routes/engagement_cockpit.py`
- `backend/services/task_first_engagements.py`
- `backend/services/task_first_engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `backend/services/task_first_engagement_issues.py`
- `backend/queue/payloads.py`
- `backend/queue/client.py`
- `backend/workers/community_join.py`
- `backend/workers/engagement_detect*.py`
- `backend/workers/engagement_scheduler.py`
- `backend/workers/engagement_send.py`
- `backend/db/models_engagement.py`

Treat these as compat-only unless a phase explicitly extracts shared
primitives from them:

- `backend/api/routes/engagement.py`
- `backend/api/routes/engagement_targets.py`
- `backend/api/routes/engagement_settings_topics.py`
- `backend/api/routes/engagement_prompts_style.py`
- `backend/api/routes/engagement_candidates_actions.py`
- `backend/services/community_engagement.py`
- `backend/services/community_engagement_*.py`

## Refactor Rules

1. Do not add new active behavior through compat routers or compat export
   facades.
2. Preserve queue payload shapes and deterministic job IDs until an explicit
   migration plan says otherwise.
3. Preserve current bot-visible semantics while moving ownership.
4. Prefer extracting shared primitives over duplicating logic across active and
   compat paths.
5. Do not prune compat modules until active workers and active routes no
   longer depend on them.

## Phase 1: Freeze The Runtime Boundary

### Objective

Make it explicit which backend contracts are active, which are compat, and
 which modules are allowed to own runtime behavior.

Working artifact:

- `wiki/plan/engagement-backend-strangler-refactor/phase-1-classification-table.md`

### Changes

- Mark `backend/api/routes/engagement.py` as an assembly shell only.
- Mark `backend/services/community_engagement.py` as a compat export surface,
  not an active runtime authority.
- Record the active keep-set in code-index/spec/plan docs where needed.
- Add or tighten tests that lock:
  - task-first API responses
  - cockpit mutation responses
  - queue payload/job-id contracts
  - worker preflight outcomes

### Classification Criteria

Classify backend surfaces using these buckets:

- `active` - current source of truth for live task-first runtime behavior
- `shared primitive` - reusable logic worth keeping, but not as a top-level
  contract surface
- `compat` - still needed because active code, migrations, or legacy data
  depend on it
- `stale` - no longer trustworthy as a contract source

Use these questions to decide:

- does the active task-first bot/API path call it now
- do join/detect/send/scheduler runtime decisions depend on it now
- is its behavior locked by active tests
- does it own a real DB/queue invariant
- is it unique behavior or only a wrapper/facade/duplicate
- if removed today, would the active path break or only old admin paths break
- is it still required for migration or only retained as history

### Exit Criteria

- No new feature work is landing in compat route files.
- The active keep-set is documented and referenced consistently.
- Tests exist for the current active behavior before deeper extraction begins.

## Phase 2: Replace The Effective-Settings Bridge

### Objective

Replace the mixed legacy/task-first effective-settings lookup with one
canonical active runtime layer.

### Changes

- Introduce one backend service responsible for active runtime engagement
  policy/state, for example:
  - effective mode
  - assigned account
  - quiet hours
  - migration-time permission projection where still required
  - approval and reply-only gates
- Move scheduler, join, send, and any collection-triggered decisions onto
  that service.
- Migrate these paths first:
  - `backend/workers/engagement_scheduler.py`
  - `backend/workers/engagement_send.py`
  - `backend/workers/community_join.py`
  - any collection-triggered engagement gating that still routes through the
    legacy bridge
- Reduce `community_engagement_settings.py` to:
  - compat CRUD for legacy surfaces
  - temporary adapters only where still required
- Decide and document precedence when both old and task-first records exist.
- Add focused tests for:
  - active engagement wins over legacy settings
  - no-active-engagement fallback behavior
  - mode/account edge cases

### Exit Criteria

- Active workers no longer call the legacy effective-settings bridge.
- Settings precedence is owned by one explicit service and test suite.
- Scheduler target selection no longer unions models ad hoc in worker code.

## Phase 3: Remove Low-Level Permission State

### Objective

Replace low-level join/detect/post permission flags with lifecycle-driven
runtime semantics.

### Changes

- Stop treating `allow_join`, `allow_detect`, and `allow_post` as first-class
  operator-facing state.
- Derive runtime behavior from:
  - engagement status
  - engagement mode
  - high-level operator actions such as add, edit, pause, and archive
- Keep permission projection only as a temporary migration adapter while old
  rows and compat routes still exist.
- Remove or demote issue states that exist only because of low-level permission
  mismatches.
- Update runtime policy/docs/tests so permission flags are no longer the
  conceptual source of truth for active behavior.

### Exit Criteria

- Active runtime callers no longer require explicit join/detect/post permission
  flags to explain behavior.
- Target rows act as references and lifecycle state, not mini-permission
  objects.
- Permission-only issues and branches are either removed or clearly compat-only.

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
