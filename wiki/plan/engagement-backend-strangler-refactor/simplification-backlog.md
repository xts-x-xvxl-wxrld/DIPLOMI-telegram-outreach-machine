# Engagement Backend Strangler — Simplification Backlog

Items ranked by payoff and how much they unblock later cleanup.

## 1. Low-Level Permission Flags

Problem:

- `allow_join`, `allow_detect`, and `allow_post` create a second control model
  that operators do not actually manage from the bot.
- Runtime behavior gets split across engagement state, target rows, worker
  checks, and compat helpers.

Direction:

- Replace permission-first behavior with lifecycle/state-driven behavior.
- High-level actions such as `add`, `edit`, `pause`, and `archive` become the
  meaningful controls.

## 2. Community-Scoped Runtime Settings As A First-Class Model

Problem:

- Active runtime behavior still inherits from community-scoped settings even
  though the product is centered on task-first engagements.
- This keeps the old community model looking canonical long after the live path
  moved elsewhere.

Direction:

- Keep community-scoped settings only as migration/fallback/compat state.
- Make engagement-scoped runtime policy the only active source of truth.

## 3. Targets As Mini Control-Plane Objects

Problem:

- Target rows currently do too much: reference, approval, permission, and
  runtime gating all mix together.
- This inflates the issue model and keeps `community_engagement_targets.py`
  heavier than it should be.

Direction:

- Reduce targets to reference and lifecycle semantics.
- Move any remaining active runtime decisions up to engagement policy/state.

## 4. Worker-Local Policy Exceptions

Problem:

- Runtime rules such as operator-send exceptions, quiet-hours checks,
  send-limit checks, and reservation behavior have been partly encoded inside
  worker modules.
- That makes workers both orchestrators and policy owners.

Direction:

- Keep workers as orchestration entrypoints only.
- Move reusable runtime decisions into backend services with direct tests.

## 5. Manual Job Concepts In The Operator Model

Problem:

- Join, detect, and send are infrastructure actions, but parts of the backend
  and compat API still treat them like first-class operator concepts.
- This exposes internal mechanics instead of the operator workflow.

Direction:

- Keep jobs and workers as implementation details.
- Keep the product model focused on engagement lifecycle and operator review
  flow, not on raw job verbs.

## 6. Split Runtime Sources For One Decision

Problem:

- A single behavior can currently depend on status, settings, target flags,
  membership state, and worker-local exceptions at the same time.
- This is a recurring cause of drift and hard-to-explain bugs.

Direction:

- Collapse each live decision onto one named owner.
- If a rule needs multiple inputs, that composition should happen in one
  runtime policy layer rather than across several modules.

## 7. Assigned-Account Ambiguity

Problem:

- Join, collection, detect, and send do not interpret assigned accounts the
  same way today.
- That means account choice is important enough to matter but not defined well
  enough to be predictable.

Direction:

- Make assigned-account behavior explicitly authoritative, or explicitly
  advisory, but not half-and-half.
- Do not "fix" this accidentally inside unrelated refactors.

## 8. Compat Facades That Still Look Canonical

Problem:

- `backend/api/routes/engagement.py` and
  `backend/services/community_engagement.py` still make the old surface look
  alive and central.
- This invites new code to land in the wrong place.

Direction:

- Fence compat facades early.
- Reduce them to assembly or migration-only roles, then prune them once active
  paths stop depending on them.
