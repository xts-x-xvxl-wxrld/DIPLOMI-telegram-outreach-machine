# Engagement Cockpit Verification: Phase 2 Code Mapping

Phase 2 maps each in-scope cockpit surface to the current bot, UI, API-client,
route, and backend service entrypoints, then records the main contract risks to
verify in Phase 3 and Phase 4.

Companion to:

- `wiki/plan/engagement-cockpit-verification/phase-1-spec-baseline.md`

## Shared Entry Points

Primary dispatch and callback constants:

- `bot/callback_handlers.py`
- `bot/ui_common.py`

Primary backend read/write surfaces:

- `bot/api_client.py`
- `backend/api/routes/engagement_cockpit.py`
- `backend/api/routes/engagement_task_first.py`
- `backend/services/task_first_engagement_cockpit.py`
- `backend/services/task_first_engagement_cockpit_mutations.py`
- `backend/services/task_first_engagement_issues.py`
- `backend/services/task_first_engagements.py`

## Surface Matrix

| Surface | Code entrypoints | Risk notes |
| --- | --- | --- |
| `Engagements` home | Bot router: `bot/callback_handlers.py` routes `eng:home` to `_send_cockpit_home()`. UI: `bot/ui_engagement_home.py` `cockpit_home_markup()`. API client: `get_engagement_cockpit_home()`. Backend: `GET /engagement/cockpit/home` in `backend/api/routes/engagement_cockpit.py`, backed by `get_cockpit_home()` in `backend/services/task_first_engagement_cockpit.py`. | Home buttons are not fully aligned with the spec callback contract: `Approve draft` and `Top issues` buttons emit `eng:appr:list:0` and `eng:iss:list:0` directly instead of `op:approve` and `op:issues`. `My engagements`, `Add engagement`, and `Sent messages` do use `op:*`. |
| `Approve draft` | Bot router: `ACTION_OP_APPROVE` and `ACTION_ENGAGEMENT_APPROVAL_QUEUE` in `bot/callback_handlers.py`. Flow: `bot/engagement_approval_flow.py` `show_global_approval_queue()`, `show_scoped_approval_queue()`, `show_draft_card()`, `handle_approve_confirmed()`, `handle_reject_confirmed()`, `handle_edit_request_start()`, `handle_edit_request_text()`. API client: `get_engagement_cockpit_approvals*()`, `approve_engagement_cockpit_draft()`, `reject_engagement_cockpit_draft()`, `edit_engagement_cockpit_draft()`. Backend routes: `/engagement/cockpit/approvals`, scoped approvals, and draft action routes in `backend/api/routes/engagement_cockpit.py`. Backend services: `get_cockpit_approvals()` plus draft mutations in `backend/services/task_first_engagement_cockpit_mutations.py`. | Approval UI still uses the generic `_with_navigation()` default footer in several places, which adds top-level `op:home` instead of the spec's `<< Engagements`. `show_draft_card()` reloads only the global approvals payload and falls back to a placeholder card if the requested draft is not current, so reopening a specific `draft_id` is weaker than the spec requires. Scoped completion also signals return through context state instead of routing cleanly in the callback layer. |
| `Top issues` | Bot router: `ACTION_OP_ISSUES` and `ACTION_ENGAGEMENT_ISSUE_QUEUE` in `bot/callback_handlers.py`. Flow: `bot/engagement_issue_flow.py` `show_global_issue_queue()`, `show_scoped_issue_queue()`, `show_issue_card()`, `handle_issue_skip()`, `handle_issue_action()`. API client: `get_engagement_cockpit_issues*()`, `act_on_engagement_cockpit_issue()`. Backend routes: `/engagement/cockpit/issues`, scoped issues, and issue-action route in `backend/api/routes/engagement_cockpit.py`. Backend services: `get_cockpit_issues()` in `backend/services/task_first_engagement_cockpit.py`; issue generation in `backend/services/task_first_engagement_issues.py`; semantic mutations in `backend/services/task_first_engagement_cockpit_mutations.py`. | The issue UI also uses generic `_with_navigation()` defaults, so global/scoped controllers still surface `op:home` rather than the task-first `<< Engagements` contract. `show_issue_card()` reloads the global queue and falls back to the current issue if the requested `issue_id` is not current, which means reopening a specific issue card is not reliable. |
| Rate-limit detail | Flow: `bot/engagement_issue_flow.py` `show_rate_limit_detail()`. API client: `get_engagement_cockpit_issue_rate_limit()`. Backend route: `GET /engagement/cockpit/issues/{issue_id}/rate-limit` in `backend/api/routes/engagement_cockpit.py`. Backend service: `get_cockpit_rate_limit_detail()` in `backend/services/task_first_engagement_cockpit_mutations.py`. | Backend returns `next_callback="eng:rate:open:{issue_id}"`, but the main callback router does not dispatch an `eng:rate:*` family. Instead, the bot opens rate-limit detail through special-case issue handling, so the active code path does not actually follow the backend callback family the spec describes. The detail markup also uses generic navigation rather than `Back` plus `<< Engagements`. |
| Quiet-hours edit | Flow: `bot/engagement_issue_flow.py` `start_quiet_hours_edit()` and `save_quiet_hours()`. Formatting: `bot/formatting_engagement_issue.py`. API client: `get_engagement_cockpit_quiet_hours()` and `update_engagement_cockpit_quiet_hours()`. Backend route: quiet-hours read/write endpoints in `backend/api/routes/engagement_cockpit.py`. Backend service: `get_cockpit_quiet_hours()` and `update_cockpit_quiet_hours()` in `backend/services/task_first_engagement_cockpit_mutations.py`. | Backend returns `next_callback="eng:quiet:open:{engagement_id}:{issue_id}"`, but there is no `eng:quiet:*` dispatch family in `bot/callback_handlers.py`; the bot uses a local pseudo-action path instead. `start_quiet_hours_edit()` fetches the current issue queue and reads only `data["current"]` to find the engagement, so it can pick the wrong engagement if the requested quiet-hours issue is not the current queue item. The editor markup offers only `Cancel`, and the flow depends on typed text or `off`, not the spec's explicit `Edit start`, `Edit end`, `Turn off quiet hours`, and `Save` actions. |
| `My engagements` | Bot router: `ACTION_OP_ENGS` and `ACTION_ENGAGEMENT_MINE` in `bot/callback_handlers.py`. Flow: `bot/engagement_detail_flow.py` `show_engagement_list()`. UI: `bot/ui_engagement_detail.py` `engagement_list_markup()`. API client: `list_engagement_cockpit_engagements()`. Backend route: `GET /engagement/cockpit/engagements`. Backend service: `list_cockpit_engagements()` in `backend/services/task_first_engagement_cockpit.py`. | The list route and paging match the intended surface, but button rows emit `eng:mine:open:<id>` into a preview screen rather than opening engagement detail directly. Footer navigation uses `Back` to `eng:home`, which matches the surface better than approvals/issues, but the label is still the generic back button rather than a dedicated `<< Engagements` button. |
| Engagement detail | Bot router: `ACTION_ENGAGEMENT_DETAIL` in `bot/callback_handlers.py`. Flow: `bot/engagement_detail_flow.py` `show_engagement_preview()` and `show_engagement_detail()`. UI: `bot/ui_engagement_detail.py` `engagement_preview_markup()` and `engagement_detail_markup()`. API client: `get_engagement_cockpit_engagement()`. Backend route: `GET /engagement/cockpit/engagements/{engagement_id}`. Backend service: `get_cockpit_engagement_detail()` in `backend/services/task_first_engagement_cockpit.py`. | `eng:mine:open:<id>` currently opens a preview card with `View details`, not the full detail screen the spec expects. Detail edit buttons route to `eng:wz:edit:*`, which matches the active callback family, but the back footer returns to `eng:mine:list:0` rather than offering the spec's `<< Engagements` immediate exit. |
| Pending-task resume | Bot router: `eng:det:resume:<engagement_id>` in `bot/callback_handlers.py`. Flow: `bot/engagement_detail_flow.py` `handle_engagement_resume()`. Backend read model: `pending_task.resume_callback` is produced by `_pending_task_for_engagement()` in `backend/services/task_first_engagement_cockpit.py`. | The backend correctly owns `resume_callback`, but the bot's resume handler relies on an optional `context._dispatch_callback` hook that is not wired in the main callback router. Without that hook, the fallback behavior is to re-render detail instead of dispatching the returned callback, so resume may not actually follow the backend semantic contract. |
| `Sent messages` | Bot router: `ACTION_OP_SENT` and `ACTION_ENGAGEMENT_SENT` in `bot/callback_handlers.py`. Flow: `bot/engagement_detail_flow.py` `show_sent_messages()`. UI: `bot/ui_engagement_detail.py` `sent_messages_markup()`. API client: `list_engagement_cockpit_sent()`. Backend route: `GET /engagement/cockpit/sent`. Backend service: `list_cockpit_sent()` in `backend/services/task_first_engagement_cockpit.py`. | The feed is read-only and paged as expected. Navigation still uses the generic footer helper, so the exit path is a standard back button to `eng:home` rather than the explicit `<< Engagements` contract. |
| `Add engagement` wizard | Bot router: `ACTION_OP_ADD` and `ACTION_ENGAGEMENT_WIZARD` in `bot/callback_handlers.py`. Flow: `bot/engagement_wizard_flow.py` `_start_engagement_wizard()` and `_handle_wizard_callback()`. UI: `bot/ui_engagement_wizard.py`. API client: `create_engagement()`, `patch_engagement()`, `put_engagement_settings()`, `wizard_confirm_engagement()`, `wizard_retry_engagement()`. Backend routes: create/patch/settings plus `/wizard-confirm` and `/wizard-retry` in `backend/api/routes/engagement_task_first.py`. Backend service: `backend/services/task_first_engagements.py`. | The active callback family is `eng:wz:*`, which matches the Phase 1 normalization. Two larger drifts remain: `_start_engagement_wizard()` resumes existing wizard state when present, even though the spec says `Add engagement` should always start fresh, and step 4 still uses legacy `watching/suggesting/sending` labels with `observe/suggest/require_approval` mode mapping instead of the spec's `Draft/Auto send` and `suggest/auto_limited` contract. Existing bot tests currently bless the resume behavior and the legacy mode mapping. |
| Engagement edit via wizard | Bot router: `eng:wz:edit:<engagement_id>:<field>` in `bot/engagement_wizard_flow.py`, reached from detail UI in `bot/ui_engagement_detail.py`. Backend helper callbacks: `_wizard_edit_callback()` in `backend/services/task_first_engagements.py`; issue mutations also return `eng:wz:edit:*` in `backend/services/task_first_engagement_cockpit_mutations.py`. | Edit reentry exists and stores `return_callback` state for some paths, but the field vocabulary is not fully aligned: backend confirm validation uses `sending_mode`, while the detail UI and Phase 1 baseline normalize on `mode`. This is survivable if the wizard translates consistently, but it is a routing-risk seam. |
| Navigation outside the wizard | Shared UI helper: `_with_navigation()` in `bot/ui_common.py`. Used by `bot/engagement_approval_flow.py`, `bot/engagement_issue_flow.py`, and `bot/ui_engagement_detail.py`. | The shared helper still encodes `← Back` plus top-level `⌂ Home` by default. The active spec requires `Back` plus `<< Engagements` outside the wizard and explicitly supersedes the older home-footer model, so this is one of the main contract drifts to harden with regression tests. |
| Navigation inside the wizard | Wizard UI: `bot/ui_engagement_wizard.py` `engagement_wizard_step1_markup()`, picker markups, launch markup, and cancel-confirm markup. Wizard flow: `bot/engagement_wizard_flow.py`. | Wizard navigation is closer to spec than the rest of the cockpit: step screens use `Back` plus `Cancel` and omit the top-level `Home` footer. The remaining risk is semantic rather than visual: `eng:wz:start` can resume prior state instead of starting fresh. |

## Cross-Cutting Risk Summary

- Home-to-surface callback drift:
  the home markup uses direct `eng:appr:*` and `eng:iss:*` callbacks for two
  destinations instead of the spec's `op:*` home callbacks.
- Footer drift:
  secondary screens still rely on a shared helper that emits top-level
  `op:home`, not the task-first `<< Engagements` return target.
- Reopen drift:
  approval and issue reopen handlers do not reliably reopen the requested
  `draft_id` or `issue_id`; they mostly reload the current global controller.
- `next_callback` drift:
  backend issue mutations return `eng:rate:*` and `eng:quiet:*`, but the bot
  does not dispatch those families directly.
- Resume drift:
  detail resume depends on an optional dispatch hook rather than a guaranteed
  callback re-dispatch path.
- Wizard drift:
  the current wizard behavior and tests still preserve resumable state and
  legacy sending-mode labels that conflict with the active task-first spec.

## Phase 3 Read Targets

Phase 3 should compare this map against:

- `tests/test_bot_engagement_home_handlers.py`
- `tests/test_bot_engagement_approval_handlers.py`
- `tests/test_bot_engagement_issue_handlers.py`
- `tests/test_bot_engagement_detail_handlers.py`
- `tests/test_bot_engagement_wizard.py`
- `tests/test_engagement_api.py`

The high-risk assertions to check first are:

- home callback emissions
- non-wizard footer navigation targets
- reopening requested `draft_id` and `issue_id`
- `next_callback` handling for rate-limit and quiet-hours flows
- detail resume using backend `resume_callback`
- wizard fresh-start behavior and sending-mode mapping
