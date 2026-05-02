# Engagement Cockpit Verification: Phase 3 Test Coverage Review

Phase 3 maps the active task-first cockpit surfaces to the current bot and API
tests, then separates strong contract coverage from permissive assertions that
still allow routing drift.

Companions:

- `wiki/plan/engagement-cockpit-verification/phase-1-spec-baseline.md`
- `wiki/plan/engagement-cockpit-verification/phase-2-code-mapping.md`

## Coverage Matrix

| Surface | Existing tests | Coverage strength | Missing assertions / permissive gaps |
| --- | --- | --- | --- |
| `Engagements` home | `tests/test_bot_engagement_home_handlers.py` covers home copy, all four home states, button ordering, no home/back controls, `eng:home` render, and `op:*` router smoke tests. | Strong on visible copy and state ordering. | The markup tests explicitly bless `Approve draft -> eng:appr:list:0` and `Top issues -> eng:iss:list:0`, so they currently permit drift from the spec's home-emitted `op:approve` and `op:issues` contract. The `op:*` routing tests mostly assert that something rendered, not that the exact destination controller or callback family was used. |
| `Approve draft` | `tests/test_bot_engagement_approval_handlers.py` covers global/scoped queue rendering, empty states, placeholder-only state, local approve/reject confirmations, approve/reject result handling, edit-request capture, and approval-store helpers. `tests/test_engagement_api.py` covers durable update placeholders and semantic draft action results. | Strong on queue states and semantic backend results. | `show_draft_card()` tests allow fallback rendering for a non-current `draft_id` and do not require reopening the requested item from the right payload family. No test asserts scoped completion returns to `eng:det:open:<engagement_id>`. No test asserts the non-wizard footer uses `<< Engagements` instead of the old top-level home model. |
| `Top issues` | `tests/test_bot_engagement_issue_handlers.py` covers global/scoped queue rendering, skip state, resolved/stale/noop/blocked action results, local rate-limit and quiet-hours pseudo-actions, and quiet-hours save flows. `tests/test_engagement_api.py` covers semantic issue-action results, issue generation, and quiet/rate backend shapes. | Strong on backend semantic result types and basic handler branching. | `next_step` bot coverage is weak: the main test only checks that rendered text contains the callback or "Next step", not that the bot dispatches the returned `next_callback`. `show_issue_card()` tests do not prove reopening the requested `issue_id`; they only prove the current issue or a not-found message renders. Scoped empty-queue tests assert text only, not the return callback. No bot test asserts the task-first footer contract outside the wizard. |
| Rate-limit detail | `tests/test_bot_engagement_issue_handlers.py` covers `show_rate_limit_detail()` API calls, displayed fields, and API error handling. `tests/test_engagement_api.py` covers the backend `ready` shape and the backend `next_callback` to reopen the issue card. | Strong on backend data shape and read-only field coverage. | No bot-level test asserts that issue `next_step` actions actually follow the backend callback family into the rate-limit surface. No test asserts the detail screen's `Back` target or the `<< Engagements` footer contract. |
| Quiet-hours edit | `tests/test_bot_engagement_issue_handlers.py` covers loading current state, storing pending edit state, erroring when no engagement is found, valid/off/invalid saves, and clearing pending edit state. `tests/test_engagement_api.py` covers quiet-hours read/write semantic result shapes. | Strong on the typed text-save implementation that exists today. | Coverage is permissive relative to the active spec: it blesses the current free-text `HH:MM-HH:MM` / `off` editor rather than the spec's explicit action set. No test proves the edit uses the engagement that belongs to the requested issue rather than the queue's current issue. No bot test asserts `noop` returns to the same issue card or that save/off follow the right callbacks. |
| `My engagements` | `tests/test_bot_engagement_detail_handlers.py` covers list formatting, row badges, paging labels, list rendering, offsets, and empty state. `tests/test_engagement_api.py` covers offset clamping and sending-mode labels. | Strong on list shape and paging behavior. | The current tests bless the preview-screen implementation because row-button tests only require engagement IDs in callback data, and flow tests explicitly cover `show_engagement_preview()`. There is no test asserting row taps should open full engagement detail directly, which the active spec expects. Footer target assertions are also missing. |
| Engagement detail | `tests/test_bot_engagement_detail_handlers.py` covers detail formatting, pending-task labels, edit buttons, API errors, and markup presence. `tests/test_engagement_api.py` covers pending-task priority and backend `resume_callback` selection. | Strong on backend pending-task priority and detail read-model shape. | Bot tests do not assert that `eng:mine:open:<id>` should bypass preview and land on full detail. Edit-button tests only check that topic/account/mode callbacks exist, not that they match the precise wizard reentry contract. Footer target assertions are missing. |
| Pending-task resume | `tests/test_bot_engagement_detail_handlers.py` checks no-pending-task fallback, missing `resume_callback` fallback, and that some output occurs when resume is attempted. `tests/test_engagement_api.py` verifies backend `resume_callback` values. | Strong on backend resume-callback generation. | Bot coverage is weak where the real risk lives: it does not assert that `handle_engagement_resume()` dispatches the backend `resume_callback`. The current test even treats "callback stored" or a fallback detail render as acceptable, so broken resume routing would still pass. |
| `Sent messages` | `tests/test_bot_engagement_detail_handlers.py` covers formatting, rendering, paging labels, offsets, and empty state. `tests/test_engagement_api.py` covers newest-first ordering, offset clamping, and filtering out join-audit actions. | Strong on feed ordering and paging behavior. | No bot test asserts the non-wizard footer target or that the screen stays read-only without row-open callbacks. |
| `Add engagement` wizard | `tests/test_bot_engagement_wizard.py` covers step rendering, no `Home` button, topic/account subflows, retry, cancel confirmation, and edit reentry. `tests/test_engagement_task_first_wizard_api.py` and `tests/test_engagement_api.py` cover confirm validation, join/detect enqueueing, target approval, and settings acceptance including `auto_limited`. | Strong on the shipped wizard implementation and backend confirm semantics. | Several tests currently bless behavior that conflicts with the active spec: `eng:wz:start` resuming previous wizard state, and step 4 mapping `watching/suggesting/sending` to `observe/suggest/require_approval`. Confirm tests usually assert generic success/error copy, not that `validation_failed` routes to the returned field step or that `confirmed` / `stale` / `retry` follow the returned `next_callback`. |
| Engagement edit via wizard | `tests/test_bot_engagement_wizard.py` covers topic/mode edit reentry and local `return_callback` state changes. | Moderate. | Existing tests only prove that edit reentry opens a plausible step and that some state changes after a save. They do not assert the exact callback target after successful edit completion, and they currently preserve legacy mode labels in the pending state. |
| Navigation outside the wizard | Home tests ensure no back/home controls on `Engagements`. Some list/detail tests check pager labels or the presence of button rows. | Weak. | There is no dedicated regression test asserting that non-wizard cockpit screens use `Back` plus `<< Engagements` and do not surface top-level `Home`. This is one of the clearest shared gaps across approvals, issues, list/detail, sent feed, and rate/quiet subflows. |
| Navigation inside the wizard | `tests/test_bot_engagement_wizard.py` asserts no `Home` button on step screens and cancel confirmation, plus `Back` visibility on some screens. | Moderate to strong. | Coverage does not assert the fresh-start rule for `Add engagement`; current tests do the opposite by verifying resume behavior. There is also no test that the step flow uses the spec's `Draft` / `Auto send` labels instead of the legacy internal mode vocabulary. |

## High-Signal Gaps To Harden Next

These are the most important missing assertions for Phase 4:

1. Issue `next_step` actions should dispatch the returned `next_callback`, not
   just print it.
2. `eng:iss:open:<issue_id>` should reopen the requested issue card by
   `issue_id`, not silently fall back to whatever issue is currently loaded.
3. Quiet-hours issue flows should use the issue's actual `engagement_id`, not
   whichever issue is currently first in the queue payload.
4. `eng:appr:open:<draft_id>` should reopen the requested draft by `draft_id`,
   not a placeholder card when the draft is not current.
5. Non-wizard screens should assert `Back` plus `<< Engagements` and reject the
   older top-level `Home` footer model.
6. `eng:det:resume:<engagement_id>` should assert that the handler follows the
   backend `resume_callback`.
7. Wizard tests should stop blessing resume-on-start and legacy
   `watching/suggesting/sending` mode semantics if the active task-first spec is
   the source of truth.

## Tests That Currently Bless Drift

- `tests/test_bot_engagement_home_handlers.py`
  `test_cockpit_home_markup_approval_queue_button_routes_to_appr_list`
  and `test_cockpit_home_markup_issues_button_routes_to_iss_list`
  encode the current callback drift as expected behavior.
- `tests/test_bot_engagement_wizard.py`
  `test_wizard_resume_shows_appropriate_step` and
  `test_wizard_resume_at_mode_step`
  encode resumable `eng:wz:start` behavior that conflicts with the active spec.
- `tests/test_bot_engagement_wizard.py`
  `test_wizard_step4_level_watching_maps_to_observe`,
  `test_wizard_step4_level_suggesting_maps_to_suggest`, and
  `test_wizard_step4_level_sending_maps_to_require_approval`
  encode the legacy mode vocabulary instead of the active `Draft` /
  `Auto send` contract.
- `tests/test_bot_engagement_issue_handlers.py`
  `test_handle_issue_action_next_step_navigates`
  treats printing the callback string as sufficient, so broken navigation still
  passes.
- `tests/test_bot_engagement_approval_handlers.py`
  `test_show_draft_card_for_non_current_draft_still_renders`
  allows placeholder reopening instead of proving the requested draft is truly
  reopened.

## Phase 4 Priority Order

1. Replace permissive navigation assertions that currently bless drift.
2. Add handler-level tests for exact callback dispatch and exact reopen-by-ID
   behavior.
3. Add footer assertions across non-wizard surfaces.
4. Add wizard contract tests only after deciding whether the active spec or the
   shipped legacy wizard semantics should win.
