# Engagement Cockpit Verification Audit Note

Single retained audit note for the task-first engagement cockpit cleanup.

This note preserves the compact verification baseline after the larger wrapper
plan and drift-heavy verification shards were removed during contract-surface
cleanup.

## Goal

Audit the task-first Telegram engagement cockpit against the active UX spec,
verify each operator path in code, and harden the contract with regression
tests before fixing confirmed defects.

## Authority Order

1. `wiki/spec/bot-cockpit-experience/engagement-task-first-cockpit.md`
2. `wiki/spec/bot/engagement-add-wizard.md` for wizard implementation details
   only
3. `wiki/spec/bot-cockpit-experience/attention-and-navigation.md` for
   compatibility notes only

If callback examples conflict, the task-first cockpit shard wins.

## Scope

In scope:

- `Engagements` home state and button ordering
- approval queue and draft review actions
- issue queue and issue-fix subflows
- `My engagements`
- engagement detail and resume behavior
- sent-message feed
- add/edit wizard flows
- non-wizard vs wizard navigation rules
- bot/API contract alignment for task-first callbacks

Out of scope:

- legacy pre-task-first engagement home behavior
- discovery cockpit redesign work
- non-bot frontend work
- new engagement product features not already specified

## Shared Navigation Rules

- Home is `Engagements` and shows no `Back` or home button.
- Outside the wizard, secondary screens use `Back` plus `<< Engagements`.
- Inside the wizard, show step-by-step `Back` only; do not show
  `<< Engagements`.
- Returning to the engagement cockpit always uses `eng:home`.
- Returning to the top-level operator cockpit uses `op:home`.
- Prefer backend `next_callback` and `resume_callback` values over bot-inferred
  routing whenever the payload provides them.

## Legacy / Compat Note

Older admin/setup and candidate-review surfaces still exist in code, but they
are not the active `/engagement` contract. Treat them as compatibility paths
only, not as operator-source-of-truth behavior for the task-first cockpit.

## Surface Matrix

| Surface | Entry callback(s) | Expected behavior | Return / dependency notes |
| --- | --- | --- | --- |
| `Engagements` home | `eng:home` | Render one of four home states with the five always-visible destinations: `Approve draft`, `Top issues`, `My engagements`, `Add engagement`, `Sent messages`. Order changes by state; visibility does not. | Home emits only `op:approve`, `op:issues`, `op:engs`, `op:add`, and `op:sent`. No back/home footer lives on this screen. |
| `Approve draft` | `op:approve`, `eng:appr:list:0`, `eng:appr:eng:<engagement_id>`, `eng:appr:open:<draft_id>` | One-draft controller titled `Approve draft`; supports local confirm for approve/reject plus draft edit entry. | Approve, reject, and completed edit refresh the same approval controller; global empty queue returns `eng:home`; scoped queue exhaustion returns `eng:det:open:<engagement_id>`; early edit exit returns `eng:appr:open:<draft_id>`. |
| `Top issues` | `op:issues`, `eng:iss:list:0`, `eng:iss:eng:<engagement_id>`, `eng:iss:open:<issue_id>` | One-issue controller titled `Top issues`; shows exact issue labels and one-by-one issue work. | `resolved` and `stale` refresh the same controller; global empty queue returns `eng:home`; scoped queue exhaustion returns `eng:det:open:<engagement_id>`; `next_step` must follow backend `next_callback`; early fix exit returns `eng:iss:open:<issue_id>`. |
| Rate-limit detail | issue action `eng:iss:act:<issue_id>:ratelimit`, then backend `next_callback` into `eng:rate:*` | Open a read-only `Rate limit active` detail screen with blocked account, short reason, and next retry time when available. | `Back` returns to the same issue card. If the issue clears before open, refresh the current issue controller instead. |
| Quiet-hours edit | issue action `eng:iss:act:<issue_id>:quiet`, then backend `next_callback` into `eng:quiet:*` | Open `Change quiet hours` prefilled with the engagement's current quiet-hours values; allow `Edit start`, `Edit end`, `Turn off quiet hours`, `Save`, and `Cancel`. | `Cancel` and write `noop` return to `eng:iss:open:<issue_id>`; successful save returns to the issue controller; write handling depends on the issue's actual `engagement_id`; `blocked` stays on the quiet-hours screen; `stale` refreshes the issue controller. |
| `My engagements` | `op:engs`, `eng:mine:list:0`, `eng:mine:open:<engagement_id>` | Show completed engagements only, newest first, with sending-mode badge first and issue-count badge second when non-zero. | Uses `Newer` / `Older` paging. Opening a row routes to `eng:det:open:<engagement_id>`. Secondary screens use `Back` plus `<< Engagements`. |
| Engagement detail | `eng:det:open:<engagement_id>` | Read-focused detail screen for target, topic, account, sending mode, approvals, and issues. Topic, account, and mode reopen the wizard at that step. | Outside-wizard footer rules apply. The detail view may expose one primary pending-task action, not multiple. |
| Pending-task resume | `eng:det:resume:<engagement_id>` | Resume the one primary pending task surfaced on detail. | The bot must use `pending_task.resume_callback` from the detail payload instead of recomputing priority locally. Scoped approvals/issues resumed from detail return to the same detail screen when exhausted. |
| `Sent messages` | `op:sent`, `eng:sent:list:0` | Read-only global sent-message feed, newest first, no row-open detail in v1. | Uses `Newer` / `Older` paging and the normal outside-wizard footer pattern. |
| `Add engagement` wizard | `op:add`, `eng:wz:start` | Always start fresh at Step 1 (`Target`) and do not restore abandoned setup. No draft engagement is created before target resolution succeeds. | Step writes advance through `Target -> Topic -> Account -> Sending mode -> Final review`. `Confirm` and `Retry` follow backend workflow results, including returned `next_callback` values. |
| Engagement edit via wizard | `eng:det:edit:<engagement_id>:topic`, `eng:det:edit:<engagement_id>:account`, `eng:det:edit:<engagement_id>:mode`, plus `eng:wz:edit:<engagement_id>:<step>` | Reopen the full wizard with prefilled values at the tapped step; the operator can still go backward to earlier steps. | Edit confirmation updates the existing engagement atomically and returns to engagement detail. Wizard navigation rules still apply while editing. |
| Navigation outside the wizard | applies to `eng:appr:*`, `eng:iss:*`, `eng:mine:*`, `eng:det:*`, `eng:sent:*`, `eng:rate:*`, and `eng:quiet:*` | `Back` goes one step back; `<< Engagements` leaves immediately for the engagement home. | Do not use the older `Home` footer model. `eng:home` is the only cockpit-home return target. |
| Navigation inside the wizard | applies to `eng:wz:*` screens | Show only step-by-step `Back`; do not show `<< Engagements`; leaving is handled by wizard controls such as `Cancel`, `Retry`, and `Confirm`. | `Cancel` requires local confirmation; `wizard-confirm` and `wizard-retry` must follow returned backend routing instead of bot-inferred destinations. |

## Verification Workflow

1. Use the matrix below as the intended behavior baseline.
2. Map each surface to bot handlers, API endpoints, and tests.
3. Identify mismatches between spec, code, and tests.
4. Add or tighten regression tests for the real contract.
5. Fix only confirmed failures or contract drift.

## Code Anchors

- `bot/engagement_commands_daily.py`
- `bot/callback_handlers.py`
- `bot/ui_engagement_home.py`
- `bot/engagement_approval_flow.py`
- `bot/engagement_issue_flow.py`
- `bot/engagement_detail_flow.py`
- `bot/engagement_wizard_flow.py`
- `backend/api/routes/engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `tests/test_bot_engagement_cockpit_home.py`
- `tests/test_bot_engagement_home_handlers.py`
- `tests/test_bot_engagement_issue_handlers.py`
- `tests/test_bot_engagement_detail_handlers.py`
- `tests/test_bot_engagement_wizard.py`
- `tests/test_engagement_api.py`

## Exit Criteria

This audit thread is done when:

- each in-scope engagement surface is mapped to spec, code, and tests
- critical navigation paths have regression tests for the real contract
- known mismatches are either fixed or recorded as explicit follow-up work
- the engagement cockpit no longer relies on placeholder assertions for core
  navigation behavior

## Supersedes

This audit note supersedes the removed wrapper and drift-heavy verification
shards:

- `wiki/plan/engagement-cockpit-verification.md`
- `wiki/plan/engagement-cockpit-verification/phase-2-code-mapping.md`
- `wiki/plan/engagement-cockpit-verification/phase-3-test-coverage-review.md`

## Normalization Notes

- Treat `eng:wz:*` as the active callback family for add/edit wizard work during
  verification, even though the older wizard shard still documents
  `eng:wizard:*`.
- Treat `Top issues` as the only active top-level issue surface; older
  `Needs attention` language is superseded.
- Treat `Back` plus `<< Engagements` as the only active outside-wizard footer
  contract; older `Home` footer behavior is superseded.
