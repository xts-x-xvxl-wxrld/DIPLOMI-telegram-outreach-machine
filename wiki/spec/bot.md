# Bot Spec

## Purpose

The Telegram bot is the MVP operator UI.

It lets the operator import example Telegram communities as seed groups, resolve those examples,
collect metadata and visible members for the resolved seed communities, inspect job status, and
start monitoring approved communities.
The operator can also send one public Telegram username or link as plain text; the bot asks the API
to classify it as a channel, group, user, or bot.

The bot talks only to the backend API over HTTP. It never imports backend internals and never talks
directly to Redis, workers, Postgres, web-search providers, Telethon, or OpenAI.

## MVP Commands

```text
/start
/seeds
/seed <seed_group_id>
/channels <seed_group_id>
/resolveseeds <seed_group_id>
/candidates <seed_group_id>
/community <community_id>
/collect <community_id>
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
/engagement_topics
/create_engagement_topic <name> | <guidance> | <comma_keywords>
/toggle_engagement_topic <topic_id> <on|off>
/engagement_settings <community_id>
/set_engagement <community_id> <off|observe|suggest|ready>
/join_community <community_id>
/detect_engagement <community_id> [window_minutes]
/engagement_candidates [status]
/approve_reply <candidate_id>
/reject_reply <candidate_id>
/send_reply <candidate_id>
/engagement_actions [community_id]
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
- `GET /api/communities/{community_id}/collection-runs`

The bot should show:

- title, link, status, source, and match reason
- latest snapshot summary
- latest collection-run status
- latest analysis summary when available
- inline refresh and manual collection buttons

### `/collect <community_id>`

Calls `POST /api/communities/{community_id}/collection-jobs` with:

```json
{
  "window_days": 90
}
```

The bot reports the queued `collection.run` job and offers inline buttons for job refresh and
community detail.

### `/members <community_id>`

Calls `GET /api/communities/{community_id}/members`.

The bot should show a paged list of visible collected members with only:

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

For MVP, approving a community moves it directly to `monitoring` and queues initial collection.

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
candidate `communities` rows and queues initial collection for resolved communities.

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

### `/engagement`

Shows a compact engagement cockpit with counts for pending replies, approved replies, failed
candidates, and active topics. It should offer inline buttons for topics, candidates, settings entry
points when opened from a community, and recent actions.

### `/engagement_topics`

Calls `GET /api/engagement/topics` and lists configured topics with active state, trigger keyword
preview, and concise guidance text.

### `/create_engagement_topic <name> | <guidance> | <comma_keywords>`

Creates a topic through `POST /api/engagement/topics`.

The first bot implementation uses pipe-separated command text instead of a multi-step form.
Validation remains owned by the API and engagement service.

### `/toggle_engagement_topic <topic_id> <on|off>`

Calls `PATCH /api/engagement/topics/{topic_id}` with only the `active` field.

### `/engagement_settings <community_id>`

Calls `GET /api/communities/{community_id}/engagement-settings`.

The bot should show mode, join/post flags, reply-only and approval requirements, rate limits, quiet
hours when configured, and assigned account ID when configured.

### `/set_engagement <community_id> <off|observe|suggest|ready>`

Applies a safe settings preset through `PUT /api/communities/{community_id}/engagement-settings`.

Preset meanings:

- `off` - disabled, no joins, no posts.
- `observe` - detect-only posture, no joins or posts.
- `suggest` - draft candidates for review, no joins or posts.
- `ready` - allow joins and approved public replies while preserving `reply_only=true` and
  `require_approval=true`.

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
suggested or final reply text, risk notes, and status. The bot must not show sender identity.

### `/approve_reply <candidate_id>`

Approves a candidate through `POST /api/engagement/candidates/{candidate_id}/approve`. The returned
card may offer `Queue send`, but approval itself must not enqueue sending.

### `/reject_reply <candidate_id>`

Rejects a candidate through `POST /api/engagement/candidates/{candidate_id}/reject`.

### `/send_reply <candidate_id>`

Queues `engagement.send` through `POST /api/engagement/candidates/{candidate_id}/send-jobs`.

Only approved candidates should expose this command or inline button. The API must still reject
unapproved candidates.

### `/engagement_actions [community_id]`

Calls `GET /api/engagement/actions` and shows recent join/reply audit rows. Community filtering is
optional in the command and should be passed to the API when provided.

## Operator Access

The bot may be restricted with `TELEGRAM_ALLOWED_USER_IDS`, a comma- or whitespace-separated list of
numeric Telegram user IDs.

If the allowlist is empty, existing local/development behavior is preserved and any Telegram user who
can reach the bot can use it.

If the allowlist is set, only listed user IDs can use operator commands, reply keyboard actions,
inline callback actions, CSV uploads, or plain-text Telegram entity submission. Unauthorized message
senders receive their own Telegram user ID and instructions to ask the operator to add it. Unauthorized
callback users receive the same information as a Telegram alert.

Telegram Premium status does not change this flow; Telegram still includes the same `from_user.id`
for bot messages and callbacks.

## Review Status Decision

MVP review behavior:

- `candidate` - discovered and awaiting review
- `monitoring` - approved and actively scheduled for collection
- `rejected` - operator rejected
- `dropped` - previously relevant but no longer collectable or intentionally removed
- `approved` - reserved for later workflows where approval and monitoring are separate

The current MVP bot uses approve-as-monitoring to keep the first workflow short.

## UX Rules

- Messages should be concise and operational.
- The top-level bot entry should expose a persistent Telegram reply keyboard for the main actions.
- Candidate cards must not expose raw message history.
- Candidate cards should explain graph evidence, such as linked discussion, forwarded source,
  Telegram link, or repeated discovery from multiple seeds.
- The bot must never show person-level scores.
- Account phone numbers must be masked by the API before reaching the bot.
- Bot copy should describe communities, not outreach targets.
- Engagement controls must not combine approval and sending unless a later spec explicitly enables
  that workflow.
