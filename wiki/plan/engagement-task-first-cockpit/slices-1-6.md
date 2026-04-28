# Engagement Task-First Cockpit Slices 1-6

Detailed early build slices for the task-first `Engagements` cockpit.

## Slice 1: Schema And Backfill Foundation

Status: done.

Work items:

- Add or finalize first-class `engagements` storage with `target_id`,
  `community_id`, `topic_id`, `status`, and audit fields.
- Finalize `engagement_settings` support for assigned account, sending mode, and
  quiet hours.
- Remove any remaining multi-topic-per-engagement assumptions from schema and
  services.
- Add idempotent backfill from legacy community-scoped setup into one
  engagement per target.

Acceptance:

- Migrations apply and roll back cleanly.
- Backfill can run multiple times without duplicating engagements.
- Draft engagements remain hidden from normal operator lists.
- One engagement per target is enforced.

## Slice 2: Engagement-Scoped Wizard Write Endpoints

Status: done enough for sequencing.

Work items:

- Implement `POST /api/engagements`.
- Implement `PATCH /api/engagements/{engagement_id}` for single-topic draft
  writes.
- Implement `PUT /api/engagements/{engagement_id}/settings`.
- Implement `POST /api/engagements/{engagement_id}/wizard-confirm`.
- Implement `POST /api/engagements/{engagement_id}/wizard-retry`.
- Remove the validation guard that still rejects `auto_limited`.

Acceptance:

- Wizard step writes are idempotent.
- Single-topic validation is enforced.
- `wizard-confirm` can validate, approve target when needed, enqueue detect, and
  activate atomically from the operator point of view.
- `wizard-retry` resets wizard-owned state without deleting the durable
  engagement row.

## Slice 3: Cockpit Read Models

Status: not started.

Repo status check:

- No `GET /api/engagement/cockpit/*` routes exist yet.
- `backend/api/schemas.py` currently stops at the task-first write DTOs; there
  are no cockpit home, queue, detail, or sent-feed schemas.
- The bot still renders review, settings, and activity surfaces by mixing
  legacy candidate, target, settings, and action reads.

Work items:

- Add an explicit read-model service for the task-first cockpit instead of
  extending the legacy community-scoped view helpers in place.
- Implement `GET /api/engagement/cockpit/home`.
- Implement `GET /api/engagement/cockpit/approvals` and
  `GET /api/engagement/cockpit/engagements/{engagement_id}/approvals` with one
  shared DTO shape.
- Implement `GET /api/engagement/cockpit/issues` and
  `GET /api/engagement/cockpit/engagements/{engagement_id}/issues` with one
  shared DTO shape.
- Implement `GET /api/engagement/cockpit/engagements`,
  `GET /api/engagement/cockpit/engagements/{engagement_id}`, and
  `GET /api/engagement/cockpit/sent`.
- Compute engagement detail `pending_task` in backend order only:
  `approvals`, then `approval_updates`, then `issues`.
- Exclude incomplete draft engagements from `My engagements`.
- Keep paging and empty-state behavior inside these read models so bot handlers
  only render returned payloads.

Backend and bot touchpoints:

- Backend routes: add a dedicated cockpit router module and include it from
  `backend/api/routes/engagement.py` rather than growing
  `engagement_task_first.py`, which is currently write-only.
- Backend schemas: add home, approvals, issues, engagement-list, engagement
  detail, pending-task, and sent-feed DTOs in `backend/api/schemas.py`.
- Backend services: add a cockpit read-model service next to
  `backend/services/task_first_engagements.py`; it will need
  `Engagement`, `EngagementSettings`, `EngagementTarget`,
  `EngagementCandidate`, `EngagementAction`, and
  `CommunityAccountMembership` state.
- Bot follow-on dependency: these endpoints must be complete before Slice 6
  starts wiring new client methods and handlers.

Dependencies:

- Depends on Slice 1 data model and the landed Slice 2 wizard write surface.
- Should land before Slice 4 issue queue generation is exposed through bot
  controllers, even if Slice 4 shares some helper projections.
- Should not depend on bot callback rewrites.

Acceptance:

- Each task-first screen renders from one explicit read-model payload.
- Bot handlers do not need to merge legacy settings, target, and candidate
  endpoints to render these surfaces.
- Scoped queue endpoints match the same DTO shape as global queue endpoints.
- Home payload matches the documented four states and preview visibility rules.
- `My engagements` and `Sent messages` are newest-first and return the closest
  valid page when the requested offset is now out of range.
- Engagement detail returns at most one primary pending task and never requires
  bot-side priority recomputation.

Tests:

- Add route/service coverage in `tests/test_engagement_api.py` for every new
  cockpit read endpoint.
- Cover home-state selection, approval placeholder ordering, issue ordering,
  `pending_task` priority, hidden draft engagements, and sent-feed ordering.
- Add stale-offset coverage for `My engagements` and `Sent messages`.

Rollout notes:

- Merge this slice before any new task-first bot screen ships.
- Keep legacy bot screens pointed at legacy endpoints until every required
  cockpit read model exists; do not ship mixed read sources.

## Slice 4: Issue Generation Service

Status: not started.

Repo status check:

- The confirmed issue taxonomy only exists in spec docs today.
- There is no backend issue-generation service, no cockpit issue DTO, and no
  persistence layer for skipped/recurring issue state.
- Existing engagement services expose the raw state needed to derive issues, but
  no single place consolidates it.

Work items:

- Implement the confirmed issue taxonomy only:
  `topics_not_chosen`, `account_not_connected`, `sending_is_paused`,
  `reply_expired`, `reply_failed`, `target_not_approved`,
  `target_not_resolved`, `community_permissions_missing`,
  `rate_limit_active`, `quiet_hours_active`, and `account_restricted`.
- Choose one backend implementation path and keep behavior identical to spec:
  materialized issue rows or synthesized-on-read issue views.
- Enforce one active issue of a given type per engagement.
- Re-surface a recurring condition as a fresh issue with a fresh timestamp.
- Remove resolved issues immediately from every cockpit read model.
- Carry the domain IDs needed for safe fixes:
  `engagement_id`, `candidate_id`, `target_id`, `community_id`, and
  `assigned_account_id` when applicable.
- Extract or reuse shared helpers for quiet-hours and rate-limit evaluation
  instead of duplicating divergent logic in multiple services.

Backend and bot touchpoints:

- Backend service: add a dedicated issue-generation layer next to
  `backend/services/task_first_engagements.py`.
- Backend models/helpers it will need: engagement status/settings, target
  approval and permissions state, candidate status (`failed`, `expired`,
  reviewable), joined account membership state, send-action timestamps, and
  quiet-hours logic currently embedded in `backend/services/community_collection.py`.
- Slice 3 read models should call this service rather than recreating issue
  rules inline.
- Bot follow-on dependency: Slice 10 should consume only the issue DTOs emitted
  here.

Dependencies:

- Depends on Slice 3 read-model structure, because the issue queue payload needs
  a stable DTO shape.
- Must land before Slice 5 semantic issue actions and Slice 10 issue queue UI.
- Can ship without any bot changes if only the backend issue service and tests
  are added.

Acceptance:

- `Top issues` ordering is newest-first by issue timestamp.
- Re-resolved/reoccurred issues behave as fresh rows.
- No passive or duplicate issue variants leak into the queue.
- Only confirmed issue types appear.
- `rate_limit_active` and `quiet_hours_active` do not appear unless a real
  engagement action is currently blocked.
- The issue payload exposes the domain IDs required for the documented fix
  actions without forcing bot-side lookup joins.

Tests:

- Add one backend test per confirmed issue type in `tests/test_engagement_api.py`
  or a dedicated cockpit-issue test module if coverage becomes too large.
- Cover de-duplication, recurrence after resolution, newest-first ordering, and
  immediate disappearance on resolution.
- Add negative coverage for passive rate-limit and quiet-hours cases.

Rollout notes:

- Keep this slice backend-only and mergeable. The bot should not guess issue
  generation rules while this is still in flight.
- If a persisted issue table is chosen, keep the external DTO identical to the
  synthesized-on-read contract so later slices do not care how issues are stored.

## Slice 5: Semantic Draft And Issue Mutations

Status: not started.

Repo status check:

- The only landed task-first mutations are `POST /api/engagements`,
  `PATCH /api/engagements/{engagement_id}`,
  `PUT /api/engagements/{engagement_id}/settings`,
  `POST /api/engagements/{engagement_id}/wizard-confirm`, and
  `POST /api/engagements/{engagement_id}/wizard-retry`.
- There are no task-first draft approval/reject/edit routes yet.
- There is no task-first issue-action route, no rate-limit detail route, and no
  task-first quiet-hours read/write route.

Work items:

- Implement `POST /api/engagement/cockpit/drafts/{draft_id}/approve`.
- Implement `POST /api/engagement/cockpit/drafts/{draft_id}/reject`.
- Implement `POST /api/engagement/cockpit/drafts/{draft_id}/edit`.
- Implement `POST /api/engagement/cockpit/issues/{issue_id}/actions/{action_key}`.
- Implement the helper routes or internal adapters needed for semantic
  task-first fixes:
  resume sending, target approval, permission sync, and candidate retry.
- Implement `GET /api/engagement/cockpit/issues/{issue_id}/rate-limit`.
- Implement `GET /api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`.
- Implement `PUT /api/engagement/cockpit/engagements/{engagement_id}/quiet-hours`.
- Return only documented semantic result shapes:
  `approved`, `rejected`, `queued_update`, `resolved`, `next_step`, `noop`,
  `blocked`, and `stale`.

Backend and bot touchpoints:

- Backend routes: add a cockpit mutation router instead of expanding the legacy
  candidate and target route files directly.
- Backend services: add a semantic mutation layer that may adapt to existing
  lower-level services such as candidate approve/reject/retry and target patch
  services, but keeps the cockpit contract stable.
- Backend schemas: add result DTOs for draft actions, issue actions, rate-limit
  detail, and quiet-hours read/write.
- Bot dependency: Slice 9, Slice 10, and Slice 11 should call only these
  semantic contracts, not raw candidate/target/settings mutations.

Dependencies:

- Depends on Slice 4 issue generation so `issue_id` and `action_key` map to
  stable issue objects.
- Should land before Slice 6 client wiring and before any queue controller work.
- Can reuse existing lower-level services internally, but the bot contract must
  not expose those lower-level shapes.

Acceptance:

- Every approval and issue action defined in the cockpit spec maps to a concrete
  endpoint.
- Result DTOs match the documented `approved`/`rejected`/`queued_update` and
  `resolved`/`next_step`/`blocked`/`stale` models.
- Quiet-hours and rate-limit subflows no longer require ad hoc payloads.
- Direct fixes resolve through one tap and guided fixes return `next_callback`
  without the bot inventing routing.
- Quiet-hours writes support `updated`, `noop`, `blocked`, and `stale` exactly
  as documented.
- Draft edit requests create `Updating draft` semantics instead of mutating the
  visible approved text in place.

Tests:

- Add API tests for every draft action result path and every issue action family
  in `tests/test_engagement_api.py`.
- Cover approve/reject stale and blocked cases, edit-to-placeholder behavior,
  direct fix success, `next_step` routing, rate-limit stale handling, and
  quiet-hours save/off/noop validation.
- Add regression tests proving bot callers never need raw target permission or
  generic settings patch payloads for task-first issue fixes.

Rollout notes:

- Merge these routes before Slice 6 so the bot client can target stable paths.
- Keep any temporary adapters entirely behind the cockpit mutation layer; do not
  let new bot handlers call legacy write routes directly.

## Slice 6: Bot API Client And Callback Parsing

Status: not started.

Repo status check:

- `bot/api_client.py` exposes legacy candidate, target, settings, topic, and
  action methods only; there are no client methods for cockpit home, approvals,
  issues, detail, or sent-feed routes.
- `bot/ui_common.py` only knows the old `op:*`, `eng:home`, `eng:cand:*`,
  `eng:set:*`, `eng:topic:*`, `eng:actions:*`, and admin callback families.
- `tests/test_bot_ui.py` and `tests/test_bot_api_client.py` currently assert
  only the legacy callback matrix and legacy API paths.

Work items:

- Add bot API client methods for every Slice 3 and Slice 5 route:
  home, approvals, scoped approvals, issues, scoped issues, engagement list,
  engagement detail, sent feed, draft actions, issue actions, rate-limit
  detail, quiet-hours read/write, and task-first wizard writes.
- Add callback constants and parser support for:
  `op:approve`, `op:issues`, `op:engs`, `op:sent`, `op:add`,
  `eng:appr:*`, `eng:iss:*`, `eng:mine:*`, `eng:det:*`, `eng:sent:*`, and the
  expanded `eng:wz:*` edit/start callbacks.
- Keep callback payloads under Telegram's 64-byte limit with UUID-sized IDs.
- Add helper builders for scoped queue routes and `pending_task.resume_callback`
  targets so controllers do not hand-build strings.
- Update shared UI exports so new callback constants are available from
  `bot/ui.py`.

Backend and bot touchpoints:

- Bot client: `bot/api_client.py`.
- Callback constants and parser: `bot/ui_common.py`.
- Re-export surface: `bot/ui.py`.
- Dispatcher follow-on dependency: `bot/callback_handlers.py` and the wizard /
  queue controller modules added in later slices.

Dependencies:

- Depends on finished Slice 3 read models and Slice 5 mutation routes.
- Should land before Slice 8-11 bot-controller work so those slices build on
  stable client helpers and callback parsing.
- Can merge before the UI cutover, because adding parser and client support does
  not expose the new cockpit on its own.

Acceptance:

- Every documented task-first callback can be parsed and dispatched.
- API client tests cover request paths, query params, and DTO parsing.
- Callback payloads stay within Telegram length limits.
- New callback parsing does not break the legacy families that still exist until
  Slice 12.
- `pending_task.resume_callback` values from backend payloads can be passed
  through without bot-side rewriting.

Tests:

- Extend `tests/test_bot_api_client.py` for every new cockpit route and mutation
  path, including query params and result payload passthrough.
- Extend `tests/test_bot_ui.py` for callback parsing and callback-length limits
  across all new `op:*` and `eng:*` families.
- Add minimal dispatcher tests once `bot/callback_handlers.py` begins routing
  these families, but keep the parser/client coverage here.

Rollout notes:

- Do not repoint the operator home yet. This slice should only make the new
  callback/client surface available.
- Keep legacy callbacks intact until Slice 12 removes the old primary path.
