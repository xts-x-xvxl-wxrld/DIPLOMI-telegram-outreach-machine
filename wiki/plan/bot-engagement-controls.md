# Bot Engagement Controls Plan

## Goal

Add the next layer of Telegram bot engagement controls described in
`wiki/spec/bot-engagement-controls.md`.

The plan starts from the controls already completed in `wiki/plan/engagement-operator-controls.md`
and expands the bot into a fuller engagement admin surface while preserving the same safety posture:
operator review is required, sending is explicit, and the bot talks only to the backend API.

## Current Context

Already implemented:

- `/engagement` cockpit
- `/engagement_candidates [status]`
- `/approve_reply <candidate_id>`
- `/reject_reply <candidate_id>`
- `/send_reply <candidate_id>`
- `/engagement_settings <community_id>`
- `/set_engagement <community_id> <off|observe|suggest|ready>`
- `/join_community <community_id>`
- `/detect_engagement <community_id> [window_minutes]`
- `/engagement_topics`
- `/create_engagement_topic <name> | <guidance> | <comma_keywords>`
- `/toggle_engagement_topic <topic_id> <on|off>`
- `/engagement_actions [community_id]`

Backend/API concepts already specified:

- engagement targets
- prompt profiles and versions
- style rules
- topic examples
- editable candidate replies and revisions
- Telegram account pool separation

Known menu gaps:

- Daily engagement still lacks direct `Approved queue`, `Settings lookup`, candidate detail,
  revisions, expire, retry, and button-led reply editing flows.
- Target controls list and approve targets, but lack detail, resolve, reject, archive, permission
  toggles, target-scoped join/detect, status filters, and add-target menu buttons.
- Prompt controls list, preview, and activate profiles, but lack detail, versions, creation,
  duplication, editing, rollback, inline preview, and activation confirmation.
- Topic controls lack admin-menu placement, detail, example removal, keyword editing, guidance
  editing, and inline example controls.
- Style controls are currently read-only and lack detail, create, edit, toggle, and scope-filter
  flows.
- Community controls lack rate-limit, quiet-hours, and assigned-account commands and menu entries.
- Cross-cutting admin permission, confirmation, and conversation-state editing flows are still
  missing.
- Config editing should use an explicit field allowlist and typed edit flow, not generic database
  column editing.
- The bot engagement surfaces should be reorganized around operator intentions before exposing
  backend entities and raw permission fields.

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

## Slice 6: Prompt Profile Admin Controls

Status: completed on 2026-04-21.

Add bot support for:

```text
/engagement_prompts
/engagement_prompt <profile_id>
/engagement_prompt_versions <profile_id>
/engagement_prompt_preview <profile_id>
/activate_engagement_prompt <profile_id>
/duplicate_engagement_prompt <profile_id> <new_name>
/edit_engagement_prompt <profile_id> <field>
/rollback_engagement_prompt <profile_id> <version_number>
```

Work items:

- Add prompt profile API-client methods.
- Add prompt profile, version, and preview formatters.
- Add conversation-state editing for long prompt fields.
- Add activation confirmation callbacks.

Acceptance:

- Preview is render-only.
- Prompt edits create immutable backend versions.
- Activation is explicit and visible.
- The bot rejects unapproved prompt fields and variables before calling the API when possible.

Completed:

- Added prompt profile detail, version list, duplicate, edit, activation confirmation, and rollback
  confirmation commands.
- Added bot API-client methods for prompt profile get, version list, duplicate, and rollback.
- Added inline prompt profile controls for open, preview, versions, field editing, duplication,
  activation confirmation, and rollback confirmation.
- Prompt profile long-field edits reuse the guided config-edit flow, and user prompt template edits
  reject unapproved variables such as sender identity before calling the API.
- Added focused bot API-client, handler, and config-editing tests.

## Slice 7: Topic Examples And Style Rules

Status: completed on 2026-04-21.

Add bot support for:

```text
/engagement_topic <topic_id>
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>

/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
```

Work items:

- Add topic example API-client methods.
- Add style rule API-client methods.
- Add topic detail and style rule formatters.
- Add long-text edit flows for topic guidance and style rule text.

Acceptance:

- Good and bad examples are labeled clearly.
- Bad examples are never presented as templates to copy.
- Style rule scope and priority are visible in every rule card.
- Unsafe guidance is still rejected by backend validation.

Completed:

- Added backend topic/style detail routes so the bot can open one topic or one style rule without
  overfetching full lists.
- Added `/engagement_topic`, `/topic_remove_example`, `/topic_keywords`, and
  `/edit_topic_guidance`, including guided long-text editing for topic guidance and command-driven
  keyword/example mutation.
- Topic cards now clearly label good examples vs. bad examples, mark bad examples as avoid-copy
  guidance, and expose inline open/edit/remove controls.
- Added `/engagement_style [scope] [scope_id]`, `/engagement_style_rule`, `/create_style_rule`,
  `/edit_style_rule`, and `/toggle_style_rule`, with scoped style-rule list filters plus inline
  open/edit/toggle controls.
- Style rule cards now always show scope, priority, and direct command hints, while long rule-text
  edits reuse the shared config-edit preview/save flow.

## Slice 8: Advanced Community Settings

Status: planned.

Add bot support for:

```text
/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>
/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>
/clear_engagement_quiet_hours <community_id>
/assign_engagement_account <community_id> <telegram_account_id>
/clear_engagement_account <community_id>
```

Work items:

- Extend settings update helper payloads.
- Add parsing and validation for simple numeric/time inputs.
- Add account assignment display using masked or non-secret account labels only.

Acceptance:

- Updates preserve `reply_only=true` and `require_approval=true`.
- Backend rejects out-of-range limits and wrong-pool accounts.
- Bot never shows full account phone numbers.

## Slice 9: Admin Permission Boundary

Status: planned.

Add admin-only enforcement when backend support exists.

Work items:

- Identify admin permission source.
- Restrict prompt, style, target approval, and posting-permission controls.
- Keep daily candidate review available to ordinary operators if allowed.

Acceptance:

- Non-admin operators cannot mutate prompt profiles, style rules, target approvals, or posting
  permissions.
- Unauthorized attempts produce clear bot messages without calling protected API mutations.
- Backend auth remains the source of truth.

## Slice 10: Release Documentation And Broader Test Wrap-Up

Status: planned.

Update after implementation:

- `wiki/spec/bot.md`
- `wiki/spec/api.md` if API route behavior changes
- `wiki/spec/engagement-admin-control-plane.md` if admin behavior changes
- `wiki/index.md` for new implementation roots
- `wiki/log.md`

Run focused tests for every touched layer plus the relevant full suite command used by the repo.

Acceptance:

- Bot API client, formatting, callback, and handler tests pass.
- API/service tests pass for any newly added backend endpoints.
- Wiki docs reflect the shipped behavior.
- Changes are committed and pushed when a remote is configured.

## Open Questions

- Should prompt duplicate and rollback routes be added before bot controls, or should the bot
  compose those workflows from existing create/edit/version endpoints?
- Should admin permission be implemented as a backend role, a bot allowlist, or both?
- Should target approval also create default engagement settings?
- Should conversation-state edits survive bot restarts?
