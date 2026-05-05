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
flow that collects topic name, conversation target, optional trigger keywords, reply guidance,
optional voice guidance, good examples, bad examples, and optional avoid rules before showing a
confirmation step. Negative keywords remain editable from the topic detail surfaces and
`/topic_keywords`.

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

## Historical Compat Note

The old slash-command layer for engagement settings, join/detect triggers,
action-history review, and candidate review is no longer the intended contract.

Current operator/admin behavior:

- Send-safety and manual controls are callback-first under `eng:set:*`,
  `eng:join:*`, `eng:detect:*`, and `eng:actions:*`.
- The settings card still shows mode, pacing, quiet hours, and assigned account,
  but edits now start from buttons instead of slash-command mirrors.
- Join and manual detect still queue the same backend jobs; the operator reaches
  them from button-led target/settings surfaces rather than typed commands.
- Action-history paging remains under `eng:actions:*`.
- Legacy candidate-review slash commands are removed from the active bot-side
  contract and should not be reintroduced in compat docs.

Top-level bot entrypoints such as `/engagement` and `/engagement_admin` may
still hand operators into the task-first or admin flows, but the detailed manual
control layer should be documented as callback-driven.
