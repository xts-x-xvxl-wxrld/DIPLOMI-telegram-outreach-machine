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

Status: not started.

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

Status: not started.

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

Status: not started.

Work items:

- Add bot API client methods for every new cockpit read-model and mutation
  endpoint.
- Add parser support for the `op:*` and `eng:*` callback families.
- Add callback helpers for scoped queues and wizard edit entry points.

Acceptance:

- Every documented task-first callback can be parsed and dispatched.
- API client tests cover request paths, query params, and DTO parsing.
- Callback payloads stay within Telegram length limits.
