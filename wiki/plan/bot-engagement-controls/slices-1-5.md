# Bot Engagement Controls Plan Slices 1-5

Original detailed rollout notes for documentation, navigation, target controls, editing foundation, and candidate revision slices.

## Slice 1: Documentation Baseline

Status: completed.

Create:

- `wiki/spec/bot-engagement-controls.md`
- `wiki/plan/bot-engagement-controls.md`

Update:

- `wiki/index.md`
- `wiki/spec/bot.md` with a pointer to the dedicated bot engagement controls spec
- `wiki/log.md`

Acceptance:

- The new spec describes command, callback, formatting, API, safety, and testing contracts.
- The plan is linked from the wiki index.
- No code is changed in this slice.

Completed notes:

- Added a current menu gap inventory to the spec so later slices can work from the real bot menu
  state instead of only the target command list.

## Slice 2: Operator Intention Navigation And Readiness Summaries

Status: completed.

Reorganize the engagement cockpit around what the operator is trying to do.

Work items:

- Add intention-first entries for `Today`, `Review replies`, `Approved to send`, `Communities`,
  `Topics`, and `Recent actions`.
- Add engagement admin entries for `Communities`, `Topics`, `Voice rules`, `Limits and accounts`,
  and `Advanced`.
- Add candidate send-readiness summaries before raw candidate details.
- Add community readiness summaries before raw target and settings fields.
- Keep existing commands working as traceability and testing paths.

Acceptance:

- The default `/engagement` card answers what needs review and what is ready to send.
- Community cards summarize whether the app is not approved, watching only, drafting, ready to post,
  paused, or blocked.
- Candidate cards show only state-relevant primary actions by default.
- Backend identifiers and raw fields remain available in detail cards but are not the first thing an
  operator has to interpret.

Completed notes:

- `/engagement` now exposes `Today`, `Review replies`, `Approved to send`, `Communities`, `Topics`,
  `Recent actions`, and `Admin` inline entries.
- `/engagement_admin` now exposes `Communities`, `Topics`, `Voice rules`, `Limits/accounts`, and
  `Advanced` entries, with small landing cards for limits/account lookup and advanced controls.
- Candidate, engagement target, and community settings cards now show derived readiness summaries
  before lower-level IDs, modes, and permission fields.
- Candidate cards now list state-relevant command hints: needs-review candidates do not show send,
  approved candidates show send, and terminal candidates point to audit.

## Slice 3: Engagement Target Bot Controls

Status: completed.

Add bot support for:

```text
/engagement_targets [status]
/engagement_target <target_id>
/add_engagement_target <telegram_link_or_username_or_community_id>
/resolve_engagement_target <target_id>
/approve_engagement_target <target_id>
/reject_engagement_target <target_id>
/archive_engagement_target <target_id>
/target_permission <target_id> <join|detect|post> <on|off>
/target_join <target_id>
/target_detect <target_id> [window_minutes]
```

Work items:

- Add API-client methods for target list/create/update and target-scoped jobs.
- Add target card formatting.
- Add inline target list/detail/permission callbacks.
- Hide or gracefully reject controls when required target API endpoints are missing.

Acceptance:

- Engagement target commands never call seed APIs.
- Permission toggles display before/after state.
- Rejected and archived targets show all permissions off.
- Target join/detect controls enqueue jobs only through API methods.

Completed notes:

- Added `/engagement_targets [status]`, `/engagement_target`, `/resolve_engagement_target`,
  `/reject_engagement_target`, `/archive_engagement_target`, `/target_permission`, `/target_join`,
  and `/target_detect` bot commands.
- Target list navigation now includes an add-target usage button and status filters for all,
  pending, resolved, approved, failed, rejected, and archived targets.
- Target cards expose state-aware inline controls for open/detail, resolve, approval, rejection,
  archive, permission toggles, target-scoped join, and target-scoped detect.
- Target approval and permission/status mutations fetch the current target first and display
  before/after permission state after the API returns.
- Added `GET /api/engagement/targets/{target_id}` and bot API-client methods for target detail,
  target-scoped join, and target-scoped detection.

## Slice 4: Config Editing Foundation

Status: completed.

Add a reusable bot editing foundation for admin/settings configuration.
The behavioral contract for this slice lives in `wiki/spec/bot-engagement-controls.md`.

Work items:

- Define editable field metadata by entity, field, label, value type, confirmation requirement, and
  admin requirement.
- Add in-process pending edit state scoped by Telegram operator ID.
- Add typed parsers for text, long text, int, float, bool, enum, time, UUID, and keyword-list
  values.
- Add common preview/confirmation rendering with Save and Cancel callbacks.
- Route saves through explicit API-client methods for each entity rather than a generic PATCH helper.

Acceptance:

- A pending edit from one operator cannot be saved by another operator.
- Starting a new command cancels or supersedes stale pending edit state.
- Long instruction values show a preview before save.
- Risky changes such as prompt activation, posting permission, and account assignment require
  confirmation.
- Backend validation remains the source of truth for unsafe guidance, wrong account pools, invalid
  prompt variables, and out-of-range settings.

Completed notes:

- Added `bot/config_editing.py` with explicit editable field metadata, typed parsers, pending edit
  state, 15-minute expiry, and reusable preview/cancel/save message rendering.
- Added `eng:edit:save` and `eng:edit:cancel` callbacks with compact callback data.
- Added `/edit_reply <candidate_id>` as the first guided long-edit flow. Operators can still use
  the existing pipe command, while the guided path stores pending state by Telegram user ID, accepts
  the next text message as the proposed final reply, previews it, and saves only through the
  candidate edit API.
- Added `/cancel_edit` for the caller's pending edit.
- Added save dispatch plumbing for candidate, target, prompt profile, topic, style rule, and
  engagement settings entities. Later slices can register UI entrypoints without adding a new state
  machine.
- Added focused config-editing, UI callback, and engagement-handler tests for value parsing,
  operator scoping, expiry, preview, save, cancel, and callback length.

## Slice 5: Candidate Detail, Editing, And Revisions

Status: completed.

Add bot support for:

```text
/engagement_candidate <candidate_id>
/edit_reply <candidate_id> | <new final reply>
/candidate_revisions <candidate_id>
/expire_candidate <candidate_id>
/retry_candidate <candidate_id>
```

Work items:

- Add candidate-detail and revision API-client methods if backend routes exist.
- Add edit API-client method for `POST /api/engagement/candidates/{candidate_id}/edit`.
- Add conversation-state editing for long final replies.
- Add candidate detail formatting with prompt provenance and risk notes.

Acceptance:

- Candidate approval uses the latest valid final reply.
- Sent candidates cannot be edited through normal bot controls.
- Send buttons appear only for approved candidates.
- Source excerpts are capped and sender identity is never shown.

Completed notes:

- Added backend candidate detail, revision list, explicit expire, and failed-candidate retry routes.
- Added bot API-client methods and commands for `/engagement_candidate`,
  `/candidate_revisions`, `/expire_candidate`, and `/retry_candidate`.
- Candidate list cards now expose open/detail controls; detail cards expose state-aware edit,
  approve, reject, send, expire, retry, and revisions buttons.
- Candidate detail edit buttons reuse the Slice 4 guided preview/save flow for final replies.
- Added focused API-client, formatting, UI callback, handler, and backend API tests covering detail,
  revisions, expire/retry transitions, and send-button visibility.
