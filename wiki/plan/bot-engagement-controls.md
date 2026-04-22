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

- Daily engagement lacks a direct `Settings lookup` menu item.
- Target approval and posting-permission changes still mutate immediately; they need explicit
  confirmation cards before the API update.
- Target notes have edit metadata, but the bot still needs a target-note save dispatch and
  button-led guided edit entrypoints.
- Prompt profile creation has backend/API-client support, but the bot needs a dedicated creation
  command and a visible create entrypoint.
- Topic examples can be added by command, but topic cards need inline `Add good example` and
  `Add bad example` buttons that start conversation-state input.
- Style rules can be created by command, but the inline `Create` button only shows command help; it
  needs a bot-led creation flow.
- Community settings cards expose command hints for rate limits, quiet hours, and account
  assignment, but they need inline edit controls and account-assignment confirmation.
- Readiness summaries should use richer backend-provided membership, account, rate-limit,
  quiet-hour, and expiry details when those fields are available.
- Default cards still expose more raw IDs and backend fields than ideal; details must remain
  reachable for audit/debug, but default views should become more operator-intention first.
- Long-term admin authorization still depends on the transitional bot allowlist; backend
  capabilities or roles remain the preferred authority.

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

Status: completed on 2026-04-21.

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

Completed:

- Added `/set_engagement_limits`, `/set_engagement_quiet_hours`,
  `/clear_engagement_quiet_hours`, `/assign_engagement_account`, and
  `/clear_engagement_account` bot commands.
- Community-settings updates now reuse the shared "read current settings,
  merge changes, preserve hard safety fields" helper path instead of
  rebuilding payloads ad hoc in each command.
- Quiet-hour command parsing now rejects malformed `HH:MM` values before
  making API calls, while numeric bounds still defer to backend validation.
- Settings cards now include direct command hints for limits, quiet hours,
  and account assignment, and assigned accounts render with masked-phone
  labels from `/api/debug/accounts` when available.
- Added focused handler and formatting tests covering preserved safety
  fields, quiet-hour validation, assignment clearing, and masked account
  display.

## Slice 9: Admin Permission Boundary

Status: completed on 2026-04-21.

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

Completed:

- Added a transitional bot-side admin allowlist through `TELEGRAM_ADMIN_USER_IDS`. When it is set,
  only those Telegram users are treated as engagement admins locally; when it is empty, the bot
  keeps the previous permissive local behavior and still relies on backend authorization.
- Added shared admin checks for admin-only engagement commands, callback routes, and guided
  config-edit saves so non-admin operators are rejected before protected mutation API calls.
- Daily review surfaces remain available to ordinary allowlisted operators, while the `/engagement`
  home hides the `Admin` button for known non-admin users and read-only target/topic/settings cards
  hide admin mutation buttons when the bot can determine the caller is not an admin.
- Added focused bot access, UI, config, and handler tests covering hidden controls plus early
  rejection of non-admin prompt, style, target-permission, topic, and advanced community-setting
  mutations.

## Slice 10: Release Documentation And Broader Test Wrap-Up

Status: completed on 2026-04-21.

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

Completed:

- Refreshed the release docs after the shipped Slice 4 through Slice 9 behavior, including the
  current menu-gap inventory in `wiki/spec/bot-engagement-controls.md`.
- Updated `wiki/spec/bot.md` with the final prompt-profile command surface and admin boundary
  behavior.
- Updated `wiki/spec/api.md` and `wiki/spec/engagement-admin-control-plane.md` for prompt profile
  detail, duplicate, rollback, and admin-only confirmation behavior.
- Updated `wiki/index.md` with the bot config module and broader bot/engagement regression test
  roots.
- Ran the focused release coverage:
  `python -m pytest -q tests/test_bot_api_client.py tests/test_bot_formatting.py tests/test_bot_ui.py tests/test_bot_handlers.py tests/test_bot_engagement_handlers.py tests/test_bot_config_editing.py tests/test_bot_access.py tests/test_engagement_api.py tests/test_engagement_prompt_controls.py tests/test_engagement_targets.py tests/test_engagement_send_worker.py tests/test_engagement_detect_worker.py tests/test_engagement_scheduler.py tests/test_engagement_embeddings.py tests/test_engagement_semantic_eval_fixtures.py tests/test_engagement_schema.py`
  with 281 passing tests.
- Ran the full repo suite with `python -m pytest -q` outside the sandbox after the sandbox denied
  pytest temp-directory setup; the full suite passed with 385 tests and one existing datetime
  deprecation warning.

## Follow-Up Slice 11: Safety Confirmations

Status: completed on 2026-04-21.

Purpose:

Close the remaining risky-action UX gaps before adding more creation surfaces.

Work items:

- Add explicit confirmation callbacks and confirmation cards before target approval.
- Add explicit confirmation callbacks before target posting-permission changes.
- Add explicit confirmation before assigning or clearing a community engagement account.
- Keep command paths available, but make commands render the confirmation card instead of mutating
  immediately.
- Keep the final mutation in the confirm callback, with the same backend validation and admin
  gating as the existing direct update path.
- Render before/after permission or account state using masked account labels only.

Acceptance:

- `/approve_engagement_target <target_id>` shows a confirmation card and does not call the target
  update API until the admin confirms.
- Inline target approval shows the same confirmation card before mutation.
- `/target_permission <target_id> post <on|off>` and the inline posting toggle require
  confirmation before saving.
- Join/detect target permission toggles may remain direct unless later product review marks them
  risky, but posting permission must be confirmed.
- `/assign_engagement_account` and `/clear_engagement_account` show before/after account state and
  require confirmation before saving.
- Non-admin confirm callbacks are rejected before protected API methods are called.
- Bot messages never expose full phone numbers or account secrets.

Tests:

- Handler tests prove target approval, posting-permission changes, and account assignment do not
  call mutation APIs until the confirm callback.
- Callback parser tests cover the new confirmation callback shapes and the 64-byte Telegram limit.
- Admin permission tests cover command and callback confirmation paths.
- Formatting/privacy tests cover before/after cards and masked account labels.

Completed:

- `/approve_engagement_target <target_id>` and inline target approval now render an explicit
  before/after confirmation card; the target update API is called only from the confirm callback.
- `/target_permission <target_id> post <on|off>` and inline posting toggles now render the same
  before/after confirmation flow before mutating `allow_post`.
- Join and detect target permission toggles remain direct, matching this slice's reviewed scope.
- `/assign_engagement_account` and `/clear_engagement_account` now store a short per-operator
  pending confirmation and show before/after account labels before saving.
- Account confirmation callbacks stay payload-free so they remain well under Telegram's callback
  length limit even when community and account IDs are UUIDs.
- Non-admin command and confirm-callback paths are rejected before protected target or settings
  mutation APIs are called.
- Added formatting, callback parser, callback length, handler, and admin-boundary tests for the new
  confirmation surfaces.

## Follow-Up Slice 12: Guided Edit Entrypoints

Status: completed on 2026-04-22.

Purpose:

Use the existing config-editing foundation for the remaining long or awkward edit paths.

Work items:

- Add target save dispatch for `target.notes` in the guided config-edit save path.
- Add `Edit notes` buttons to target detail cards.
- Add settings-card buttons for rate limit, quiet hours, and account assignment edit entrypoints.
- Reuse the existing per-operator pending edit state, preview, save, cancel, and expiry behavior.
- Preserve `reply_only=true` and `require_approval=true` on all community settings saves.

Acceptance:

- Target note editing can be started from a button-led target detail flow.
- Saving target notes calls only the engagement target API.
- Settings-card edit buttons start guided edits for allowed settings fields.
- Settings saves preserve hard safety fields and rely on backend validation for bounds and account
  pool checks.

Tests:

- Guided target-note edit tests cover start, preview, save, cancel, expiry, and admin-only gating.
- Settings guided edit tests cover rate-limit, quiet-hour, and account-assignment entrypoints.
- API-client route tests prove target note saves use `PATCH /api/engagement/targets/{target_id}`.

Completed:

- Target cards now expose an admin-only `Edit notes` button that starts the shared guided
  config-edit flow for `target.notes`.
- Guided target-note saves call `PATCH /api/engagement/targets/{target_id}` through the existing
  engagement target API-client method with `updated_by` metadata.
- Community settings cards now expose admin-only guided edit buttons for max posts per day,
  minimum minutes between posts, quiet-hour start/end, and assigned engagement account.
- Settings guided edit callbacks use compact field codes so UUID-heavy callback data stays under
  Telegram's 64-byte limit.
- Guided settings saves reuse the existing current-settings merge path and preserve
  `reply_only=true` and `require_approval=true`.
- Added focused UI, API-client, config-editing, handler, admin-boundary, cancel, and expiry tests
  for the new guided edit entrypoints.

## Follow-Up Slice 13: Creation Flows

Status: completed on 2026-04-22.

Purpose:

Add bot-native creation entrypoints for prompt profiles, topic examples, and style rules without
requiring operators to compose long slash commands from memory.

Prompt profile work items:

- Add `/create_engagement_prompt` as the dedicated prompt profile creation command.
- Use the existing prompt profile create API-client method.
- Start with a pipe-delimited command syntax for traceability and testability.
- Add an inline `Create profile` button from the prompt profile list or advanced prompt screen.
- Ensure unsupported prompt variables are rejected before the API call when possible.

Topic example work items:

- Add `Add good example` and `Add bad example` buttons on topic cards.
- Start a conversation-state flow where the admin sends the example text as the next message.
- Preview the example and save through `POST /api/engagement/topics/{topic_id}/examples`.
- Keep bad examples clearly labeled as avoid-copy guidance.

Style rule work items:

- Replace the current inline style-rule `Create` help-only response with a bot-led create flow.
- Use a compact guided input format for the first implementation, then preview and confirm before
  creating.
- Continue supporting `/create_style_rule` as the command-led path.

Acceptance:

- Prompt profiles can be created from a dedicated command and from a visible inline entrypoint.
- Topic examples can be added without using `/topic_good_reply` or `/topic_bad_reply`.
- Style-rule creation from inline controls creates a real pending flow, not just command help.
- All creation mutations remain admin-only and use backend API routes.

Tests:

- Bot API-client tests cover prompt profile creation payloads.
- Handler tests cover prompt profile command creation and inline create entrypoints.
- Conversation-state tests cover good example, bad example, and style-rule create flows.
- Privacy tests prove created prompt/style/topic output does not expose sender identity, full phone
  numbers, or person-level scores.

Completed:

- Added `/create_engagement_prompt` with pipe-delimited input for name, description, model,
  temperature, max tokens, system prompt, and user prompt template. New profiles are created
  inactive and prompt-template variables are checked before the API call when possible.
- Prompt profile lists now expose an inline `Create profile` button that starts a guided
  preview/save flow using the shared pending-edit store.
- Topic cards now expose `Add good example` and `Add bad example` buttons. The admin sends the
  example as the next message, previews it, and saves through the topic examples API.
- The style-rule `Create` button now starts a real guided creation flow instead of returning only
  command help. The compact input uses the same scope/name/priority/rule-text shape as
  `/create_style_rule`, then previews and saves through the style-rule API.
- Added focused API-client, UI callback, config-editing, handler, conversation-state, and privacy
  regression tests for prompt, topic-example, and style-rule creation.
- Full repo coverage passed with 410 tests.

## Follow-Up Slice 14: Menu And Progressive Disclosure Polish

Status: planned.

Purpose:

Make daily engagement and admin cards easier to navigate after the safety and creation gaps are
closed.

Work items:

- Add a direct `Settings lookup` item to the daily engagement menu.
- Add button-led settings lookup entrypoints that reuse `/engagement_settings <community_id>` where
  practical.
- Prefer operator-facing labels before backend field names on default cards.
- Move raw IDs and diagnostic backend fields lower in default cards while keeping detail views
  audit-friendly.
- Improve readiness summaries when backend responses expose enough membership, account,
  rate-limit, quiet-hour, or expiry detail to explain blocks accurately.

Acceptance:

- `/engagement` exposes a direct route to settings lookup.
- Default target, settings, topic, style, and prompt cards are compact and intention-first.
- Detail views still expose IDs and audit-relevant state.
- Readiness summaries do not invent precision when the backend does not expose a concrete reason.

Tests:

- UI tests assert the Settings lookup button exists and callback data stays within Telegram limits.
- Formatting tests cover compact default cards and detail-card ID visibility.
- Readiness formatting tests cover backend-provided readiness strings and fallback behavior.

## Follow-Up Slice 15: Backend Capability Boundary

Status: deferred.

Purpose:

Move the admin permission source from the transitional Telegram bot allowlist toward backend-owned
operator capabilities or roles.

Work items:

- Add or identify a backend endpoint that exposes engagement operator/admin capabilities for the
  current bot auth context.
- Update the bot to use backend capabilities when available.
- Keep `TELEGRAM_ADMIN_USER_IDS` as a transitional fallback during rollout.
- Make backend authorization the primary contract for prompt, style, topic, target, and advanced
  community-setting mutations.

Acceptance:

- The bot can hide or reject admin-only controls based on backend capabilities.
- Protected backend routes remain authoritative even if bot-side checks are misconfigured.
- Tests cover both backend-capability and transitional-allowlist behavior.

## Open Questions

- Prompt duplicate and rollback are first-class API routes in the shipped implementation.
- Admin permission currently uses a transitional bot allowlist through `TELEGRAM_ADMIN_USER_IDS`;
  a backend capability or role model remains the preferred long-term authority.
- Should target approval also create default engagement settings? Current recommendation: keep
  approval and settings separate until product review chooses otherwise.
- Should conversation-state edits survive bot restarts? Current recommendation: keep short-lived
  in-process drafts for the next slices and revisit durable drafts only if operators lose work in
  practice.
