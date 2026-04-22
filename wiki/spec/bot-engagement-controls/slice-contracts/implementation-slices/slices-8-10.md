# Bot Engagement Implementation Slices 8-10

Detailed settings, permission-boundary, and release wrap-up slice contracts.

### Slice 8: Advanced Community Settings

Purpose:

Expose rate limits, quiet hours, and engagement account assignment in the admin cockpit while
preserving reply-only, approval-required engagement.

Required commands:

```text
/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>
/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>
/clear_engagement_quiet_hours <community_id>
/assign_engagement_account <community_id> <telegram_account_id>
/clear_engagement_account <community_id>
```

Deferred inline follow-up:

- Button-led community controls for rate limits, quiet hours, and account assignment remain future
  work. The current slice ships slash-command entrypoints plus richer settings cards.

Rules:

- Settings cards should show a readiness summary before raw numeric fields.
- Updates must preserve `reply_only=true` and `require_approval=true`.
- The bot may pre-check time format and positive integers but must rely on API bounds.
- Quiet hours are interpreted in the configured app/user locale.
- Assigned accounts must be engagement-pool accounts.
- Bot messages must use account IDs or masked display labels only. Full phone numbers must never be
  shown.
- Account assignment changes require confirmation because they affect outbound identity.

API dependencies:

```http
GET /api/communities/{community_id}/engagement-settings
PUT /api/communities/{community_id}/engagement-settings
GET /api/debug/accounts
```

The account list dependency may be replaced by a dedicated engagement-account lookup endpoint later.
If only debug account data is available, the API must provide masked phone numbers before the bot
renders them.

Tests:

- Limit updates preserve hard safety fields.
- Quiet-hour parsing accepts valid `HH:MM` values and rejects malformed ones before API calls.
- Wrong-pool account assignment failures are surfaced from the API.
- Full phone numbers are absent from account selection and settings messages.
- Assignment confirmation displays before/after account labels.
### Slice 9: Admin Permission Boundary

Purpose:

Separate ordinary daily engagement review from configuration that changes outbound permissions,
prompt behavior, style behavior, account assignment, or target approval.

Permission model:

- Regular operator: may use daily review controls when allowed by the backend.
- Engagement admin: may mutate engagement targets, prompt profiles, style rules, topic guidance,
  advanced community settings, and account assignment.
- Backend authorization is the source of truth.
- Bot-side gating is a UX and early-rejection layer, not a security boundary by itself.

Admin-only actions:

- target approval, rejection, archive, and posting permission changes
- prompt profile create, edit, activate, duplicate, rollback
- style rule create, edit, toggle
- topic guidance, keyword, and example mutation
- community rate limits, quiet hours, and account assignment
- any future control that can change outbound behavior

Rules:

- Unauthorized users should receive a clear bot message or callback alert.
- Unauthorized attempts must not call protected mutation endpoints when the bot can identify the
  user as non-admin locally.
- If the bot cannot determine admin status locally, it may call the API and surface the API's
  authorization error.
- Daily candidate review may remain available to non-admin allowlisted operators if the backend
  permits it.
- Permission checks must apply to slash commands and inline callbacks.
- Hidden buttons are not sufficient; handlers must check permissions again.

Implementation options:

- Preferred: backend exposes operator/admin capabilities in the existing bot auth context or a
  dedicated capability endpoint.
- Transitional: bot maintains a separate admin allowlist, while still treating API authorization as
  authoritative.

Tests:

- Non-admin operators cannot mutate prompt profiles, style rules, target approvals, posting
  permissions, topic guidance, or account assignment.
- Unauthorized inline callbacks do not call mutation API-client methods.
- Authorized admins can still reach the same flows.
- Ordinary operators can still use permitted daily review controls.
- Permission checks cover both commands and callbacks.
### Slice 10: Release Documentation And Broader Test Wrap-Up

Purpose:

Close the bot engagement controls feature by updating the wiki, broadening regression coverage, and
documenting shipped behavior across the bot, API, and engagement control-plane specs.

Required documentation updates:

- Update this spec's Current Menu Gap Inventory so shipped controls move from missing to exposed.
- Update `wiki/plan/bot-engagement-controls.md` with completed notes for slices 4 through 9.
- Update `wiki/spec/bot.md` with final command behavior and admin boundary notes.
- Update `wiki/spec/api.md` when API routes or authorization behavior changed.
- Update `wiki/spec/engagement-admin-control-plane.md` when prompt, style, topic, revision, or
  permission behavior changed.
- Update `wiki/spec/database.md` if schema, revision, version, audit, or permission fields changed.
- Update `wiki/index.md` for new implementation roots, migrations, or tests.
- Append `wiki/log.md` entries for each completed change slice.

Required release checks:

- Run focused bot API-client tests.
- Run bot formatting tests.
- Run callback parser tests, including callback length checks.
- Run bot handler tests for command and inline flows.
- Run backend API/service tests for new or changed endpoints.
- Run candidate edit/revision tests.
- Run prompt profile/version tests.
- Run topic example and style rule tests.
- Run admin permission tests.
- Run privacy regressions proving messages omit sender identity, full phone numbers, private account
  metadata, and person-level scores.
- Run the repo's relevant full suite command before final release documentation is marked complete.

Acceptance:

- The shipped bot surface matches this spec and the plan status.
- Missing route controls are hidden or documented as future work.
- Tests cover daily review, admin mutation, confirmation, privacy, and API-client routing.
- The final feature commit is pushed when the remote is configured.
