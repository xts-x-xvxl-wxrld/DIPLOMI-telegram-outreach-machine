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
backend exposes that distinction. Until then, the bot should keep admin actions behind distinct
commands and confirmation copy so they are not confused with daily review.

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
| Topics | `name`, `description`, `stance_guidance`, `trigger_keywords`, `negative_keywords`, good examples, bad examples, `active` | Guidance and examples are admin-authored instruction inputs. Bad examples are never templates to copy. |
| Style rules | `name`, `priority`, `rule_text`, `active` | Scope may be immutable after creation in the first implementation. |
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
- Topic guidance controls when and how the system should be useful for one subject.
- Good examples show desired reply shape.
- Bad examples show what to avoid and must be passed to the model only as negative examples.
- Style rules tune voice, brevity, disclosure, and community/topic-specific constraints.
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
- Inline `Topics`, `Replies`, `Audit`, and `Admin` buttons.
- Candidate queue filters for `needs_review`, `approved`, `failed`, `sent`, and `rejected`.
- Candidate approve, reject, and queue-send controls.
- `/edit_reply <candidate_id> | <new final reply>` as a pipe-command edit path.
- `/engagement_actions [community_id]`.
- `/engagement_settings <community_id>`.
- `/set_engagement <community_id> <off|observe|suggest|ready>`.
- `/join_community <community_id>`.
- `/detect_engagement <community_id> [window_minutes]`.
- `/engagement_topics`, topic creation, topic active-state toggles, and good/bad topic examples.
- `/engagement_admin` with inline `Targets`, `Prompts`, `Style rules`, and back-to-engagement
  buttons.
- `/engagement_targets`, `/add_engagement_target`, and `/approve_engagement_target`.
- `/engagement_prompts`, `/engagement_prompt_preview`, and direct prompt activation.
- `/engagement_style` as a read-only style-rule list.

### Missing From Daily Engagement

- Direct `Approved queue` menu item.
- `Settings lookup` menu item.
- Candidate detail/open command: `/engagement_candidate <candidate_id>`.
- Inline candidate open/details handler. `ACTION_ENGAGEMENT_CANDIDATE_OPEN` exists in bot UI code,
  but the callback is not handled yet.
- Candidate revisions command: `/candidate_revisions <candidate_id>`.
- Candidate expire command: `/expire_candidate <candidate_id>`.
- Candidate retry command: `/retry_candidate <candidate_id>`.
- Inline or conversation-state edit-reply flow. The pipe command exists, but there is no button-led
  preview and confirmation flow.

### Missing From Engagement Targets

- Add-target menu button. `/add_engagement_target` exists, but the admin menu only lists targets.
- Target detail/open command: `/engagement_target <target_id>`.
- Resolve target command: `/resolve_engagement_target <target_id>`.
- Reject target command: `/reject_engagement_target <target_id>`.
- Archive target command: `/archive_engagement_target <target_id>`.
- Permission toggle command:
  `/target_permission <target_id> <join|detect|post> <on|off>`.
- Target-scoped join command: `/target_join <target_id>`.
- Target-scoped detect command: `/target_detect <target_id> [window_minutes]`.
- Target status filters in target list navigation.
- Inline target detail, resolve, reject, archive, permission, join, and detect controls.

### Missing From Prompt Profiles

- Prompt detail/open command: `/engagement_prompt <profile_id>`.
- Prompt version list command: `/engagement_prompt_versions <profile_id>`.
- Inline prompt preview button. `/engagement_prompt_preview` exists, but prompt cards only show it as
  command text.
- Prompt profile creation.
- Prompt profile duplication: `/duplicate_engagement_prompt <profile_id> <new_name>`.
- Prompt profile field editing: `/edit_engagement_prompt <profile_id> <field>`.
- Prompt profile rollback: `/rollback_engagement_prompt <profile_id> <version_number>`.
- Activation confirmation. Current prompt activation is direct.
- Conversation-state editing for long prompt fields.

### Missing From Topics And Examples

- Admin menu button for `Topics and examples`; topics currently live in the main engagement menu.
- Topic detail/open command: `/engagement_topic <topic_id>`.
- Remove topic example command: `/topic_remove_example <topic_id> <good|bad> <index>`.
- Topic keyword editing command:
  `/topic_keywords <topic_id> <trigger|negative> <comma_keywords>`.
- Topic guidance editing command: `/edit_topic_guidance <topic_id>`.
- Inline buttons for adding and removing examples.
- Conversation-state editing for topic guidance.

### Missing From Style Rules

- Style rule detail/open command: `/engagement_style_rule <rule_id>`.
- Style rule creation:
  `/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>`.
- Style rule editing: `/edit_style_rule <rule_id>`.
- Style rule active-state toggles: `/toggle_style_rule <rule_id> <on|off>`.
- Scope filters for style-rule lists. The API client supports scope filters, but the menu does not
  expose them.
- Inline style-rule detail, create, edit, and toggle controls.
- Conversation-state editing for long style rule text.

### Missing From Community Controls

- `Community controls` menu entry under engagement admin.
- Rate-limit command:
  `/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>`.
- Quiet-hours command: `/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>`.
- Clear quiet-hours command: `/clear_engagement_quiet_hours <community_id>`.
- Assigned-account command: `/assign_engagement_account <community_id> <telegram_account_id>`.
- Clear assigned-account command: `/clear_engagement_account <community_id>`.
- Inline community controls for rate limits, quiet hours, and account assignment.

### Missing Cross-Cutting UX

- Operator-intention navigation for Today, Communities, Topics, Voice rules, Limits/accounts, and
  Advanced.
- Readiness summaries that collapse target permissions, community settings, membership, candidate
  status, expiry, and rate limits into one operator-facing state.
- Progressive disclosure so cards show only the next safe actions by default.
- Human labels for backend fields, especially target permissions and community settings.
- Conversation-state editing for long prompt, topic guidance, style rule, and reply edits.
- Save/cancel confirmation buttons for long edits.
- Admin permission boundary in the bot UI.
- Confirmation flows for risky admin mutations, including prompt activation, posting permission
  changes, target approval, and account assignment.

### Recommended Next Menu Slice

The next implementation slice should prioritize:

- Add `Today`, `Review replies`, `Approved to send`, `Communities`, `Topics`, and `Recent actions`
  entries to `/engagement`.
- Add `Communities`, `Topics`, `Voice rules`, `Limits and accounts`, and `Advanced` entries to
  `/engagement_admin`.
- Add readiness summaries to community and candidate cards before adding more low-level controls.
- Expand target cards with resolve, reject, archive, permission toggles, target join, and target
  detect controls, but label them as watch/draft/post readiness where possible.

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
