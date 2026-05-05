# Engagement Backend Strangler — Phases 1–3

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
