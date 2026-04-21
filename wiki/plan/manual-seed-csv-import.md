# Manual Seed CSV Import Plan

## Goal

Let the operator upload a structured CSV file to the Telegram bot to create named seed groups of
Telegram channels or public groups.

Manual seed groups are the practical MVP path when broad automated group/channel search is too
limited or noisy.

## CSV Contract

Required columns:

- `group_name` - operator-facing seed group name
- `channel` - Telegram username or link, such as `@example`, `https://t.me/example`, or `t.me/s/example`

Optional columns:

- `title` - operator-provided label before Telethon resolution
- `notes` - operator notes about why the seed belongs in the group

Accepted aliases:

- group: `group`, `seed_group`, `seed_group_name`, `name`
- channel: `username`, `link`, `url`, `telegram`, `telegram_link`

Seed import normalizes accepted public Telegram usernames and public Telegram links to:

- `raw_value` - trimmed original CSV value
- `normalized_key` - `username:<casefolded_username>`
- `username` - parsed public Telegram username
- `telegram_url` - `https://t.me/<username>`

## Data Model

Add:

- `seed_groups` for named operator seed sets
- `seed_channels` for unresolved or resolved seed links within a group

`seed_channels.community_id` is nullable and links to `communities.id` after a resolver/expansion
worker maps the seed link to a Telegram ID.

Seed resolution is now a separate `seed.resolve` job rather than hidden inside expansion. Expansion
only starts from seed rows already linked to `communities`.

## API

- `POST /api/seed-imports/csv` imports CSV text from the bot.
- `GET /api/seed-groups` lists seed groups.
- `GET /api/seed-groups/{seed_group_id}/channels` lists seeds in a group.
- `POST /api/seed-groups/{seed_group_id}/expansion-jobs` starts expansion for resolved seeds in a group.

## Bot

- Uploading a `.csv` document imports seed groups.
- `/seeds` lists seed groups and IDs.
- `/expandseeds <seed_group_id>` starts expansion for resolved seeds when available.

## Helper

`scripts/make_seed_csv.py` can turn a simple list of public Telegram usernames or links into the
required CSV shape. This keeps the bot import path explicit while making operator data preparation
quick from pasted usernames.

## Non-Goals

- No retired external index dependency.
- No automatic joining of private communities.
- No raw message intake during import.
- No person-level scoring.
