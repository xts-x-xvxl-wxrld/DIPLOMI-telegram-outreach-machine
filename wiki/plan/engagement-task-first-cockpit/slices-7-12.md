# Engagement Task-First Cockpit Slices 7-12

Detailed later build slices for the task-first `Engagements` cockpit.

## Slice 7: `Engagements` Home And Navigation Shell

Status: not started.

Repo status check:

- The current operator shell still routes the engagement entrypoint to the old
  engagement home and candidate-review surfaces.
- There is no `Engagements` home renderer for the four task-first home states.
- The new `op:approve`, `op:issues`, `op:engs`, `op:sent`, and `op:add`
  callbacks are not wired anywhere yet.

Work items:

- Replace the old primary operator home with `Engagements`.
- Render the four defined home states from the new home read model.
- Implement `Approve draft`, `Top issues`, `My engagements`, `Add engagement`,
  and `Sent messages` entries in the correct order by state.
- Remove competing old primary navigation from the default operator path.
- Add top-level handlers for the full `op:*` home callback set and keep them as
  thin routers to the Slice 3 home and list payloads.
- Hide `Sent messages` in the approval-focused state even if sent rows exist.
- Keep `Add engagement` present in every non-first-run state.
- Apply the documented navigation rule: no back or home controls on the
  `Engagements` home itself.

Backend and bot touchpoints:

- Bot callback routing: `bot/callback_handlers.py`.
- Bot shell/UI helpers: `bot/ui_common.py`, `bot/ui.py`, and either
  `bot/ui_engagement.py` or a new task-first cockpit UI module.
- Bot formatting: add an `Engagements` home formatter instead of reusing the
  legacy engagement-home copy.
- Read dependency: consume only `GET /api/engagement/cockpit/home`.

Dependencies:

- Depends on Slice 3 for the home payload and on Slice 6 for client/callback
  support.
- Should land late, after Slice 8-11 screens exist, so the new home does not
  point into half-built controllers.
- Does not need legacy primary-path deletion yet; that belongs to Slice 12.

Acceptance:

- Home copy and action order match the source-of-truth spec.
- First-run, approval-focused, issue-present, and clear states all render from
  backend payloads only.
- Old and new primary homes do not coexist as parallel main paths.
- Home visibility rules for `Approve draft`, `Top issues`, `My engagements`,
  `Add engagement`, and `Sent messages` match the spec exactly.
- Tapping the home preview rows routes to the same controllers as the matching
  primary actions.

Tests:

- Add bot-handler coverage for all four home states and action ordering.
- Add UI/formatting coverage for no-nav home rendering and preview visibility.
- Add regression coverage that the default engagement entrypoint no longer
  renders the legacy candidate-review home once cutover is enabled.

Rollout notes:

- Gate this slice behind completed downstream controllers; do not make
  `Engagements` the primary shell until `Approve draft`, `Top issues`,
  `My engagements`, detail, and sent-feed screens are real.
- Keep `/engagement` or any equivalent primary operator shortcut pointing to one
  shell only.

## Slice 8: Wizard UI And Edit Reentry

Status: blocked by Slice 6 and the finished Slice 2 contract.

Repo status check:

- `bot/engagement_wizard_flow.py` currently keeps community-scoped local state
  such as `community_id`, `target_id`, `topic_ids`, `account_id`, and `level`.
- The existing wizard is multi-topic and community-settings-based; it does not
  use the new engagement-scoped create/patch/settings/confirm/retry endpoints.
- Existing wizard tests in `tests/test_bot_engagement_wizard.py` assert legacy
  topic toggling, legacy settings writes, and old callback flows.

Work items:

- Implement the five-step add-engagement wizard screens.
- Implement single-topic picker behavior.
- Implement inline return flow from topic-create and account-create helpers.
- Implement engagement detail reentry into topic/account/mode steps.
- Implement final review, confirm, retry, and cancel behavior from the wizard
  DTOs.
- Replace local wizard state shape with engagement-scoped state centered on
  `engagement_id`, one selected `topic_id`, assigned account, mode, and stored
  return target.
- Keep Step 1 local-only until target resolution succeeds; only then create or
  reuse the draft engagement through `POST /api/engagements`.
- Save Step 2 through `PATCH /api/engagements/{engagement_id}`.
- Save Step 3 and Step 4 through
  `PUT /api/engagements/{engagement_id}/settings`.
- Use `POST /api/engagements/{engagement_id}/wizard-confirm` and
  `POST /api/engagements/{engagement_id}/wizard-retry` for final review actions.
- Preserve the documented early-exit return behavior for draft-edit and
  issue-fix reentry.
- Keep the topic and account pickers paged when needed, with selected state
  preserved across pages.

Acceptance:

- `Add engagement` starts at Step 1 every time.
- Existing engagement edits reopen at the tapped step with prefilled values.
- Incomplete engagements remain hidden from `My engagements`.
- The wizard no longer writes multi-topic arrays or community-scoped engagement
  settings as its primary durable state.
- `Retry` restarts from Step 1 using the backend retry contract instead of local
  state resets only.
- `Cancel` is local confirmation only and does not silently delete the durable
  engagement row.

Backend and bot touchpoints:

- Bot flow/controller: `bot/engagement_wizard_flow.py`.
- Bot wizard markup: `bot/ui_engagement_wizard.py`.
- Bot runtime/pending-state helpers: `bot/runtime_base.py` and existing
  pending-edit / return-context storage.
- Bot client methods from Slice 6 for the new task-first endpoints.
- Follow-on entrypoints: `eng:wz:start`, `eng:wz:edit:<engagement_id>:topic`,
  `eng:wz:edit:<engagement_id>:account`, and
  `eng:wz:edit:<engagement_id>:mode`.

Dependencies:

- Depends on Slice 2 writes and Slice 6 client/callback wiring.
- Should be available before Slice 9 and Slice 10 so approval and issue flows
  can send operators back into the wizard.
- Can merge before the main shell cutover in Slice 7.

Tests:

- Rewrite or extend `tests/test_bot_engagement_wizard.py` around the new
  engagement-scoped callbacks and client calls.
- Cover Step 1 target resolution, single-topic selection, account and mode
  saves, confirm/validation_failed/blocked/stale handling, retry, cancel, and
  detail-step reentry.
- Add regression coverage that unfinished drafts remain hidden from
  `My engagements`.

Rollout notes:

- Land the new wizard flow behind the new `eng:wz:*` callbacks before changing
  the primary home entrypoint.
- Keep any temporary join-job or topic-create helper reuse as implementation
  detail only; the persisted wizard state must live on the engagement record.

## Slice 9: Approval Queue Controller

Status: blocked by Slices 5-6.

Repo status check:

- The repo already has a reply-opportunity review flow in
  `bot/engagement_review_flow.py`, but it is driven by legacy
  `eng:cand:*` candidate status queues.
- There is no task-first approval controller for `eng:appr:*`.
- Existing queue tests target the candidate-review contract, not the task-first
  draft approval contract.

Work items:

- Implement `Approve draft` controller rendering.
- Implement approve/reject confirmations.
- Implement draft edit request flow and `Updating draft` placeholder behavior.
- Implement scoped approval queue behavior launched from engagement detail.
- Add handlers for `eng:appr:list:<offset>`, `eng:appr:eng:<engagement_id>`,
  `eng:appr:open:<draft_id>`, `eng:appr:ok:<draft_id>`,
  `eng:appr:okc:<draft_id>`, `eng:appr:no:<draft_id>`,
  `eng:appr:noc:<draft_id>`, and `eng:appr:edit:<draft_id>`.
- Keep local confirmation UI for approve/reject and reserve backend calls for
  the confirm step only.
- Reuse pending-edit infrastructure for free-text draft edit requests, but post
  only the semantic edit request to the backend.
- Render placeholder-only queues as `Waiting for updated drafts` rather than
  kicking the operator out.

Acceptance:

- Approve/reject/edit actions operate only through the documented semantic draft
  endpoints.
- Updated replacement drafts re-enter the queue correctly.
- Scoped approval flow returns to engagement detail when the engagement queue
  empties.
- Global approval queues stay on the same screen and render `No drafts for
  approval` when the final draft disappears.
- Early exit from the edit-request subflow returns to the same draft card.
- Approval routing refreshes the same scoped or global controller instead of
  jumping home.

Backend and bot touchpoints:

- Bot controller: either adapt `bot/engagement_review_flow.py` or add a new
  approval-flow module with no `eng:cand:*` assumptions.
- Bot callback dispatcher: `bot/callback_handlers.py`.
- Bot formatting/UI helpers for the approval card and placeholder states.
- Backend dependency: Slice 3 approval read models plus Slice 5 draft-action
  mutations.

Dependencies:

- Depends on Slice 5 mutation routes and Slice 6 callback/client support.
- Depends on Slice 8 wizard reentry for `eng:appr:edit:<draft_id>`.
- Should land before Slice 7 shell cutover so approvals are already production
  ready.

Tests:

- Add controller coverage for global and scoped approval flows, placeholder-only
  queues, approve/reject confirmation, edit request submission, and stale-item
  refresh behavior.
- Keep existing candidate-review tests until Slice 12 removes the legacy path;
  do not rewrite them in place and accidentally lose old-path coverage too early.

Rollout notes:

- This is the highest-priority operator task. Land it before issue queue and
  before the shell cutover.
- Do not reuse the legacy `eng:cand:*` copy or callback names on the new
  controller; the task-first queue is a distinct surface.

## Slice 10: Issue Queue Controller

Status: blocked by Slices 4-6.

Repo status check:

- There is no task-first issue controller, no `eng:iss:*` callback family, and
  no task-first rate-limit or quiet-hours subflow.
- Existing engagement queue logic is candidate-review-specific and cannot be
  repurposed without adding issue-specific state and return handling.
- Quiet-hours editing exists only through legacy settings-edit flows.

Work items:

- Implement `Top issues` controller rendering.
- Implement skip behavior.
- Implement direct fixes and `next_step` subflow routing.
- Implement rate-limit detail and quiet-hours edit screens.
- Implement scoped issue queue behavior launched from engagement detail.
- Add handlers for `eng:iss:list:<offset>`, `eng:iss:eng:<engagement_id>`,
  `eng:iss:open:<issue_id>`, `eng:iss:skip:<issue_id>`, and
  `eng:iss:act:<issue_id>:<action_key>`.
- Implement the two issue subflows that need dedicated screens:
  read-only rate-limit detail and quiet-hours edit.
- Route wizard-entry fixes through `eng:wz:*` with stored return context.
- Keep skip as local operator state for the current single-operator model and
  badge skipped issues when they reappear.
- Refresh the same controller on `resolved` or `stale`; keep the operator on the
  issue card for `noop` and `blocked`.

Acceptance:

- Each issue type surfaces the documented action set only.
- Direct fixes refresh the queue correctly.
- Quiet-hours and rate-limit flows follow the documented DTOs and return rules.
- Scoped issue flow returns to engagement detail when its queue empties.
- The controller never exposes umbrella issues or raw backend diagnostics.
- `Skip` always advances, but skipped issues remain unresolved and can return
  with the `Skipped before` badge.
- Read-only rate-limit detail never mutates state.

Backend and bot touchpoints:

- Bot controller: add a dedicated issue-flow module or equivalent controller
  layer rather than extending candidate review logic ad hoc.
- Bot dispatcher: `bot/callback_handlers.py`.
- Bot formatting/UI helpers for issue cards, fix actions, rate-limit detail, and
  quiet-hours editing.
- Bot config-editing/time parsing helpers may be reused for quiet-hours edits,
  but the save route must target the task-first quiet-hours endpoint.
- Backend dependency: Slice 4 issue generation and Slice 5 issue-action /
  quiet-hours / rate-limit endpoints.

Dependencies:

- Depends on Slice 4, Slice 5, and Slice 6.
- Depends on Slice 8 for wizard-entry fix actions such as choosing topic or
  account.
- Can land before Slice 7 home cutover and before Slice 11 browse surfaces.

Tests:

- Add controller coverage for every confirmed issue type and action family.
- Cover skip, stale refresh, direct-fix success, blocked/noop handling,
  rate-limit stale behavior, quiet-hours save/off/noop, scoped return to detail,
  and wizard-entry early-exit return.
- Add formatting tests for exact issue labels and badges.

Rollout notes:

- Keep this slice isolated from the shell cutover. The queue should be fully
  usable from direct callback entry before `Top issues` becomes a primary home
  action.
- Do not backdoor issue fixes through legacy settings or target mutation
  screens once this controller exists.

## Slice 11: Engagement Detail And Sent Messages

Status: blocked by Slice 3 and bot routing work.

Repo status check:

- There is no task-first `My engagements` list, no task-first engagement detail,
  and no task-first sent-message feed in the bot today.
- Existing engagement surfaces focus on candidate review, settings lookup, and
  recent actions, not on engagement-scoped task-first detail.
- There is no handler that uses backend `pending_task.resume_callback`.

Work items:

- Implement `My engagements` list rendering and paging.
- Implement engagement detail with `pending_task` priority handling.
- Implement resume behavior using `pending_task.resume_callback`.
- Implement `Sent messages` read-only feed and paging.
- Add handlers for `eng:mine:list:<offset>`, `eng:mine:open:<engagement_id>`,
  `eng:det:open:<engagement_id>`, `eng:det:resume:<engagement_id>`, and
  `eng:sent:list:<offset>`.
- Add edit entry actions on detail for topic, account, and sending mode that
  route into the wizard reentry callbacks.
- Keep `Sent messages` read-only and omit any row-open callback in v1.
- Use backend paging data as-is for `My engagements` and `Sent messages`; do not
  add bot-side filters.

Acceptance:

- Engagement rows show the correct badges and ordering.
- Detail exposes at most one primary pending task.
- Sent messages stay read-only and newest-first.
- Detail `resume` uses `pending_task.resume_callback` from backend payloads
  instead of recomputing queue priority in bot code.
- Empty states render exactly `No engagements` and `No sent messages`.
- Out-of-range paging gracefully snaps back to the nearest valid page.

Backend and bot touchpoints:

- Bot UI/formatting: add list-row, detail, and sent-feed formatters plus pager
  helpers.
- Bot callbacks: `bot/callback_handlers.py`.
- Bot read dependency: Slice 3 engagement list/detail/sent endpoints.
- Wizard follow-on: Slice 8 edit reentry callbacks.
- Queue follow-on: Slice 9 and Slice 10 scoped return callbacks.

Dependencies:

- Depends on Slice 3 read models and Slice 6 callback/client support.
- Depends on Slice 8 for detail edit reentry.
- Benefits from Slice 9 and Slice 10 being present first so detail resume and
  scoped queue returns have real destinations.

Tests:

- Add bot-handler coverage for engagement list paging, detail rendering, pending
  task resume routing, no-pending-task detail, and sent-feed paging.
- Add UI tests for row badge order, empty states, and omission of row-open
  callbacks for sent messages.

Rollout notes:

- This slice can ship before the main shell cutover as direct callback entry or
  wizard-confirm destination.
- Keep detail read-focused. Do not reintroduce inline settings mutation controls
  from the legacy community-scoped surfaces.

## Slice 12: Legacy Retirement And Release Hardening

Status: blocked by all prior slices.

Repo status check:

- Legacy engagement flows remain concentrated in `bot/callback_handlers.py`,
  `bot/engagement_wizard_flow.py`, `bot/engagement_review_flow.py`,
  `bot/ui_common.py`, and older engagement formatting/UI helpers.
- Legacy community-scoped settings, candidate-review, and recent-actions paths
  still have active tests and callback coverage.
- The repo has not yet run a full end-to-end task-first operator walkthrough.

Work items:

- Remove or hide legacy community-scoped primary operator paths.
- Keep only necessary compatibility/admin screens during transition.
- Remove legacy writes when no active task-first callback depends on them.
- Add regression coverage for stale, blocked, noop, and empty-state flows.
- Run full operator walkthroughs for create, edit, approve, reject, issue
  resolution, and sent-message review.
- Delete or quarantine the old primary engagement home and candidate-review
  callback entrypoints once Slice 7-11 are live.
- Retain admin-only target/topic/prompt/style tooling only where the new primary
  cockpit still depends on it.
- Remove any remaining bot-side merges of community settings into task-first
  screens.
- Prune client helpers and parser constants that only serve the retired primary
  path.
- Verify that no active task-first callback emits legacy `eng:cand:*`,
  `eng:set:*`, or equivalent primary-navigation callbacks.

Acceptance:

- No competing old/new primary operator flows remain.
- Mixed-source screens are gone.
- Bot tests and targeted manual walkthroughs cover the documented happy paths
  and edge cases.
- All documented stale, blocked, noop, and empty-state outcomes are exercised at
  least once in automated tests.
- The task-first shell is the only default operator engagement path.

Backend and bot touchpoints:

- Bot cleanup across callback routing, UI constants, formatting helpers, wizard
  flow, review flow, and any legacy queue/list handlers that still define the
  old primary path.
- Backend cleanup only after confirming no active bot surface needs legacy
  community-scoped write endpoints as operator-facing paths.
- Test cleanup and replacement across `tests/test_bot_ui.py`,
  `tests/test_bot_engagement_wizard.py`, queue-handler tests, and any legacy
  engagement-home tests.

Dependencies:

- Depends on completed Slice 3 through Slice 11 work.
- Should be the only slice allowed to remove legacy primary callbacks and tests.
- Requires manual verification after the automated suite is green.

Tests:

- Run the targeted engagement API and bot test suites after cleanup.
- Add regression cases for:
  stale queue items, blocked issue fixes, noop quiet-hours saves, empty global
  queues, empty scoped queues, hidden incomplete drafts, and out-of-range list
  paging after data shrinkage.
- Record a manual checklist walkthrough for create, edit, approve, reject, issue
  resolution, and sent-message review before release.

Rollout notes:

- Do not remove legacy primary paths until the new home, wizard, queues, detail,
  and sent-feed surfaces are all live behind real callbacks.
- Prefer one cleanup PR after the new cockpit is proven rather than mixing large
  deletions into earlier feature slices.
