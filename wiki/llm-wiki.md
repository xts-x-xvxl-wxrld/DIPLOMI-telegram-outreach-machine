# Project Wiki — Telegram Community Discovery App

This wiki is the single source of truth for the planning and implementation of this project. It is not a knowledge base about Telegram. It is a living spec system: LLMs write plans here, read them before touching code, record every meaningful change, and use it to stay consistent across sessions, agents, and providers.

**You (the LLM) own this wiki entirely.** The developer sources direction; you maintain all spec files, the index, and the log.


## Purpose

This wiki exists to solve a specific problem: LLM agents lose context between sessions. Without a persistent spec layer, every new session has to rediscover what was decided, what was built, and where to make the next change. This wiki eliminates that. Before writing any code, an agent reads the relevant spec. After making any change, it updates the log. Specs stay current because the agent updates them, not the developer.

The wiki covers this project only:

> A Telegram community discovery and monitoring app. Operators enter a target audience in plain language. The system converts that into a search brief, uses manual seeds and configured discovery adapters to find candidate channels and chats, uses Telethon and crawler logic to expand through seeds, collects public messages from approved communities, and summarizes community relevance. Centered on community intelligence — not direct outreach.


## Directory Layout

```
wiki/
  llm-wiki.md          ← this file (schema and instructions for the agent)
  app-high-level.md    ← immutable product brief (read-only, do not modify)
  index.md             ← catalog of all spec and plan files (agent maintains this)
  log.md               ← append-only change record (agent appends after every session)
  spec/
    audience-brief.md  ← Audience Brief module spec
    discovery.md       ← Discovery Worker spec
    expansion.md       ← Seed Expansion Worker (Telethon + crawler) spec
    collection.md      ← Collection Worker (Telethon / TeleCatch) spec
    analysis.md        ← Community Analysis Worker spec
    api.md             ← Backend API spec
    frontend.md        ← Frontend spec
    database.md        ← Database schema and storage spec
    queue.md           ← Queue / Scheduler spec
  plan/
    [feature-slug].md  ← one file per planned feature or implementation task
```

Spec files live under `spec/`. They describe the intended design of each module: responsibilities, interfaces, data shapes, key decisions, open questions.

Plan files live under `plan/`. They describe a specific implementation task: what to build, where in the codebase, step-by-step approach, acceptance criteria. One file per task or feature. Delete or archive when done.

`app-high-level.md` is immutable. It is the product brief. Read it; never edit it.


## Operations

### Before writing any code

1. Read `wiki/index.md` to orient yourself.
2. Find and read the spec file(s) for the module you are working on.
3. If a plan file exists for the task, read it. If not, write one under `wiki/plan/`.
4. Identify exact file paths and line numbers in the codebase where the work lands.
5. State your intended changes before making them.

### After writing or changing code

1. Append an entry to `wiki/log.md` (format below).
2. If the change affects a module's design, update the relevant spec file.
3. If a plan is complete, mark it done at the top and note the outcome.
4. If new modules, files, or interfaces were created, add them to `wiki/index.md`.

### Writing a spec file

Each spec file should cover:
- **Responsibility** — what this module does and does not do
- **Interfaces** — what it consumes and produces (API endpoints, queue messages, DB writes, etc.)
- **Key decisions** — why it is designed this way (e.g. "collection worker has no business logic — analysis is separate")
- **Code location** — which files and directories implement this module
- **Open questions** — unresolved design choices to revisit

### Writing a plan file

Each plan file (`wiki/plan/[feature-slug].md`) should cover:
- **Goal** — one sentence
- **Scope** — what is in and out of scope
- **Steps** — ordered list of implementation steps with file paths
- **Acceptance criteria** — how to know it is done
- **Status** — `in-progress` | `done` | `blocked`


## log.md Format

Entries are appended, never edited. Each entry starts with a consistent prefix so it is grep-parseable:

```
## [YYYY-MM-DD] <type> | <short title>

<type> is one of: spec | plan | code | refactor | fix | decision | question

Body: what changed, where (file paths), and why. Keep it short.
```

Example:
```
## [2026-04-14] code | Audience Brief — keyword extraction endpoint

Added POST /api/brief endpoint in backend/api/routes/brief.py.
Implemented keyword/phrase/language extraction via Claude API call.
Updated spec/audience-brief.md to reflect final request/response shape.
```


## index.md Format

The index is a flat catalog. The agent updates it whenever a spec or plan file is created or significantly changed.

```
# Wiki Index

## Spec files
- [Audience Brief](spec/audience-brief.md) — keyword extraction and search brief generation
- [Discovery](spec/discovery.md) — source-adapter discovery and candidate community ingestion
- [Expansion](spec/expansion.md) — Telethon seed inspection, graph expansion
- [Collection](spec/collection.md) — public message collection from approved communities
- [Analysis](spec/analysis.md) — community summarization and relevance scoring
- [API](spec/api.md) — backend REST API, endpoints, auth
- [Frontend](spec/frontend.md) — operator UI: brief input, review, watchlists, summaries
- [Database](spec/database.md) — schema: briefs, candidates, snapshots, watchlists, summaries
- [Queue](spec/queue.md) — async workers, scheduling, job states

## Plan files
- (none yet)
```


## Module Map

Quick reference for where each part of the app lives and which spec governs it:

| Module | Spec file | Codebase directory (to be confirmed) |
|---|---|---|
| Audience Brief | spec/audience-brief.md | `backend/brief/` |
| Discovery Worker | spec/discovery.md | `workers/discovery/` |
| Expansion Worker | spec/expansion.md | `workers/expansion/` |
| Collection Worker | spec/collection.md | `workers/collection/` |
| Analysis Worker | spec/analysis.md | `workers/analysis/` |
| Backend API | spec/api.md | `backend/api/` |
| Frontend | spec/frontend.md | `frontend/` |
| Database | spec/database.md | `backend/db/` |
| Queue / Scheduler | spec/queue.md | `workers/queue/` |

Update this table as the codebase structure is established.


## Rules for agents

- Never modify `app-high-level.md`.
- Never write business logic in the collection worker (see product brief).
- Never produce person-level scores or lead lists — analysis is community-level only.
- Always read the relevant spec before writing code for a module.
- Always append to `log.md` after any meaningful change.
- If a spec does not exist yet for a module you are about to build, write it first, then write the code.
- If you discover a conflict between a spec and the actual code, flag it in the log and update the spec to reflect the truth — or fix the code. Do not silently ignore the discrepancy.
- Keep spec files short and factual. They are not documentation for end users — they are working notes for agents.


## Bootstrapping

The wiki is currently empty (no spec files, no index, no log). The first agent session should:

1. Create `wiki/index.md` and `wiki/log.md` as empty scaffolds.
2. Pick the first module to implement (suggest starting with Database schema and Backend API skeleton).
3. Write the spec file for that module before touching code.
4. Proceed with implementation, updating the log and index as you go.
