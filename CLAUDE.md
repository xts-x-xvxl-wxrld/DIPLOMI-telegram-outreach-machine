# Telegram Community Discovery App

This project uses a wiki at `wiki/` as the source of truth for all specs, plans, and change history.

## Before Writing Any Code

1. Read `wiki/index.md` to see what specs and plans exist.
2. Read only the spec file or spec shard for the module you are working on.
3. If no plan file exists for your task, write one under `wiki/plan/`.
4. Use `rg` to locate code symbols before opening large files.

## After Writing Or Changing Code

1. Append to `wiki/log.md`.
2. Update the relevant spec if the design changed.
3. Update `wiki/index.md` if new files, specs, shards, modules, or entrypoints were created.

## Context Budget

- Do not read `wiki/llm-wiki.md`, `wiki/llm-wiki-md.txt`, all of `wiki/log.md`, `.claude/`, pytest temp directories, env files, caches, sessions, or data volumes during normal coding.
- Keep top-level specs under 300 lines and plans under 200 lines. Split larger material into focused shards and link them from the parent spec.
- Keep production files under 800 lines and tests under 1,000 lines when practical. If a touched file is already over the cap, extract a cohesive module before adding feature-sized behavior.

## Key Rules

- `wiki/app-high-level.md` is the immutable product brief; never edit it.
- No business logic in the collection worker.
- No person-level scores or lead lists; community-level analysis only.
- Write the spec before writing code for any new module.

## Stack

- **Manual seed import** - operator-curated seed batches for reliable initial discovery
- **Public web search adapters** - optional t.me username discovery
- **Telethon** - Telegram client, collection, seed inspection, and graph expansion
- **TGCrawl** - channel-graph expansion reference
- **TeleCatch** - collection UI/API reference
