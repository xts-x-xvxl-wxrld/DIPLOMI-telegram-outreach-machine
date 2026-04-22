# Bot Engagement Controls Plan Slices 6-10

Original detailed rollout notes for prompt, topic, settings, permission, and release-wrap slices.

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
