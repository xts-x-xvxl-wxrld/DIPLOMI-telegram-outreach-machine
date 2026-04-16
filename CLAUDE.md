# Telegram Community Discovery App

This project uses a wiki at `wiki/` as the source of truth for all specs, plans, and change history.

## Before writing any code

1. Run `/wiki` (or read `wiki/llm-wiki.md`) to load the full protocol.
2. Read `wiki/index.md` to see what specs and plans exist.
3. Read the spec for the module you are working on.
4. If no plan file exists for your task, write one under `wiki/plan/`.

## After writing or changing code

1. Append to `wiki/log.md`.
2. Update the relevant spec if the design changed.
3. Update `wiki/index.md` if new files or modules were created.

## Key rules

- `wiki/app-high-level.md` is the immutable product brief — never edit it.
- No business logic in the collection worker.
- No person-level scores or lead lists — community-level analysis only.
- Write the spec before writing code for any new module.

## Stack

- **Manual seed import** — operator-curated seed batches for reliable initial discovery
- **Public web search adapters** — optional t.me username discovery
- **Telethon** — Telegram client, collection, seed inspection, and graph expansion
- **TGCrawl** — channel-graph expansion reference
- **TeleCatch** — collection UI/API reference
