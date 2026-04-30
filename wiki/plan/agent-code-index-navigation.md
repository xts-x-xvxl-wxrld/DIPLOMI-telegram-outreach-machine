# Agent Code Index Navigation

Status: planned

## Goal

Give Codex, Claude, and future coding agents a small, layered navigation system for the codebase
without turning `wiki/index.md` into a large mixed wiki/code inventory.

## Problem

`wiki/index.md` currently indexes both wiki artifacts and implementation roots. That makes it useful
as a first-stop map, but it also mixes two different jobs:
- finding specs, plans, shards, and project history
- finding the right code area, entrypoint, facade, worker, service, or test file

As the codebase grows, one flat implementation list becomes noisy. Agents need a gradual zoom path
that lets them read only the code index shard relevant to the current task.

## Target Structure

Keep wiki and code navigation separate:

```text
wiki/index.md
wiki/code-index/
  index.md
  backend.md
  bot.md
  tests.md
  scripts.md
  alembic.md
  backend/
    api.md
    services.md
    workers.md
    db.md
  bot/
    engagement.md
    search.md
    accounts.md
    formatting.md
```

Add more shards only when a parent index would become too broad. Prefer a short parent file that
points to narrower child indexes over one exhaustive code map.

## Responsibilities

`wiki/index.md` should index only wiki artifacts:
- specs
- plans
- shard directories
- runbooks or project-knowledge documents
- code-index entrypoint link

`wiki/code-index/index.md` should be the top-level human-readable code navigation entrypoint:
- subsystem list
- when to read each subsystem index
- cross-cutting rules for generated symbol indexes, if any are added later

Narrow code-index shards should explain:
- subsystem purpose
- read-first files
- entrypoints and facades
- important boundaries and invariants
- related tests
- spec or plan links that commonly apply

Code indexes are navigation maps, not behavior specs. The source of truth for product behavior
remains under `wiki/spec/`, and work sequencing remains under `wiki/plan/`.

## Agent Protocol

Before code changes, agents should:

1. Read `wiki/index.md` to find relevant specs and plans.
2. Read `wiki/code-index/index.md` to choose the code subsystem.
3. Read only the narrow code-index shard for the target subsystem.
4. Read the relevant spec or plan shard.
5. Use `rg` to verify symbols and call sites before editing.

After code changes, agents should:

1. Update the relevant code-index shard if files, entrypoints, facades, or ownership boundaries
   changed.
2. Update `wiki/index.md` only when wiki artifacts or the code-index entrypoint list changes.
3. Append `wiki/log.md`.
4. Run local CI parity required by `AGENTS.md` and `CLAUDE.md`.

## Generated Index Policy

Generated symbol or call-graph indexes may be added later, but they should stay separate from the
human-readable wiki maps. Preferred location:

```text
.agent-index/
```

Generated indexes must exclude files that normal coding agents should not read, including:
- `wiki/llm-wiki.md`
- `wiki/llm-wiki-md.txt`
- `wiki/log.md`
- `.claude/`
- env files
- sessions, data volumes, caches, and pytest scratch directories

Generated indexes should be optional helper artifacts. Agents must still verify code with `rg` and
targeted file reads before editing.

## Implementation Slices

1. Create the `wiki/code-index/` directory and top-level code navigation files.
2. Rewrite `wiki/index.md` so it is wiki-only and links to `wiki/code-index/index.md`.
3. Update `AGENTS.md` and `CLAUDE.md` with the combined wiki/code navigation protocol.
4. Add or adapt any generated symbol-index tooling only after the human-readable maps exist.

## Acceptance Criteria

- `wiki/index.md` no longer carries the long implementation-roots inventory.
- `wiki/code-index/index.md` exists and points to narrower code-index shards.
- At least backend, bot, tests, scripts, and alembic have code-index entries.
- Agent instructions require the wiki index, code-index entrypoint, relevant code shard, and relevant
  spec or plan before editing.
- Generated index tooling, if introduced, is ignored or otherwise kept out of normal source-control
  churn and respects project reading exclusions.
