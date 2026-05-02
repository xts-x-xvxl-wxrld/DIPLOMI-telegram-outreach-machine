# Bot Engagement Commands

Engagement review, admin, prompt, topic, style, settings, join, detect, send, action, and rollout command contracts.

## Engagement Controls

Engagement is an optional bot surface for the module in `wiki/spec/engagement.md`. It must keep
approval and sending separate.

The expanded bot-specific control contract for engagement targets, prompt profiles, style rules,
candidate editing, and admin workflows lives in `wiki/spec/bot-engagement-controls.md`. This section
keeps the core command behavior visible in the main bot spec.

### `/engagement`

Shows a compact engagement cockpit with counts for replies needing review, approved replies waiting
to send, failed candidates needing attention, and active topics. It offers intention-first inline
buttons for today, review replies, approved-to-send replies, communities, topics, settings lookup,
recent actions, and engagement admin. When the bot can determine locally that the caller is not an
engagement admin, or when the backend capability endpoint says the caller is not an engagement
admin, it should hide the `Admin` button while keeping the daily review buttons available.

### `/engagement_admin`

Shows the admin-only configuration entrypoint for communities, topics, voice rules,
limits/accounts, and advanced prompt/audit controls. This surface stays separate from daily
candidate review. The bot may enforce this locally with a transitional `TELEGRAM_ADMIN_USER_IDS`
allowlist when backend capabilities are unconfigured or unavailable, but backend authorization
remains authoritative.

### `/engagement_targets [status]`

Lists manual engagement targets and their approval/posting permissions, optionally filtered by
target status. Default target cards start with a human-readable readiness summary and
operator-facing permission labels before raw target IDs. Opened detail cards remain audit-friendly
and expose target IDs, raw status, raw permissions, and diagnostic fields. Target cards expose
target-scoped open, settings, resolve, reject, archive, permission, join, and detect controls when
those actions apply.

### `/engagement_target <target_id>`

Shows one engagement target card with submitted reference, resolved community, status, permissions,
notes or last error when present, and the next safe target actions. Admins can start a guided
button-led target-note edit from this card; saving notes uses the engagement target API only.

### `/add_engagement_target <telegram_link_or_username_or_community_id>`

Calls the engagement target intake API. This must not create seed rows.

### `/resolve_engagement_target <target_id>`

Queues `engagement_target.resolve` through the target-scoped engagement API. This must not call seed
resolution APIs or create seed rows.

### `/approve_engagement_target <target_id>`

Shows a confirmation card for approving a resolved engagement target and enabling
join/detect/post permissions. The bot shows before/after permission state and calls the target
update API only after the admin confirms. The worker still enforces settings and target gates
before any outbound work.

### `/reject_engagement_target <target_id>`

Rejects an engagement target through the API. Rejection forces join, detect, and post permissions
off.

### `/archive_engagement_target <target_id>`

Archives an engagement target through the API. Archiving forces join, detect, and post permissions
off.

### `/target_permission <target_id> <join|detect|post> <on|off>`

Toggles one target permission through the engagement target API and displays before/after target
permissions. `detect` is labeled to operators as watching/drafting, while `post` remains reviewed
public posting only. Posting-permission changes show a confirmation card before saving; join and
detect permission changes remain direct.

### `/target_join <target_id>`

Queues a target-scoped join job. The API maps the target to its resolved community and workers still
enforce approval and `allow_join`.

### `/target_detect <target_id> [window_minutes]`

Queues a target-scoped engagement detection job. The API maps the target to its resolved community
and workers still enforce approval and `allow_detect`.

### `/engagement_prompts`

Lists prompt profile cards with active state, model parameters, current version, and preview command.

### `/engagement_prompt <profile_id>`

Shows one prompt profile detail card with active state, current version, model parameters, output
schema, capped prompt previews, and admin actions for preview, versions, edit, duplicate,
activation, and rollback when applicable.

### `/engagement_prompt_versions <profile_id>`

Lists immutable prompt profile versions newest first. Version cards may offer rollback entrypoints,
but rollback must show a confirmation card before calling the API.

### `/engagement_prompt_preview <profile_id>`

Renders a prompt profile preview through the API. The bot displays rendered text only; the preview
endpoint does not call OpenAI.

### `/create_engagement_prompt <name> | <description_or_dash> | <model> | <temperature> | <max_output_tokens> | <system_prompt> | <user_prompt_template>`

Creates an inactive prompt profile through `POST /api/engagement/prompt-profiles`.

The prompt profile list also exposes an inline `Create profile` button that starts a guided
pipe-delimited input flow. Both paths reject unsupported prompt-template variables, including
sender identity variables, before the API call when possible.

### `/activate_engagement_prompt <profile_id>`

Shows an explicit activation confirmation card before activating the profile through the API.
Activation is admin-only and never happens as part of previewing or editing.

### `/duplicate_engagement_prompt <profile_id> <new_name>`

Duplicates an existing prompt profile through the prompt profile API. The new profile is returned as
a normal prompt profile card and remains subject to backend validation and activation rules.

### `/edit_engagement_prompt <profile_id> <field>`

Starts the shared guided config-edit flow for an allowlisted prompt profile field. Long prompt text
is collected as the next Telegram message, previewed, and saved only after confirmation.
Unsupported prompt variables, including sender identity variables, are rejected before the API call
when possible.

### `/rollback_engagement_prompt <profile_id> <version_number>`

Shows an explicit rollback confirmation card, then calls the rollback API to restore the selected
immutable version as the profile's current editable state.

### `/engagement_style [scope] [scope_id]`

Lists configured style rules with optional `global`, `account`, `community`, or `topic` scope
filters. Cards show scope, active state, priority, capped rule text, and inline open/edit/toggle
controls.

### `/engagement_style_rule <rule_id>`

Calls `GET /api/engagement/style-rules/{rule_id}` and shows one style-rule detail card.

### `/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>`

Creates a style rule through `POST /api/engagement/style-rules`.
The inline style-rule `Create` button starts a guided compact-input flow that previews and confirms
before creating the rule.

### `/edit_style_rule <rule_id>`

Starts the shared guided config-edit flow for the style rule text.

### `/toggle_style_rule <rule_id> <on|off>`

Calls `PATCH /api/engagement/style-rules/{rule_id}` with only the `active` field.

### `/engagement_topics`

Calls `GET /api/engagement/topics` and lists configured topics with active state, trigger keyword
preview, concise guidance text, and clearly separated good vs. bad examples.

### `/engagement_topic <topic_id>`

Calls `GET /api/engagement/topics/{topic_id}` and shows one topic detail card with guidance,
trigger and negative keywords, labeled good examples, labeled bad examples that are marked as
avoid-copy guidance, and inline edit/remove controls.

### `/create_engagement_topic [legacy_inline_payload]`

Creates a topic through `POST /api/engagement/topics`.

Calling `/create_engagement_topic` with no arguments starts a guided one-question-at-a-time bot
flow that collects topic name, reply guidance, trigger keywords, optional description, and optional
negative keywords before showing a confirmation step.

For backward compatibility, the bot may still accept the legacy pipe-delimited inline payload when
arguments are supplied directly. Validation remains owned by the API and engagement service.

### `/toggle_engagement_topic <topic_id> <on|off>`

Calls `PATCH /api/engagement/topics/{topic_id}` with only the `active` field.

### `/topic_good_reply <topic_id> | <example>`

Adds a positive reply example to a topic through the topic examples API.

### `/topic_bad_reply <topic_id> | <example>`

Adds a negative reply example to a topic. Bad examples are avoid-this guidance, not templates.
Topic detail cards also expose button-led good/bad example entrypoints that collect the next
message, show a preview, and save through the same topic examples API.

### `/topic_remove_example <topic_id> <good|bad> <index>`

Removes one topic example. Bot-facing indexes are one-based for operator readability.

### `/topic_keywords <topic_id> <trigger|negative> <comma_keywords>`

Replaces the selected keyword list through `PATCH /api/engagement/topics/{topic_id}`.

### `/edit_topic_guidance <topic_id>`

Starts the shared guided config-edit flow for topic guidance.

### `/engagement_settings <community_id>`

Calls `GET /api/communities/{community_id}/engagement-settings`.

The bot should show mode, join/post flags, reply-only and approval requirements, rate limits, quiet
hours when configured, and the assigned engagement account as an ID or masked non-secret label.
The daily engagement menu also exposes a Settings lookup button that lists approved resolved
engagement targets and opens this same settings card without requiring the operator to type a
community ID.
Admins can start guided button-led edits for posting limits, quiet-hour start/end, and assigned
account from the settings card. These guided saves preserve `reply_only=true` and
`require_approval=true` and rely on the API for bounds and engagement-account pool validation.

### `/set_engagement <community_id> <off|observe|suggest|ready>`

Applies a safe settings preset through `PUT /api/communities/{community_id}/engagement-settings`.

Preset meanings:

- `off` - disabled, no joins, no posts.
- `observe` - detect-only posture, no joins or posts.
- `suggest` - draft candidates for review, no joins or posts.
- `ready` - allow joins and approved public replies while preserving `reply_only=true` and
  `require_approval=true`.

### `/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>`

Reads the current community settings, replaces the two rate-limit fields, preserves
`reply_only=true` and `require_approval=true`, and updates the full settings payload through
`PUT /api/communities/{community_id}/engagement-settings`.

### `/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>`

Reads the current community settings, validates simple `HH:MM` input in the bot, and updates quiet
hours through `PUT /api/communities/{community_id}/engagement-settings`.

### `/clear_engagement_quiet_hours <community_id>`

Clears both quiet-hour fields while preserving the rest of the current settings payload.

### `/assign_engagement_account <community_id> <telegram_account_id>`

Reads the current community settings and shows a before/after account assignment confirmation using
the account ID plus a masked label from `GET /api/debug/accounts` when available. The settings API
is called only after the admin confirms. The API remains the source of truth for wrong-pool and
invalid-account rejection.

### `/clear_engagement_account <community_id>`

Shows a before/after confirmation for clearing the assigned engagement account, then clears it after
the admin confirms while preserving the rest of the current settings payload.

### `/join_community <community_id>`

Queues `community.join` through `POST /api/communities/{community_id}/join-jobs`.

The bot must show the queued job ID and a refresh button. The API and worker still own all preflight
checks and Telethon behavior.

### `/detect_engagement <community_id> [window_minutes]`

Queues manual `engagement.detect` through
`POST /api/communities/{community_id}/engagement-detect-jobs`.

### `/engagement_candidates [status]`

Lists engagement candidates. Default status is `needs_review`; supported operator filters include
`approved`, `failed`, `sent`, and `rejected` when the API supports them.

Candidate cards should show community title, topic, capped source excerpt, detected reason,
suggested and edited final reply text, prompt profile/version summary when available, risk notes,
status, and a send-readiness summary. The bot must not show sender identity. Cards should list only
state-relevant primary action hints, such as approve/reject for `needs_review` and send for
`approved`.

### `/engagement_candidate <candidate_id>`

Calls `GET /api/engagement/candidates/{candidate_id}` and shows one full candidate detail card with
capped source excerpt, detected reason, suggested reply, current final reply, prompt profile/version
summary, risk notes, status, expiry, and state-aware controls. The card must not show sender
identity, phone numbers, private account metadata, or person-level scores.

### `/edit_reply <candidate_id> | <new final reply>`

Edits the candidate's final reply through the API. The edit creates a candidate revision and uses
the same safety and length validation as generated replies.

Operators may also start a guided edit with only:

```text
/edit_reply <candidate_id>
```

In that mode, the bot stores a pending edit for the caller's Telegram user ID, accepts the next text
message as the proposed final reply, shows a preview, and saves or cancels through inline controls.
Pending edits are in-process, expire after a short timeout, and are not shared between operators.

### `/candidate_revisions <candidate_id>`

Calls `GET /api/engagement/candidates/{candidate_id}/revisions` and shows immutable manual reply
revision history with revision number, edited-by label, optional edit reason, timestamp, and capped
reply text.

### `/expire_candidate <candidate_id>`

Calls `POST /api/engagement/candidates/{candidate_id}/expire` to explicitly remove a reviewable or
approved candidate from active review when the operator decides it is stale. Sent, rejected, and
already expired candidates remain read-only.

### `/retry_candidate <candidate_id>`

Calls `POST /api/engagement/candidates/{candidate_id}/retry` to reopen a failed candidate for review
when the backend permits the transition. Retry does not send anything; it only returns the candidate
to review.

### `/cancel_edit`

Cancels the caller's pending guided config edit, if one exists.

### `/approve_reply <candidate_id>`

Approves a candidate through `POST /api/engagement/candidates/{candidate_id}/approve`. If the
candidate has an edited final reply, approval uses that text; otherwise it falls back to the
suggested reply. The returned card may offer `Queue send`, but approval itself must not enqueue
sending.

### `/reject_reply <candidate_id>`

Rejects a candidate through `POST /api/engagement/candidates/{candidate_id}/reject`.

### `/send_reply <candidate_id>`

Queues `engagement.send` through `POST /api/engagement/candidates/{candidate_id}/send-jobs`.

Only approved candidates should expose this command or inline button. The API must still reject
unapproved candidates.

### `/engagement_actions [community_id]`

Calls `GET /api/engagement/actions` and shows recent join/reply audit rows. Community filtering is
optional in the command and should be passed to the API when provided.

### `/engagement_rollout [window_days]`

Calls `GET /api/engagement/semantic-rollout` and shows aggregate semantic-selector rollout
outcomes by similarity band for threshold tuning. The command defaults to a 14-day window and
accepts a positive day count.

The same summary should also be reachable from the engagement `Drafting/audit` surface through a
`Semantic rollout` button with preset window shortcuts. The slash command remains the manual
fallback.

The message must remain aggregate-only. It may show counts and approval rates, but it must not show
candidate IDs, source messages, sender identity, phone numbers, or person-level scores.
