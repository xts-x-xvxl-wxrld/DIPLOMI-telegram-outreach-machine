# Agent Instructions - Telegram Community Discovery App

## Wiki Protocol

This project has a persistent spec wiki at `wiki/`. Every agent session must follow this protocol:

**Before writing code:**
1. Read `wiki/index.md` - see all existing specs and plans.
2. Read the spec file or spec shard for the module you are touching (see Module Map below).
3. Read or create a plan file under `wiki/plan/[feature-slug].md`.

**After writing code:**
1. Append to `wiki/log.md` using the format: `## [YYYY-MM-DD] <type> | <title>`.
2. Update the spec if the design changed.
3. Update `wiki/index.md` if new files, specs, shards, modules, or entrypoints were added.

## Context Budget And Fragmentation Protocol

Agents must keep the wiki and codebase cheap to navigate.

**Before reading:**
- Do not read `wiki/llm-wiki.md`, `wiki/llm-wiki-md.txt`, or all of `wiki/log.md` during normal coding. Use `wiki/index.md`, targeted specs/plans, and `rg` searches.
- Read only the spec shard and code files that govern the current change. If a heading or symbol search can locate the needed section, read that section first.
- Treat `.claude/`, pytest temp directories, caches, sessions, data volumes, and env files as out of scope.

**When writing wiki files:**
- Keep top-level module specs as routing contracts: responsibility, invariants, interfaces, code map, and links to shards.
- Soft caps: top-level spec <= 300 lines, plan <= 200 lines, wiki index <= 150 lines. If a file would exceed the cap, create a focused shard such as `wiki/spec/engagement/topics.md` or split the plan into slice files.
- Move detail-heavy history, endpoint matrices, prompt contracts, and rollout notes into named shards. The parent spec should link to those shards and summarize only what agents need to decide where to work.
- Keep `wiki/log.md` append-only, but read recent entries with `rg "^## \\[" wiki/log.md` instead of loading the whole file unless history is the task.

**When writing code:**
- Soft cap production files at 800 lines and tests at 1,000 lines. If a touched file is already over the cap, avoid adding another feature-sized block to it; extract a cohesive module first or include extraction in the same slice.
- Split by operational boundary, not by arbitrary helpers: API resources, bot command groups, callback routers, formatting domains, service subdomains, worker orchestration, adapters, and pure utilities.
- Preserve public imports while refactoring by leaving compatibility wrappers where useful. Do not mix broad behavior changes with pure file moves unless tests cover the combined risk.
- Update `wiki/index.md` implementation roots whenever a new shard or module becomes an agent entrypoint.

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
| Deployment | `wiki/spec/deployment.md` |

## Git Freshness Protocol

- Every completed change slice must end with a Git commit if the wiki or codebase changed.
- Push the current branch after each slice commit when a remote is configured, so GitHub stays fresh.
- Use a focused commit message that names the completed task or slice.
- Before staging, inspect `git status` and avoid committing unrelated dirty files from another user or agent.
- Never commit `.env`, secrets, local session files, data volumes, caches, logs, or virtual environments.
- `git ci "message"` may be used only when the worktree contains no unrelated changes, because it stages with `git add -A`.

## Hard Rules

- Never edit `wiki/app-high-level.md`.
- No business logic in the collection worker.
- No person-level scores - community analysis only.
- If a spec is missing, write it before writing code.
- If spec and code conflict, log and resolve it.
