# Engagement Task-First Cockpit Phases 5-9

Detailed later implementation phases for the task-first `Engagements` cockpit.

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
- run targeted manual operator walkthroughs for first engagement create, edit
  existing engagement, approve/reject draft, replacement-draft waiting, and the
  confirmed issue types

Exit criteria:

- documented happy-path and edge-path flows pass in bot tests
- rollout can proceed without exposing mixed-source UI
