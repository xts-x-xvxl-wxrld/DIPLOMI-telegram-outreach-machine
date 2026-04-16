# Seed CSV Helper Plan

## Goal

Make it easy for the operator to turn a quick list of Telegram usernames or public links into the
CSV format accepted by the Telegram bot.

## CSV Shape

The bot accepts a `.csv` document with:

- `group_name` - seed group name repeated on each row
- `channel` - public Telegram username or link
- `title` - optional operator label
- `notes` - optional operator notes

## Helper

Add `scripts/make_seed_csv.py`.

The helper:

- accepts seeds from positional arguments, a text file, or stdin
- validates public Telegram usernames and links using the same normalization as the importer
- rejects private invite links before a CSV is produced
- de-duplicates repeated usernames within one generated file
- writes bot-ready columns: `group_name,channel,title,notes`

## Bot Flow

For now, the bot imports seed groups through CSV document upload. Plain pasted username-list import
can be added later if it becomes a frequent operator action, but CSV keeps the API and bot contract
explicit.
