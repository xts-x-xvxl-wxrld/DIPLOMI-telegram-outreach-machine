# Agent Instructions — Telegram Community Discovery App

## Wiki protocol

This project has a persistent spec wiki at `wiki/`. Every agent session must follow this protocol:

**Before writing code:**
1. Read `wiki/index.md` — see all existing specs and plans.
2. Read the spec file for the module you are touching (see Module Map below).
3. Read or create a plan file under `wiki/plan/[feature-slug].md`.

**After writing code:**
1. Append to `wiki/log.md` using the format: `## [YYYY-MM-DD] <type> | <title>`
2. Update the spec if the design changed.
3. Update `wiki/index.md` if new files or modules were added.

## Module Map

| Module | Spec |
|---|---|
| Audience Brief | `wiki/spec/audience-brief.md` |
| Discovery Worker | `wiki/spec/discovery.md` |
| Expansion Worker | `wiki/spec/expansion.md` |
| Collection Worker | `wiki/spec/collection.md` |
| Analysis Worker | `wiki/spec/analysis.md` |
| Backend API | `wiki/spec/api.md` |
| Frontend | `wiki/spec/frontend.md` |
| Database | `wiki/spec/database.md` |
| Queue | `wiki/spec/queue.md` |

## Hard rules

- Never edit `wiki/app-high-level.md`.
- No business logic in the collection worker.
- No person-level scores — community analysis only.
- If a spec is missing, write it before writing code.
- If spec and code conflict, log and resolve it.
