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

## Slice 2: Engagement Target Bot Controls

Status: planned.

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

## Slice 3: Candidate Detail, Editing, And Revisions

Status: planned.

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

## Slice 4: Prompt Profile Admin Controls

Status: planned.

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

## Slice 5: Topic Examples And Style Rules

Status: planned.

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

## Slice 6: Advanced Community Settings

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

## Slice 7: Admin Permission Boundary

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

## Slice 8: Release Documentation And Tests

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
