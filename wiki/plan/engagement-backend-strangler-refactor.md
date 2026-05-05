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

## Shards

- [Simplification Backlog](engagement-backend-strangler-refactor/simplification-backlog.md)
- [Positive App Impact](engagement-backend-strangler-refactor/app-impact.md)
- [Active Keep-Set and Refactor Rules](engagement-backend-strangler-refactor/keep-set-and-rules.md)
- [Phases 1–3](engagement-backend-strangler-refactor/phases-1-3.md)
- [Phases 4–6, Test Strategy, and Acceptance Criteria](engagement-backend-strangler-refactor/phases-4-6.md)
