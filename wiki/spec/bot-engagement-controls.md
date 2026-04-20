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

- candidate queues by status
- candidate detail cards
- edit, approve, reject, and queue-send actions
- recent action audit rows
- community settings handoff

Daily controls may be available to ordinary allowlisted operators.

### Engagement Admin

Engagement admin is for configuration that can affect model output or outbound permissions.

Entry point:

```text
/engagement_admin
```

Primary controls:

- engagement targets and permissions
- prompt profiles and prompt previews
- topic guidance and good/bad examples
- style rules
- community rate limits, quiet hours, and account assignment

Admin controls require an admin permission layer in addition to the normal bot allowlist when the
backend exposes that distinction. Until then, the bot should keep admin actions behind distinct
commands and confirmation copy so they are not confused with daily review.

## Navigation

Recommended top-level engagement menus:

```text
Engagement
  Candidates
  Approved queue
  Actions
  Settings lookup

Engagement Admin
  Targets
  Prompt profiles
  Topics and examples
  Style rules
  Community controls
```

Telegram reply-keyboard buttons may open these menus, but every state-changing action must also be
reachable through an explicit command for traceability and testing.

Inline callback data must stay under Telegram's 64-byte limit. UUID-heavy actions should use short
prefixes and compact action segments.

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

- Prefer compact cards over long lists.
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
POST   /api/engagement/prompt-profiles/{profile_id}/preview
GET    /api/engagement/prompt-profiles/{profile_id}/versions

GET    /api/engagement/style-rules
POST   /api/engagement/style-rules
PATCH  /api/engagement/style-rules/{rule_id}

POST   /api/engagement/topics/{topic_id}/examples
DELETE /api/engagement/topics/{topic_id}/examples/{example_type}/{index}
POST   /api/engagement/candidates/{candidate_id}/edit
```

Optional or future API routes:

```http
GET    /api/engagement/candidates/{candidate_id}
GET    /api/engagement/candidates/{candidate_id}/revisions
POST   /api/engagement/candidates/{candidate_id}/expire
POST   /api/engagement/candidates/{candidate_id}/retry
POST   /api/engagement/prompt-profiles/{profile_id}/duplicate
POST   /api/engagement/prompt-profiles/{profile_id}/rollback
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

- Should admin permission be enforced entirely in the backend, or should the bot maintain a separate
  admin allowlist for faster first implementation?
- Should prompt duplicate and rollback be first-class API routes now, or implemented as create/edit
  flows from existing profile versions?
- Should engagement target approval create default community engagement settings, or remain a
  separate explicit settings action?
- Should assigned engagement account selection list account IDs only, or include masked display
  labels from `/api/debug/accounts`?
- Should long edit drafts survive bot restarts, or is short-lived in-process state enough for the
  first slice?
