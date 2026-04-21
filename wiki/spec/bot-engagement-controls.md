# Bot Engagement Controls Spec

## Purpose

This spec defines the next Telegram-bot control surface for the engagement module.

The existing bot engagement controls cover the daily loop:

```text
open cockpit
  -> review candidates
  -> approve or reject
  -> explicitly queue approved sends
  -> inspect audit actions
```

The next layer adds richer operator and admin controls without weakening the engagement safety model:

- engagement target intake and permission management
- prompt profile viewing, previewing, editing, activation, and rollback entrypoints
- style rule and topic example management
- editable candidate replies and revision visibility
- rate limit, quiet hour, and account-assignment controls where the backend already supports them
- clearer separation between daily review and admin configuration

This spec extends:

- `wiki/spec/bot.md`
- `wiki/spec/engagement.md`
- `wiki/spec/engagement-admin-control-plane.md`
- `wiki/spec/telegram-account-pools.md`

It does not replace those specs. Backend state, validation, queueing, Telethon behavior, OpenAI
calls, and audit logging remain owned by the API, services, and workers.

## Goals

- Let an operator manage the full engagement workflow from Telegram without using shell access.
- Keep target approval, prompt configuration, reply review, and send enqueueing explicit.
- Make every outbound-capable action visible, reversible before send, and auditable after send.
- Keep long or risky edits behind confirmation steps.
- Orient menus around operator intentions before backend entities.
- Support safe defaults for small-screen Telegram usage.
- Add controls incrementally, with each slice useful on its own.

## Non-Goals

- No automatic sending.
- No direct messages.
- No top-level posts in the first implementation.
- No bulk joining or bulk sending.
- No person-level scoring, ranking, or outreach priority lists.
- No raw message browsing beyond capped candidate source excerpts.
- No bot code that talks directly to Redis, Postgres, Telethon, OpenAI, or workers.
- No prompt or style control that can disable hard safety validation.

## Operator Modes

The bot has two engagement modes.

### Daily Engagement

Daily engagement is for normal review work.

Entry point:

```text
/engagement
```

Primary controls:

- what needs review today
- approved replies waiting to send
- clear edit, approve, reject, and send actions
- recent action outcomes
- handoff links for community, topic, and voice tuning

Daily controls may be available to ordinary allowlisted operators.

### Engagement Admin

Engagement admin is for configuration that can affect model output or outbound permissions.

Entry point:

```text
/engagement_admin
```

Primary controls:

- which communities may be watched, drafted for, or posted in
- what topics the system should notice
- how replies should sound
- safety limits, quiet hours, and account assignment
- advanced prompt profile controls

Admin controls require an admin permission layer in addition to the normal bot allowlist when the
backend exposes that distinction. Until then, the bot may enforce a transitional Telegram admin
allowlist such as `TELEGRAM_ADMIN_USER_IDS`, while still treating backend authorization as the
source of truth.

## Navigation

The primary navigation must be operator-intention first. Backend entities such as targets, settings,
prompt profiles, style rules, and action rows should be secondary implementation details unless the
operator opens an advanced or diagnostic view.

Recommended top-level engagement menu:

```text
Engagement
  Today
  Review replies
  Approved to send
  Communities
  Topics
  Recent actions
  Admin
```

Recommended engagement admin menu:

```text
Engagement Admin
  Setup
    Communities
    Topics
    Voice rules
    Limits and accounts
  Advanced
    Prompt profiles
    Audit and diagnostics
```

The operator-facing labels should answer common questions:

```text
What needs my review today?
Where are we allowed to participate?
What should the system notice?
How should replies sound?
Why can or can't this be posted?
What changed recently?
```

Telegram reply-keyboard buttons may open these menus, but every state-changing action must also be
reachable through an explicit command for traceability and testing.

Inline callback data must stay under Telegram's 64-byte limit. UUID-heavy actions should use short
prefixes and compact action segments.

## Operator Intention Model

The cockpit should hide backend complexity until it helps the operator make a decision.

| Operator intention | Primary UI label | Backend concepts behind it |
|---|---|---|
| Review what needs attention | Today, Review replies, Approved to send | candidates, candidate statuses, revisions, send jobs |
| Decide where engagement is allowed | Communities | engagement targets, community engagement settings, memberships |
| Decide what to notice | Topics | engagement topics, trigger keywords, negative keywords, topic examples |
| Tune how replies sound | Voice rules | style rules, topic guidance, prompt fragments |
| Understand whether posting is safe | Readiness, Blocked reasons | target permissions, settings mode, joined account, rate limits, expiry |
| Investigate or tune internals | Advanced | prompt profiles, prompt versions, audit/action rows, diagnostics |

Rules:

- Show a short readiness summary before raw booleans.
- Show only the next safe actions for the current state by default.
- Put IDs, raw permission fields, prompt profile internals, and diagnostic details behind expandable
  cards or advanced commands.
- Keep command paths available for traceability, testing, and power users, but make button-led flows
  the normal operator path.
- Prefer verbs the operator understands: watch, draft, review, post, tune, pause, block.
- Avoid making the operator choose between backend concepts that represent one real-world decision.

### Readiness Summaries

Community cards should summarize engagement readiness in one line before showing lower-level fields.

Recommended readiness labels:

- `Not approved`
- `Approved, not joined`
- `Watching only`
- `Drafting replies`
- `Ready to post with review`
- `Paused`
- `Blocked: no joined engagement account`
- `Blocked: posting permission off`
- `Blocked: rate limit or quiet hours`

Candidate cards should summarize send readiness in one line:

- `Needs review`
- `Approved, ready to send`
- `Blocked: community not ready`
- `Blocked: reply expired`
- `Blocked: account or rate limit`
- `Sent`
- `Rejected`
- `Failed, retry may be available`

The readiness summary is derived from backend state. It must not replace backend validation; it is a
human-readable explanation of the same preflight rules.

### Progressive Disclosure

The bot should keep the default card small. Detailed controls should appear only when the operator
opens the relevant item.

Candidate card default actions:

| Candidate state | Default actions |
|---|---|
| `needs_review` | Edit, Approve, Reject |
| `approved` | Send, Reopen/Edit, Reject |
| `failed` | Retry, View error, Reject |
| `sent` | View audit |
| `rejected` or `expired` | View audit |

Community card default actions should be similarly state-aware:

- Not approved: add or approve engagement community.
- Approved but not joined: join or keep watching without join.
- Watching only: enable drafting or pause.
- Drafting: review suggested replies, adjust topics, or pause.
- Ready to post: review approved replies, adjust limits, or pause posting.
- Blocked: show the single most important next fix first.

## Config Editing Model

The engagement admin cockpit should let admins edit most engagement configuration from Telegram,
but the bot must remain a control surface, not the source of truth.

Config editing must be reached from intention pages where possible. For example, editing
`allow_detect` should appear to the operator as changing whether a community is watched, and editing
topic trigger keywords should appear as tuning what the system notices. Raw field names may be shown
in advanced detail cards, logs, and tests, but should not be the primary label in normal use.

Every editable engagement setting should follow the same contract:

1. The backend owns the persisted value.
2. The API exposes a typed route for reading and updating that value.
3. The service layer validates safety, bounds, state transitions, and authorization.
4. The bot renders the current value, collects the proposed value, shows a preview or before/after
   confirmation, and then calls the API.
5. The mutation creates audit or version history when it can affect outbound behavior.

The bot must not implement a generic "edit any database column" surface. Each editable field must be
explicitly allowlisted by entity, field name, value type, and admin requirement.

Recommended editable field metadata:

```text
entity
field
label
value_type
requires_confirmation
admin_only
```

Supported first implementation value types:

- `text`
- `long_text`
- `int`
- `float`
- `bool`
- `enum`
- `time`
- `uuid`
- `keyword_list`

Short values may use commands or inline toggles. Long text values should use conversation-state
editing. Risky values, including posting permission, prompt activation, assigned account changes,
and long instruction changes, must show a confirmation before saving.

### Editable Config Map

The admin cockpit should expose these editable areas.

| Area | Editable fields | Notes |
|---|---|---|
| Engagement targets | `notes`, status transitions, `allow_join`, `allow_detect`, `allow_post` | Approval and permission changes require confirmation and before/after display. |
| Community settings | `mode`, `max_posts_per_day`, `min_minutes_between_posts`, quiet hours, assigned engagement account, allowed join/post flags where supported | MVP edits must preserve `reply_only=true` and `require_approval=true`. |
| Prompt profiles | `name`, `description`, `model`, `temperature`, `max_output_tokens`, `system_prompt`, `user_prompt_template` | Prompt edits create immutable backend versions. Activation is separate and confirmed. |
| Topics | `name`, `description`, `stance_guidance`, `trigger_keywords`, `negative_keywords`, good examples, bad examples, `active` | The bot should present two topic-guidance prompts: "What kind of conversation are we looking for?" and "What position should we take?" Bad examples are never templates to copy. |
| Style rules | `name`, `priority`, `rule_text`, `active` | The bot should frame style rules as: "How should this account sound in this community?" Scope may be immutable after creation in the first implementation. |
| Candidates | `final_reply`, approval/rejection/send state | Final replies are editable only before terminal states. Sending remains separate from approval. |
| Account assignment | assigned engagement account for a community | Only engagement-pool accounts are valid. Bot output must not expose full phone numbers. |

### Instruction Inputs

Written instruction fields include prompt profile prompts, topic guidance, topic good/bad examples,
style rules, and manually edited candidate replies.

These fields are operator/admin-authored configuration. They may be assisted by future draft helpers,
but generated suggestions must be treated as drafts only. A generated or inferred instruction must
not become active until an admin reviews it and explicitly saves it.

The bot should label instruction fields clearly:

- Prompt profile text controls the detection/drafting prompt.
- Topic guidance has two operator-facing values: what kind of conversation to look for, and what
  position to take when that conversation appears.
- Good examples show desired reply shape.
- Bad examples show what to avoid and must be passed to the model only as negative examples.
- Style rules tune how the account should sound in this community, including voice, brevity,
  disclosure, and community/topic-specific constraints.
- Candidate final reply is the exact text eligible for approval and eventual sending.

### Safety Floor

Editable configuration must never weaken hard safety rules. The backend and workers must continue to
enforce:

- no DMs
- no automatic sending in MVP
- no impersonation or fake personal experience
- no hidden sponsorship or fake consensus
- no person-level scoring, ranking, or targeting
- no bypassing operator approval
- no disabling audit logs
- no outbound behavior from collection, discovery, expansion, or analysis workers

If an editable prompt, topic, style rule, or reply conflicts with these rules, backend validation or
worker preflight must reject, skip, or fail closed.

## Current Menu Gap Inventory

This inventory records the gap between the current bot engagement menu and the target control
surface in this spec. It should be updated as implementation slices ship.

### Currently Exposed

The current main engagement menu exposes:

- `/engagement` cockpit.
- Inline intention-first `Today`, `Review replies`, `Approved to send`, `Communities`, `Topics`,
  `Recent actions`, and `Admin` buttons, with the `Admin` entry hidden when the bot can identify
  the caller as a non-admin locally.
- Candidate queue filters for `needs_review`, `approved`, `failed`, `sent`, and `rejected`.
- Candidate cards with readiness summaries and state-relevant approve, reject, edit, audit, and
  queue-send command hints.
- `/engagement_candidate <candidate_id>` detail cards with capped source excerpt, prompt provenance,
  risk notes, current final reply, revision entrypoint, and state-aware controls.
- `/edit_reply <candidate_id> | <new final reply>` as a pipe-command edit path.
- `/edit_reply <candidate_id>` as a guided reply-edit flow: the bot stores a pending edit by
  Telegram operator ID, accepts the next text message as the proposed final reply, shows a
  preview, and saves or cancels through `eng:edit:save` / `eng:edit:cancel`.
- Candidate detail buttons can start the same guided reply-edit preview/save flow.
- `/candidate_revisions <candidate_id>` shows immutable reply revision history.
- `/expire_candidate <candidate_id>` explicitly moves a reviewable candidate out of the queue when
  the backend permits it.
- `/retry_candidate <candidate_id>` reopens failed candidates for review when the backend permits
  the transition.
- Shared config-editing foundation with explicit editable field metadata, typed parsers for
  text/long-text/int/float/bool/enum/time/UUID/keyword-list values, per-operator pending state,
  15-minute expiry, and entity-specific API save dispatch.
- `/cancel_edit` for discarding the caller's pending guided edit.
- `/engagement_actions [community_id]`.
- `/engagement_rollout [window_days]` aggregate semantic-selector rollout summary by similarity
  band.
- `/engagement_settings <community_id>`.
- Community settings cards with readiness summaries before raw mode, permission, and rate-limit
  fields.
- `/set_engagement <community_id> <off|observe|suggest|ready>`.
- `/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>`.
- `/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>`.
- `/clear_engagement_quiet_hours <community_id>`.
- `/assign_engagement_account <community_id> <telegram_account_id>`.
- `/clear_engagement_account <community_id>`.
- Community settings cards now show direct command hints for limits, quiet hours, account
  assignment, join, and manual detection.
- Account assignment and account clearing commands now show before/after masked account labels and
  require a confirmation callback before saving.
- Non-admin operators now get read-only target/topic/settings cards where the bot can identify them
  locally, and admin-only prompt/style/admin-menu callbacks are rejected before protected mutation
  API calls.
- Assigned engagement accounts render as account IDs plus masked-phone labels from
  `/api/debug/accounts` when available.
- `/join_community <community_id>`.
- `/detect_engagement <community_id> [window_minutes]`.
- `/engagement_topics`, `/engagement_topic <topic_id>`, topic creation, topic active-state toggles,
  good/bad topic examples, example removal, keyword updates, and guided topic-guidance editing.
- `/engagement_admin` with inline `Communities`, `Topics`, `Voice rules`, `Limits/accounts`,
  `Advanced`, and back-to-engagement buttons.
- `/engagement_targets [status]`, `/engagement_target`, `/add_engagement_target`,
  `/resolve_engagement_target`, `/approve_engagement_target`, `/reject_engagement_target`,
  `/archive_engagement_target`, `/target_permission`, `/target_join`, and `/target_detect`.
- Inline target list filters for all, pending, resolved, approved, failed, rejected, and archived.
- Target cards with readiness summaries before raw target status and permission fields.
- Target cards with add-target, open/detail, resolve, approve, reject, archive, permission toggle,
  target-scoped join, and target-scoped detect controls.
- Target approval now shows an explicit before/after confirmation card before saving, and the API
  mutation happens only from the confirm callback.
- Target posting-permission changes now show an explicit before/after confirmation card before
  saving. Join and detect permission toggles remain direct.
- `/engagement_prompts`, `/engagement_prompt_preview`, and direct prompt activation.
- `/engagement_prompt <profile_id>` detail cards with full profile metadata and capped prompt
  previews.
- `/engagement_prompt_versions <profile_id>` immutable version history with rollback entrypoints.
- `/activate_engagement_prompt <profile_id>` and inline activation now show an explicit
  confirmation card before activation.
- `/duplicate_engagement_prompt <profile_id> <new_name>` and inline default duplication call the
  prompt profile duplicate API.
- `/edit_engagement_prompt <profile_id> <field>` starts the shared guided config-edit flow for
  allowlisted prompt profile fields.
- `/rollback_engagement_prompt <profile_id> <version_number>` and inline rollback controls show an
  explicit confirmation card before calling the rollback API.
- Prompt template edits reject unsupported variables, including sender identity variables, before
  calling the API when possible.
- `/engagement_style [scope] [scope_id]`, `/engagement_style_rule <rule_id>`,
  `/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>`,
  `/edit_style_rule <rule_id>`, and `/toggle_style_rule <rule_id> <on|off>`.
- Style-rule lists now expose scope filters plus inline create-help, open, edit, and toggle
  controls.
- Button-led edit entrypoints now start the shared guided edit flow for candidate final replies,
  prompt profile fields, topic guidance, and style-rule text where those cards expose edit buttons.
- Admin-only command, callback, and guided-edit save paths now reject locally identified non-admins
  before protected API mutations are called. Daily review, target detail, topic detail, style list,
  settings detail, and audit views remain readable where the backend permits them.

### Missing From Daily Engagement

- `Settings lookup` menu item.

### Missing From Engagement Targets

- Conversation-state target note editing.

### Missing From Prompt Profiles

- Prompt profile creation.
- Dedicated prompt profile creation command.

### Missing From Topics And Examples

- Inline buttons for adding topic examples from Telegram conversation state.

### Missing From Style Rules

- Inline style-rule creation form beyond the current command-led create entrypoint.

### Missing From Community Controls

- Inline community controls for rate limits, quiet hours, and account assignment.

### Missing Cross-Cutting UX

- Full readiness summaries for membership, account assignment, expiry, rate limits, and quiet-hour
  blocks when those backend fields are exposed to the bot.
- Further progressive disclosure to keep raw IDs and backend fields behind detail/open views on
  every card.
- Button-led entrypoints that start the shared edit flow from target note and settings cards.
- Confirmation flows for risky admin mutations, including prompt activation, posting permission
  changes, target approval, and account assignment.

## Implementation Slice Contracts

This section defines the remaining bot engagement control slices. The plan file tracks execution
status; this spec defines the behavior that must be true when each slice is shipped.

Each slice should keep the bot as a Telegram-native control surface over explicit backend APIs. The
bot may parse operator input, render current state, collect confirmation, and call the API. It must
not bypass API validation, mutate storage directly, or make outbound Telethon/OpenAI calls.

### Slice 4: Config Editing Foundation

Purpose:

Build one shared editing model for the long-text and risky configuration flows used by later slices.
This slice should make edits predictable before adding more editable surfaces.

Required bot capabilities:

- Maintain pending edit state by Telegram operator ID, edit type, object ID, field name, started
  timestamp, and expected value type.
- Expose reusable Save and Cancel callbacks for pending edits.
- Expire pending edits after a short timeout, recommended 15 minutes.
- Cancel or supersede an operator's pending edit when they start another command or edit flow.
- Render before/after confirmations for risky changes.
- Render preview cards for long instruction values before saving.
- Keep callback data compact enough for Telegram's 64-byte callback limit.

Editable field metadata must be explicit and allowlisted. The minimum metadata is:

```text
entity
field
label
value_type
requires_confirmation
admin_only
api_method
```

Supported value types:

- `text`
- `long_text`
- `int`
- `float`
- `bool`
- `enum`
- `time`
- `uuid`
- `keyword_list`

Rules:

- The editing foundation must not expose a generic database-column editor.
- Each save must dispatch to an entity-specific API-client method.
- Risky changes include posting permission, target approval, prompt activation, prompt rollback,
  assigned account changes, and long instruction updates.
- Backend validation remains authoritative for prompt variables, unsafe guidance, account pool
  eligibility, numeric bounds, and state transitions.
- The bot should pre-check malformed values only to produce clearer operator feedback.

Tests:

- Pending edits are scoped to one operator and cannot be saved by another.
- Save without a matching pending edit is rejected.
- Cancel removes only the caller's pending edit.
- Expired edits cannot be saved.
- Long text previews show the submitted value without calling send, generation, Telethon, or worker
  endpoints.
- Risky edits require a confirmation callback before the API mutation is called.

Done when:

- Candidate reply, prompt field, topic guidance, and style rule edit flows can share the same
  pending-edit and confirmation machinery.
- Later slices can register editable fields without adding new state-machine code.

### Slice 5: Candidate Detail, Editing, And Revisions

Purpose:

Make candidate review inspectable and editable before approval. Operators should be able to see the
full safe candidate context, revise final reply text, inspect revision history, and manage failed or
stale candidates.

Required commands:

```text
/engagement_candidate <candidate_id>
/edit_reply <candidate_id> | <new final reply>
/candidate_revisions <candidate_id>
/expire_candidate <candidate_id>
/retry_candidate <candidate_id>
```

Required inline controls:

- Open candidate detail from candidate list cards.
- Start reply edit.
- Save or cancel reply edit preview.
- Approve only after the operator can see the current final reply.
- Send only for approved candidates.
- View audit or revisions from terminal and non-terminal candidates.

Candidate detail cards should show:

- send readiness summary
- candidate ID
- community title and username when available
- topic name
- status and expiry
- capped source excerpt
- detected reason
- suggested reply
- current final reply
- prompt profile and version when available
- risk notes
- revision count when available
- next safe actions

Rules:

- Source excerpts must be capped.
- Sender identity, phone numbers, private account metadata, and person-level scores must never be
  shown.
- The exact final reply must not be truncated in approval or send confirmations. Split long
  confirmations across messages if needed.
- Sent, rejected, and expired candidates are read-only in normal controls.
- Approval and send remain separate.
- Retry is available only when the backend says the failed state is retryable.
- Expire is an explicit operator action and should leave an audit trail when the API supports it.

API dependencies:

```http
GET  /api/engagement/candidates/{candidate_id}
GET  /api/engagement/candidates/{candidate_id}/revisions
POST /api/engagement/candidates/{candidate_id}/edit
POST /api/engagement/candidates/{candidate_id}/expire
POST /api/engagement/candidates/{candidate_id}/retry
```

If detail, revisions, expire, or retry endpoints are missing, hide the related inline control and
return a clear command response instead of approximating behavior from list data.

Tests:

- Candidate detail formatting omits sender identity and private metadata.
- Editing creates a revision through the API and refreshes the candidate card.
- Approval uses the latest valid final reply.
- Send controls appear only for approved candidates.
- Terminal candidates do not expose edit controls.
- Failed non-retryable candidates do not expose retry controls.

### Slice 6: Prompt Profile Admin Controls

Purpose:

Expose prompt profile inspection and administration from the engagement admin cockpit without making
prompt editing part of daily candidate review.

Required commands:

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

Editable fields:

- `name`
- `description`
- `model`
- `temperature`
- `max_output_tokens`
- `system_prompt`
- `user_prompt_template`

Required inline controls:

- Open profile detail.
- Preview rendered prompt.
- View versions.
- Edit allowlisted fields.
- Duplicate profile when supported by the API.
- Activate profile with confirmation.
- Roll back to a version with confirmation.

Rules:

- Prompt profile controls belong under `Engagement Admin -> Advanced`.
- Preview is render-only unless a later spec introduces an explicitly named test-generation route.
- Prompt activation must show profile name, version, model, temperature, token limit, and output
  schema before confirmation.
- Prompt edits must create immutable backend versions.
- The bot may reject unknown field names and obvious unsupported prompt variables before calling the
  API, but backend validation remains authoritative.
- The bot must never display sender identity or private account metadata in prompt previews.
- Prompt profile changes are admin-only once the permission boundary exists.

API dependencies:

```http
GET  /api/engagement/prompt-profiles
POST /api/engagement/prompt-profiles
GET  /api/engagement/prompt-profiles/{profile_id}
PATCH /api/engagement/prompt-profiles/{profile_id}
POST /api/engagement/prompt-profiles/{profile_id}/activate
POST /api/engagement/prompt-profiles/{profile_id}/preview
GET  /api/engagement/prompt-profiles/{profile_id}/versions
POST /api/engagement/prompt-profiles/{profile_id}/duplicate
POST /api/engagement/prompt-profiles/{profile_id}/rollback
```

Duplicate and rollback controls use first-class backend routes in the shipped implementation.

Tests:

- Prompt preview does not call generation or send endpoints.
- Long prompt edits use the shared edit preview/save/cancel flow.
- Activation requires explicit confirmation.
- Unknown prompt fields are rejected.
- Unsupported prompt variables are rejected or surfaced from API validation.
- Version cards show enough metadata to explain what would activate or roll back.

### Slice 7: Topic Examples And Style Rules

Purpose:

Let admins tune what the system notices and how replies should sound through topic examples,
keyword edits, topic guidance, and style rules.

Required topic commands:

```text
/engagement_topic <topic_id>
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>
```

Required style commands:

```text
/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
```

Required inline controls:

- Open topic detail from topic lists.
- Add good example.
- Add bad example.
- Remove good or bad example by index until examples have stable IDs.
- Edit trigger and negative keywords.
- Edit topic guidance with the shared long-text flow.
- Open style rule detail.
- Filter style rules by scope.
- Create, edit, activate, and deactivate style rules.

Rules:

- Topic screens should use operator language: what to notice, what to avoid, and what useful replies
  sound like.
- Good examples are desired-shape guidance, not templates to copy word for word.
- Bad examples are avoid-this guidance and must never be presented as candidate text.
- Keyword edits replace the selected keyword list unless a later API exposes add/remove operations.
- Style rules may make replies stricter, shorter, clearer, or more contextual.
- Style rules may not permit DMs, impersonation, hidden sponsorship, fake consensus, harassment,
  moderation evasion, unsafe link behavior, or disabling approval.
- Style rule scope and priority must be visible in every style rule card.

API dependencies:

```http
GET    /api/engagement/topics/{topic_id}
PATCH  /api/engagement/topics/{topic_id}
POST   /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}

GET    /api/engagement/style-rules
POST   /api/engagement/style-rules
GET    /api/engagement/style-rules/{rule_id}
PATCH  /api/engagement/style-rules/{rule_id}
```

Tests:

- Good and bad examples are labeled distinctly in cards and previews.
- Bad examples are not surfaced as reusable reply text.
- Topic keyword parsing handles commas, whitespace, and empty lists consistently.
- Topic guidance edits use preview/save/cancel.
- Style rule scope filters call the API with explicit scope parameters.
- Unsafe guidance remains blocked by backend validation.

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

## Command Surface

### Daily Review Commands

Existing commands remain valid:

```text
/engagement
/engagement_candidates [status]
/edit_reply <candidate_id> | <new final reply>
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/send_reply <candidate_id>
/engagement_actions [community_id]
```

Expanded daily commands:

```text
/engagement_candidate <candidate_id>
/candidate_revisions <candidate_id>
/expire_candidate <candidate_id>
/retry_candidate <candidate_id>
```

Rules:

- Command syntax is a traceability and testing surface. The normal operator path should be
  button-led cards from `Today`, `Review replies`, and `Approved to send`.
- `/engagement_candidate` shows one full candidate card with capped source excerpt, suggested
  reply, current final reply, prompt provenance, risk notes, status, expiry, and next actions.
- `/candidate_revisions` shows manual reply revisions and who edited them.
- `/expire_candidate` is an explicit operator action for stale candidates that should leave the
  review queue.
- `/retry_candidate` may move an operationally failed candidate back to a reviewable state only when
  the API permits that transition.

### Target Commands

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

Rules:

- Target commands power the `Communities` screen. Operator-facing copy should talk about watching,
  drafting, joining, and posting rather than only `allow_*` flags.
- Adding an engagement target must call the engagement target API and must not create seed rows.
- A target must resolve to a community before it can be approved.
- Approval and permission changes must show the current `allow_join`, `allow_detect`, and
  `allow_post` state before and after the action.
- Target-level join and detect controls call target-scoped API routes when available. If the API
  only supports community-scoped routes, the bot must still verify and display the approved target
  gate returned by the API.
- Rejecting or archiving a target forces all permissions off through the API.

### Prompt Profile Commands

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

Editable fields:

- `name`
- `description`
- `model`
- `temperature`
- `max_output_tokens`
- `system_prompt`
- `user_prompt_template`

Rules:

- Prompt profile controls belong under `Advanced` by default. Most day-to-day tuning should use
  `Topics` and `Voice rules`.
- Long prompt fields should use conversation-state editing: the admin starts an edit, sends the new
  text as the next message, reviews a rendered preview, then confirms save.
- Every edit creates or references an immutable backend version row.
- Activation must be explicit and should show the profile name, version number, model, temperature,
  and output schema before confirmation.
- Prompt preview is render-only unless a later API endpoint is explicitly named as a generation
  test endpoint.
- The bot must not display or accept unapproved prompt variables.

### Topic Example Commands

Existing topic commands remain valid:

```text
/engagement_topics
/create_engagement_topic <name> | <guidance> | <comma_keywords>
/toggle_engagement_topic <topic_id> <on|off>
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
```

Expanded topic commands:

```text
/engagement_topic <topic_id>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>
```

Rules:

- Topic controls should be labeled as "what to notice" and "what to say about it" before showing raw
  keyword arrays.
- Good examples are positive guidance.
- Bad examples are avoid-this guidance and must never be treated as templates to copy.
- Example removal by array index is acceptable until the backend stores examples as first-class
  rows.
- Topic guidance edits may use conversation-state editing because guidance can be multi-paragraph.

### Style Rule Commands

```text
/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
```

Supported scopes:

- `global`
- `account`
- `community`
- `topic`

Rules:

- Style rule controls should be labeled as `Voice rules` in normal navigation.
- Style rules may make replies stricter, shorter, more contextual, or more transparent.
- Style rules may not permit DMs, impersonation, fake consensus, harassment, moderation evasion, or
  unsafe link behavior.
- The bot should show scope, active state, priority, capped rule text, and last update metadata when
  available.
- Long rule edits should use a preview-and-confirm flow.

### Community Control Commands

Existing commands remain valid:

```text
/engagement_settings <community_id>
/set_engagement <community_id> <off|observe|suggest|ready>
/join_community <community_id>
/detect_engagement <community_id> [window_minutes]
```

Expanded community commands:

```text
/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>
/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>
/clear_engagement_quiet_hours <community_id>
/assign_engagement_account <community_id> <telegram_account_id>
/clear_engagement_account <community_id>
```

Rules:

- Community controls should be summarized as readiness, safety limits, and account assignment before
  raw settings fields.
- Limit updates must preserve `reply_only=true` and `require_approval=true`.
- The backend owns numeric bounds. The bot may pre-check obvious malformed values but must rely on
  API validation.
- Quiet hours are interpreted in the deployment/user locale configured for the app.
- Assigned accounts must be engagement-pool accounts. The API validates this; the bot displays the
  error if the account is in the wrong pool.
- The bot must never show full account phone numbers.

## Inline Controls

Recommended callback prefixes:

```text
eng:home
eng:admin
eng:c:<status>:<offset>
eng:cd:<candidate_id>
eng:ca:<candidate_id>
eng:cr:<candidate_id>
eng:cs:<candidate_id>
eng:ce:<candidate_id>
eng:t:list:<status>:<offset>
eng:t:open:<target_id>
eng:t:perm:<target_id>:<j|d|p>:<0|1>
eng:t:approve:<target_id>
eng:t:reject:<target_id>
eng:p:list:<offset>
eng:p:open:<profile_id>
eng:p:preview:<profile_id>
eng:p:activate:<profile_id>
eng:topic:list:<offset>
eng:topic:open:<topic_id>
eng:style:list:<scope>:<offset>
eng:style:open:<rule_id>
eng:set:open:<community_id>
```

The exact names may change during implementation if needed to preserve the 64-byte callback limit.
The important contract is that engagement callbacks stay inside the `eng:*` namespace and route
only through bot API-client methods.

## Conversation-State Editing

Some controls need multi-message input because Telegram command arguments are awkward for long text.

Supported first-state flows:

- edit prompt system prompt
- edit prompt user template
- edit topic guidance
- edit style rule text
- edit candidate final reply

State machine:

```text
start edit
  -> bot records pending edit type, object ID, field, and operator ID
  -> operator sends replacement text
  -> bot calls preview or validation endpoint
  -> bot shows preview plus Save and Cancel controls
  -> Save calls the API mutation
  -> Cancel clears pending state
```

Rules:

- Pending edits are scoped to the operator's Telegram user ID.
- Pending edits expire after a short timeout, recommended 15 minutes.
- A new command from the same operator cancels or supersedes the pending edit after warning.
- The bot should not persist long edit text outside the existing bot process unless a future spec
  introduces durable draft storage.

## Message Formatting

Candidate cards should show:

- send readiness summary
- candidate ID
- community title and username when available
- topic name
- status and expiry
- capped source excerpt
- detected reason
- suggested reply
- final reply when different from the suggestion
- prompt profile and version
- risk notes
- next safe actions

Target cards should show:

- community readiness summary
- target ID
- submitted reference
- resolved community when available
- status
- `allow_join`, `allow_detect`, and `allow_post`
- last error when present
- next safe actions

Prompt cards should show:

- profile ID
- name and active state
- version
- model, temperature, and max output tokens
- output schema
- capped system and user-template previews
- next safe actions

Style cards should show:

- rule ID
- scope and scope ID
- active state
- priority
- capped rule text
- next safe actions

Formatting rules:

- Put the operator-facing summary and next safe action above raw IDs and backend fields.
- Prefer compact cards over long lists.
- Show only state-relevant actions on default cards; move diagnostic and advanced actions into detail
  views.
- Truncate source excerpts before final reply text.
- Never truncate final reply text in a send confirmation card. If it is too long for Telegram,
  split the confirmation into multiple messages.
- Never expose sender identity, phone numbers, full account secrets, raw prompt internals that are
  not meant for operators, or person-level scores.

## API Dependencies

The bot should use existing or planned engagement API routes only.

Required for the expanded controls:

```http
GET    /api/engagement/targets
GET    /api/engagement/targets/{target_id}
POST   /api/engagement/targets
PATCH  /api/engagement/targets/{target_id}
POST   /api/engagement/targets/{target_id}/resolve-jobs
POST   /api/engagement/targets/{target_id}/join-jobs
POST   /api/engagement/targets/{target_id}/detect-jobs

GET    /api/engagement/prompt-profiles
POST   /api/engagement/prompt-profiles
GET    /api/engagement/prompt-profiles/{profile_id}
PATCH  /api/engagement/prompt-profiles/{profile_id}
POST   /api/engagement/prompt-profiles/{profile_id}/activate
POST   /api/engagement/prompt-profiles/{profile_id}/duplicate
POST   /api/engagement/prompt-profiles/{profile_id}/rollback
POST   /api/engagement/prompt-profiles/{profile_id}/preview
GET    /api/engagement/prompt-profiles/{profile_id}/versions

GET    /api/engagement/style-rules
GET    /api/engagement/style-rules/{rule_id}
POST   /api/engagement/style-rules
PATCH  /api/engagement/style-rules/{rule_id}

GET    /api/engagement/topics/{topic_id}
POST   /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}
GET    /api/engagement/candidates/{candidate_id}
GET    /api/engagement/candidates/{candidate_id}/revisions
POST   /api/engagement/candidates/{candidate_id}/edit
POST   /api/engagement/candidates/{candidate_id}/expire
POST   /api/engagement/candidates/{candidate_id}/retry
```

If an API route is missing, the bot slice should add the API route first or keep the related bot
control hidden.

## Safety Rules

- Approval and sending remain separate.
- Queueing a send requires an approved candidate.
- The bot must never offer send controls for `needs_review`, `rejected`, `expired`, or `sent`
  candidates.
- The bot must never create seed rows from engagement target commands.
- Engagement target permissions are engagement-only and must not change community discovery,
  collection, or analysis state.
- All target, prompt, style, topic, candidate edit, approval, send, and action views must preserve
  audit-relevant IDs.
- Any control that can enable posting must show the current permission state before mutation and the
  resulting state after mutation.
- Admin prompt and style controls may not weaken hardcoded backend validation.

## Testing Contract

Minimum tests for implementation:

- Bot API client tests for each new route.
- Formatting tests for target, prompt, style, candidate detail, and revision cards.
- Callback parser tests for every new `eng:*` namespace and the Telegram 64-byte limit.
- Handler tests proving target commands do not call seed APIs.
- Handler tests proving prompt preview does not call generation or send endpoints.
- Conversation-state tests for long prompt, topic, style, and candidate edit flows.
- Permission tests for admin-only commands once backend admin permission exists.
- Safety tests proving send controls appear only for approved candidates.
- Regression tests proving phone numbers, sender identity, and person-level scores are absent from
  bot messages.

## Open Questions

- Long-term admin permission should move to backend capabilities. The shipped bot also has a
  transitional `TELEGRAM_ADMIN_USER_IDS` allowlist for early local hiding/rejection.
- Prompt duplicate and rollback are now first-class API routes.
- Should engagement target approval create default community engagement settings, or remain a
  separate explicit settings action?
- Assigned engagement accounts currently render as account IDs plus masked labels from
  `/api/debug/accounts` when available.
- Should long edit drafts survive bot restarts, or is short-lived in-process state enough for the
  first slice?
