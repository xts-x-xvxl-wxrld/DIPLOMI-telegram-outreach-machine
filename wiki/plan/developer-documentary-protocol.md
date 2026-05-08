# Developer Documentary Protocol

Status: planned

## Goal

Add a dedicated developer-documentation lane that accumulates verified code understanding during
normal implementation work, without overloading `wiki/spec/` or `wiki/code-index/`.

## Problem

The repository already has behavior specs and navigation indexes, but it lacks a stable place for
deeper developer understanding such as:
- what a subsystem really owns
- where a runtime flow actually starts and fans out
- which files are the practical entrypoints and facades
- which invariants and footguns matter during edits

Without a separate lane, those notes either never get written, get scattered into plans/logs, or
inflate specs that should stay contract-focused.

## Target Structure

```text
wiki/dev-docs/
  index.md
  protocol.md
  glossary.md
  templates/
    module-guide.md
    flow-guide.md
```

Future slices may add:

```text
wiki/dev-docs/
  architecture/
  modules/
  flows/
  patterns/
```

## Protocol

When an agent or developer deeply inspects or changes a subsystem:

1. Read the relevant spec and code-index entrypoint first.
2. Check whether a matching `wiki/dev-docs/` page already exists.
3. Update that page with only what was verified in code, tests, or current edits.
4. Record unresolved understanding gaps as open questions instead of guessing.
5. Append `wiki/log.md` when documentary artifacts change.

## Rollout

Slice 1:
- add the spec and plan for this documentary lane
- create `wiki/dev-docs/` with protocol, glossary, and starter templates
- rewrite `wiki/index.md` so it stays a wiki/documentation router instead of an implementation dump

Slice 2:
- update `AGENTS.md` and `CLAUDE.md` so future agents maintain the lane
- add the first high-value module and flow pages for active subsystems

Slice 3:
- expand coverage gradually as work naturally touches search, engagement, bot, and account areas
- refine templates if engineers find recurring omissions

## Acceptance Criteria

- `wiki/dev-docs/` exists with a clear entrypoint and maintenance protocol
- `wiki/spec/` remains the behavior source of truth
- `wiki/code-index/` remains the fast code navigation layer
- `wiki/index.md` points to the developer-docs lane
- agent instructions require upkeep of relevant dev-doc pages after substantial inspection or edits
- the initial documentation structure is small enough to stay maintainable
