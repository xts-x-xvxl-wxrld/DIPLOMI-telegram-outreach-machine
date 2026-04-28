# Engagement Task-First Cockpit Slices 7-12

Detailed later build slices for the task-first `Engagements` cockpit.

## Slice 7: `Engagements` Home And Navigation Shell

Status: not started.

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

Status: blocked by Slice 6 and the finished Slice 2 contract.

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

Status: blocked by Slices 5-6.

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

Status: blocked by Slices 4-6.

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

Status: blocked by Slice 3 and bot routing work.

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

Status: blocked by all prior slices.

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
