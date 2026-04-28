# Engagement Task-First Cockpit Slices

Detailed build slices for delivering the task-first `Engagements` cockpit from
schema through bot rollout.

## Slice 1: Schema And Backfill Foundation

Status: planned.

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

Status: planned.

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

Status: planned.

Work items:

- Implement `GET /api/engagement/cockpit/home`.
- Implement global and scoped approvals read endpoints.
- Implement global and scoped issues read endpoints.
- Implement engagement list, engagement detail, and sent-message feed endpoints.
- Compute `pending_task` on engagement detail with the documented priority.

Acceptance:

- Each task-first screen renders from one explicit read-model payload.
- Bot handlers do not need to merge legacy settings, target, and candidate
  endpoints to render these surfaces.
- Scoped queue endpoints match the same DTO shape as global queue endpoints.

## Slice 4: Issue Generation Service

Status: planned.

Work items:

- Implement the explicit issue-generation rules for all confirmed issue types.
- Add issue de-duplication and recurrence behavior.
- Wire immediate issue removal on resolution.
- Expose the domain IDs needed for issue actions in the read model.

Acceptance:

- `Top issues` ordering is newest-first by issue timestamp.
- Re-resolved/reoccurred issues behave as fresh rows.
- No passive or duplicate issue variants leak into the queue.

## Slice 5: Semantic Draft And Issue Mutations

Status: planned.

Work items:

- Implement semantic draft approve/reject/edit endpoints.
- Implement `POST /api/engagement/cockpit/issues/{issue_id}/actions/{action_key}`.
- Implement semantic helper mutations for resume sending, target approval, and
  permission sync.
- Implement rate-limit detail read and quiet-hours read/write endpoints.

Acceptance:

- Every approval and issue action defined in the cockpit spec maps to a concrete
  endpoint.
- Result DTOs match the documented `approved`/`rejected`/`queued_update` and
  `resolved`/`next_step`/`blocked`/`stale` models.
- Quiet-hours and rate-limit subflows no longer require ad hoc payloads.

## Slice 6: Bot API Client And Callback Parsing

Status: planned.

Work items:

- Add bot API client methods for every new cockpit read-model and mutation
  endpoint.
- Add parser support for the `op:*` and `eng:*` callback families.
- Add callback helpers for scoped queues and wizard edit entry points.

Acceptance:

- Every documented task-first callback can be parsed and dispatched.
- API client tests cover request paths, query params, and DTO parsing.
- Callback payloads stay within Telegram length limits.

## Slice 7: `Engagements` Home And Navigation Shell

Status: planned.

Work items:

- Replace the old primary operator home with `Engagements`.
- Render the four defined home states from the new home read model.
- Implement `Approve draft`, `Top issues`, `My engagements`, `Add engagement`,
  and `Sent messages` entries in the correct order by state.
- Remove competing old primary navigation from the default operator path.

Acceptance:

- Home copy and action order match the source-of-truth spec.
- First-run, approval-focused, issue-present, and clear states all render from
  backend payloads only.
- Old and new primary homes do not coexist as parallel main paths.

## Slice 8: Wizard UI And Edit Reentry

Status: planned.

Work items:

- Implement the five-step add-engagement wizard screens.
- Implement single-topic picker behavior.
- Implement inline return flow from topic-create and account-create helpers.
- Implement engagement detail reentry into topic/account/mode steps.
- Implement final review, confirm, retry, and cancel behavior from the wizard
  DTOs.

Acceptance:

- `Add engagement` starts at Step 1 every time.
- Existing engagement edits reopen at the tapped step with prefilled values.
- Incomplete engagements remain hidden from `My engagements`.

## Slice 9: Approval Queue Controller

Status: planned.

Work items:

- Implement `Approve draft` controller rendering.
- Implement approve/reject confirmations.
- Implement draft edit request flow and `Updating draft` placeholder behavior.
- Implement scoped approval queue behavior launched from engagement detail.

Acceptance:

- Approve/reject/edit actions operate only through the documented semantic draft
  endpoints.
- Updated replacement drafts re-enter the queue correctly.
- Scoped approval flow returns to engagement detail when the engagement queue
  empties.

## Slice 10: Issue Queue Controller

Status: planned.

Work items:

- Implement `Top issues` controller rendering.
- Implement skip behavior.
- Implement direct fixes and `next_step` subflow routing.
- Implement rate-limit detail and quiet-hours edit screens.
- Implement scoped issue queue behavior launched from engagement detail.

Acceptance:

- Each issue type surfaces the documented action set only.
- Direct fixes refresh the queue correctly.
- Quiet-hours and rate-limit flows follow the documented DTOs and return rules.
- Scoped issue flow returns to engagement detail when its queue empties.

## Slice 11: Engagement Detail And Sent Messages

Status: planned.

Work items:

- Implement `My engagements` list rendering and paging.
- Implement engagement detail with `pending_task` priority handling.
- Implement resume behavior using `pending_task.resume_callback`.
- Implement `Sent messages` read-only feed and paging.

Acceptance:

- Engagement rows show the correct badges and ordering.
- Detail exposes at most one primary pending task.
- Sent messages stay read-only and newest-first.

## Slice 12: Legacy Retirement And Release Hardening

Status: planned.

Work items:

- Remove or hide legacy community-scoped primary operator paths.
- Keep only necessary compatibility/admin screens during transition.
- Remove legacy writes when no active task-first callback depends on them.
- Add regression coverage for stale, blocked, noop, and empty-state flows.
- Run full operator walkthroughs for create, edit, approve, reject, issue
  resolution, and sent-message review.

Acceptance:

- No competing old/new primary operator flows remain.
- Mixed-source screens are gone.
- Bot tests and targeted manual walkthroughs cover the documented happy paths
  and edge cases.
