# Bot Seed And Community Commands

Detailed seed group, candidate, community, snapshot, member, review, CSV, and entity intake command contracts.

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
