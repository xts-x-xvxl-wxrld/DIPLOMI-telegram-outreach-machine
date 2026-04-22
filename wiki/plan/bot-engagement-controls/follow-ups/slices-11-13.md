# Bot Engagement Follow-Up Slices 11-13

Safety confirmations, guided edit entrypoints, and creation flow follow-ups.

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
