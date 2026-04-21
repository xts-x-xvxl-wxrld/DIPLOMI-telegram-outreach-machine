# Bot Spec

## Purpose

The Telegram bot is the MVP operator UI.

It lets the operator import example Telegram communities as seed groups, resolve those examples,
snapshot metadata and visible members for the resolved seed communities, inspect job status, and
start monitoring approved communities.
The operator can also send one public Telegram username or link as plain text; the bot asks the API
to classify it as a channel, group, user, or bot.

The bot talks only to the backend API over HTTP. It never imports backend internals and never talks
directly to Redis, workers, Postgres, web-search providers, Telethon, or OpenAI.

The top-level operator cockpit is specified in `wiki/spec/bot-operator-cockpit.md`. That cockpit
replaces the old persistent reply-keyboard menu with inline navigation while preserving slash
commands as durable shortcuts.

## MVP Commands

```text
/start
/seeds
/seed <seed_group_id>
/channels <seed_group_id>
/resolveseeds <seed_group_id>
/candidates <seed_group_id>
/community <community_id>
/snapshot <community_id>
/members <community_id>
/exportmembers <community_id>
/entity <intake_id>
/whoami
/approve <community_id>
/reject <community_id>
/job <job_id>
/accounts
```

Engagement commands are optional and operator-controlled:

```text
/engagement
/engagement_admin
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
/engagement_prompts
/engagement_prompt <profile_id>
/engagement_prompt_versions <profile_id>
/engagement_prompt_preview <profile_id>
/activate_engagement_prompt <profile_id>
/duplicate_engagement_prompt <profile_id> <new_name>
/edit_engagement_prompt <profile_id> <field>
/rollback_engagement_prompt <profile_id> <version_number>
/engagement_style [scope] [scope_id]
/engagement_style_rule <rule_id>
/create_style_rule <scope> <scope_id_or_dash> | <name> | <priority> | <rule_text>
/edit_style_rule <rule_id>
/toggle_style_rule <rule_id> <on|off>
/engagement_topics
/engagement_topic <topic_id>
/create_engagement_topic <name> | <guidance> | <comma_keywords>
/toggle_engagement_topic <topic_id> <on|off>
/topic_good_reply <topic_id> | <example>
/topic_bad_reply <topic_id> | <example>
/topic_remove_example <topic_id> <good|bad> <index>
/topic_keywords <topic_id> <trigger|negative> <comma_keywords>
/edit_topic_guidance <topic_id>
/engagement_settings <community_id>
/set_engagement <community_id> <off|observe|suggest|ready>
/set_engagement_limits <community_id> <max_posts_per_day> <min_minutes_between_posts>
/set_engagement_quiet_hours <community_id> <HH:MM> <HH:MM>
/clear_engagement_quiet_hours <community_id>
/assign_engagement_account <community_id> <telegram_account_id>
/clear_engagement_account <community_id>
/join_community <community_id>
/detect_engagement <community_id> [window_minutes]
/engagement_candidates [status]
/engagement_candidate <candidate_id>
/edit_reply <candidate_id> | <new final reply>
/candidate_revisions <candidate_id>
/expire_candidate <candidate_id>
/retry_candidate <candidate_id>
/cancel_edit
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/send_reply <candidate_id>
/engagement_actions [community_id]
/engagement_rollout [window_days]
```

Optional/future commands:

```text
/brief <audience description>
/briefs
/expandseeds <seed_group_id> [brief_id]
```

## Command Behavior

### `/brief <audience description>`

Optional/future command. The active MVP should not require briefs for discovery.

Calls `POST /api/briefs` with:

```json
{
  "raw_input": "operator text",
  "auto_start_discovery": true
}
```

The API queues `brief.process`. The bot returns the brief ID and queued job ID.

### `/briefs`

Lists recent briefs and high-level candidate counts.

If the API does not yet expose a list endpoint, this command can wait until the optional brief layer
returns.

### `/seed <seed_group_id>`

Calls `GET /api/seed-groups/{seed_group_id}`.

The bot should show a compact seed-group detail message with:

- seed group name and ID
- seed, unresolved, resolved, and failed counts
- next actions for channels, candidates, and resolution
- inline buttons for open, resolve, channels, and candidates

### `/channels <seed_group_id>`

Calls `GET /api/seed-groups/{seed_group_id}/channels`.

The bot should page imported rows and show:

- title or raw seed value
- seed resolution status
- normalized Telegram link when available
- linked community command when resolved

### `/candidates <seed_group_id>`

Calls `GET /api/seed-groups/{seed_group_id}/candidates`.

The bot should show compact cards with:

- title
- username or Telegram link when available
- member count when available
- match reason
- seed group evidence summary when available
- source seed count and evidence count when available
- community ID for review commands
- inline approve, reject, and community-detail buttons

Candidate list paging should stay within Telegram-native controls instead of requiring manual offset
typing.

### `/community <community_id>`

Calls:

- `GET /api/communities/{community_id}`
- `GET /api/communities/{community_id}/snapshot-runs`

The bot should show:

- title, link, status, source, and match reason
- latest snapshot summary
- latest snapshot-run status
- latest analysis summary when available
- inline refresh, manual snapshot, member, and engagement-settings buttons

### `/snapshot <community_id>`

Calls `POST /api/communities/{community_id}/snapshot-jobs` with:

```json
{
  "window_days": 90
}
```

The bot reports the queued `community.snapshot` job and offers inline buttons for job refresh and
community detail.

### `/members <community_id>`

Calls `GET /api/communities/{community_id}/members`.

The bot should show a paged list of snapshotted visible members with only:

- Telegram user ID
- public username when present
- first name when present
- membership status
- activity status
- first seen, last updated, and last active timestamps

The bot must not show phone numbers, internal user IDs, event counts as rankings, or person-level
scores.

### `/exportmembers <community_id>`

Calls `GET /api/communities/{community_id}/members` in pages and sends a CSV document through
Telegram.

CSV columns:

- `tg_user_id`
- `username`
- `first_name`
- `membership_status`
- `activity_status`
- `first_seen_at`
- `last_updated_at`
- `last_active_at`

### `/approve <community_id>`

Calls `POST /api/communities/{community_id}/review` with:

```json
{
  "decision": "approve",
  "store_messages": false
}
```

For MVP, approving a community moves it directly to `monitoring` and queues an initial snapshot.

### `/reject <community_id>`

Calls `POST /api/communities/{community_id}/review` with:

```json
{
  "decision": "reject",
  "store_messages": false
}
```

### CSV seed upload

When the operator uploads a `.csv` document, the bot downloads it and calls
`POST /api/seed-imports/csv`.

Required CSV columns:

- `group_name`
- `channel`

Optional CSV columns:

- `title`
- `notes`

Operators may use `scripts/make_seed_csv.py` to turn a plain list of public Telegram usernames or
links into this CSV shape before uploading the document to the bot.

The bot reports imported rows, updated rows, affected seed group IDs, and skipped row errors.

### Direct handle intake

When the operator sends plain text matching a public Telegram username or public `t.me` link, such
as `@example` or `https://t.me/example`, the bot calls `POST /api/telegram-entities`.

The bot reports the queued `telegram_entity.resolve` job. The worker classifies the target with
Telethon and saves channels/groups to `communities` and users/bots to `users`. Private invite links
are rejected, and no phone numbers or person-level scores are stored.

### `/entity <intake_id>`

Calls `GET /api/telegram-entities/{intake_id}` and shows the latest classification status plus the
linked community command or user row ID when resolved.

### `/seeds`

Calls `GET /api/seed-groups` and displays seed group names, IDs, unresolved/resolved/failed seed
counts.

The bot should send an overview message plus compact group cards with inline actions.

### `/resolveseeds <seed_group_id>`

Calls `POST /api/seed-groups/{seed_group_id}/resolve-jobs`.

The bot reports the queued `seed.resolve` job ID. Resolution links imported public Telegram seeds to
candidate `communities` rows and queues initial snapshots for resolved communities.

### `/expandseeds <seed_group_id> [brief_id]`

Optional/future command. The active bare seed-import workflow does not expose expansion in the bot.
When re-enabled, it calls `POST /api/seed-groups/{seed_group_id}/expansion-jobs`.

Expansion can only start from seed rows already resolved to `communities`. The command expands the
seed batch itself, preserving the imported group as the operator-facing context, rather than starting
generic expansion from arbitrary saved community IDs.

`brief_id` is optional future context when expansion returns.

### `/job <job_id>`

Calls `GET /api/jobs/{job_id}` and displays status, timestamps, and a short error if present.

Job messages should include an inline refresh action.

### `/accounts`

Calls `GET /api/debug/accounts` and displays account pool health with masked phone numbers only.

### `/whoami`

Returns the sender's numeric Telegram user ID and public username when available. This command is
available even when `TELEGRAM_ALLOWED_USER_IDS` is configured and the sender is not yet allowed, so a
new human researcher can message the bot and send the ID to the operator.

## Engagement Controls

Engagement is an optional bot surface for the module in `wiki/spec/engagement.md`. It must keep
approval and sending separate.

The expanded bot-specific control contract for engagement targets, prompt profiles, style rules,
candidate editing, and admin workflows lives in `wiki/spec/bot-engagement-controls.md`. This section
keeps the core command behavior visible in the main bot spec.

### `/engagement`

Shows a compact engagement cockpit with counts for replies needing review, approved replies waiting
to send, failed candidates needing attention, and active topics. It offers intention-first inline
buttons for today, review replies, approved-to-send replies, communities, topics, recent actions,
and engagement admin. When the bot can determine locally that the caller is not an engagement
admin, it should hide the `Admin` button while keeping the daily review buttons available.

### `/engagement_admin`

Shows the admin-only configuration entrypoint for communities, topics, voice rules,
limits/accounts, and advanced prompt/audit controls. This surface stays separate from daily
candidate review. The bot may enforce this locally with a transitional `TELEGRAM_ADMIN_USER_IDS`
allowlist when no backend capability endpoint exists yet, but backend authorization remains
authoritative.

### `/engagement_targets [status]`

Lists manual engagement targets and their approval/posting permissions, optionally filtered by
target status. Target cards start with a human-readable readiness summary before raw target IDs and
permission fields, and expose target-scoped open, resolve, reject, archive, permission, join, and
detect controls.

### `/engagement_target <target_id>`

Shows one engagement target card with submitted reference, resolved community, status, permissions,
notes or last error when present, and the next safe target actions.

### `/add_engagement_target <telegram_link_or_username_or_community_id>`

Calls the engagement target intake API. This must not create seed rows.

### `/resolve_engagement_target <target_id>`

Queues `engagement_target.resolve` through the target-scoped engagement API. This must not call seed
resolution APIs or create seed rows.

### `/approve_engagement_target <target_id>`

Approves a resolved engagement target and enables join/detect/post permissions for the target. The
bot shows the current permission state before mutation and the resulting state after the API
returns. The worker still enforces settings and target gates before any outbound work.

### `/reject_engagement_target <target_id>`

Rejects an engagement target through the API. Rejection forces join, detect, and post permissions
off.

### `/archive_engagement_target <target_id>`

Archives an engagement target through the API. Archiving forces join, detect, and post permissions
off.

### `/target_permission <target_id> <join|detect|post> <on|off>`

Toggles one target permission through the engagement target API and displays before/after target
permissions. `detect` is labeled to operators as watching/drafting, while `post` remains reviewed
public posting only.

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

### `/create_engagement_topic <name> | <guidance> | <comma_keywords>`

Creates a topic through `POST /api/engagement/topics`.

The first bot implementation uses pipe-separated command text instead of a multi-step form.
Validation remains owned by the API and engagement service.

### `/toggle_engagement_topic <topic_id> <on|off>`

Calls `PATCH /api/engagement/topics/{topic_id}` with only the `active` field.

### `/topic_good_reply <topic_id> | <example>`

Adds a positive reply example to a topic through the topic examples API.

### `/topic_bad_reply <topic_id> | <example>`

Adds a negative reply example to a topic. Bad examples are avoid-this guidance, not templates.

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

Reads the current community settings, updates the assigned engagement account, and renders the
result using the account ID plus a masked label from `GET /api/debug/accounts` when available. The
API remains the source of truth for wrong-pool and invalid-account rejection.

### `/clear_engagement_account <community_id>`

Clears the assigned engagement account while preserving the rest of the current settings payload.

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

The message must remain aggregate-only. It may show counts and approval rates, but it must not show
candidate IDs, source messages, sender identity, phone numbers, or person-level scores.

## Operator Access

The bot may be restricted with `TELEGRAM_ALLOWED_USER_IDS`, a comma- or whitespace-separated list of
numeric Telegram user IDs.

The engagement admin subset may be restricted further with `TELEGRAM_ADMIN_USER_IDS`, also parsed as
a comma- or whitespace-separated list of numeric Telegram user IDs. When that list is empty, the
bot preserves the older local behavior and does not distinguish engagement admins from other
allowlisted operators locally.

If the allowlist is empty, existing local/development behavior is preserved and any Telegram user who
can reach the bot can use it.

If the allowlist is set, only listed user IDs can use operator commands, reply keyboard actions,
inline callback actions, CSV uploads, or plain-text Telegram entity submission. Unauthorized message
senders receive their own Telegram user ID and instructions to ask the operator to add it. Unauthorized
callback users receive the same information as a Telegram alert.

If `TELEGRAM_ADMIN_USER_IDS` is set, non-admin operators may still use ordinary daily engagement
review controls, but the bot should hide or reject engagement-admin mutations such as prompt
profile edits, style-rule edits, target approval/permission changes, topic mutations, and advanced
community setting changes before calling protected API routes.

Telegram Premium status does not change this flow; Telegram still includes the same `from_user.id`
for bot messages and callbacks.

## Review Status Decision

MVP review behavior:

- `candidate` - discovered and awaiting review
- `monitoring` - approved and actively scheduled for snapshots or engagement monitoring
- `rejected` - operator rejected
- `dropped` - previously relevant but no longer accessible or intentionally removed
- `approved` - reserved for later workflows where approval and monitoring are separate

The current MVP bot uses approve-as-monitoring to keep the first workflow short.

## UX Rules

- Messages should be concise and operational.
- The top-level bot entry should expose an inline operator cockpit for the main actions.
- Candidate cards must not expose raw message history.
- Candidate cards should explain graph evidence, such as linked discussion, forwarded source,
  Telegram link, or repeated discovery from multiple seeds.
- The bot must never show person-level scores.
- Account phone numbers must be masked by the API before reaching the bot.
- Bot copy should describe communities, not outreach targets.
- Engagement controls must not combine approval and sending unless a later spec explicitly enables
  that workflow.
