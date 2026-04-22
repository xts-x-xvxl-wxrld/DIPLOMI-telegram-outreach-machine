# Context Fragmentation Protocol

Status: in-progress

## Goal

Reduce coding-agent token use by keeping agent-facing wiki files and core code files small,
routable, and split along stable operational boundaries.

## Scope

In scope:
- Agent instructions in `AGENTS.md` and `CLAUDE.md`.
- Ignore rules for local worktrees, temp directories, caches, sessions, data volumes, and env files.
- Wiki and code size thresholds that future work must follow.
- Follow-up refactor slices for oversized wiki specs and core implementation files.

Out of scope for this protocol slice:
- Moving existing code into new modules.
- Rewriting existing large specs.
- Deleting local `.claude/` worktrees or pytest temp directories.

## Protocol

### Reading Rules

Agents should start from `wiki/index.md`, then read only the relevant spec shard and plan. They
should use `rg` for headings and symbols before opening large files.

Agents should not read these during normal coding:
- `wiki/llm-wiki.md`
- `wiki/llm-wiki-md.txt`
- all of `wiki/log.md`
- `.claude/`
- pytest temp directories
- caches
- sessions
- data volumes
- `.env` files

Use `rg "^## \\[" wiki/log.md` to inspect recent history headings. Open full log history only when
the task is explicitly historical.

### Wiki Fragmentation Rules

Top-level specs are routing contracts. They should contain only:
- module responsibility
- non-goals and invariants
- interface summary
- code map
- links to focused shards
- open questions

Soft caps:
- top-level spec: 300 lines
- plan: 200 lines
- `wiki/index.md`: 150 lines

When a top-level spec needs more detail, split into shards under a module directory, for example:

```text
wiki/spec/engagement.md
wiki/spec/engagement/topics.md
wiki/spec/engagement/candidates.md
wiki/spec/engagement/prompts.md
wiki/spec/engagement/scheduling.md
```

The parent spec keeps a short summary and links to each shard. New feature plans should use slice
files instead of one sprawling plan.

### Code Fragmentation Rules

Soft caps:
- production file: 800 lines
- test file: 1,000 lines

If a touched file is already over the cap, agents should avoid adding feature-sized behavior to it.
They should extract a cohesive module first or include extraction in the same slice.

Preferred split boundaries:
- API routes by resource or operator workflow.
- Bot handlers by command group and callback namespace.
- Bot formatting by domain.
- Bot UI helpers by menu/control surface.
- Services by aggregate or subdomain.
- Workers into orchestration, persistence, Telegram adapter, and model/LLM adapter layers.
- Tests by public behavior surface.

Pure moves should preserve public imports with compatibility wrappers when that reduces risk. Broad
behavior changes should not be mixed with file moves unless the tests cover the combined behavior.

## Refactor Backlog

Completed in the 2026-04-22 fragmentation refactor:
- Split `wiki/spec/engagement.md` into parent contract plus focused shards.
- Split `wiki/spec/bot-engagement-controls.md` into navigation, admin controls, editing,
  formatting, and tests shards.
- Split `wiki/spec/api.md` into resource-specific API shards.
- Split `wiki/spec/database.md` into core discovery/search/engagement schema shards.
- Split remaining oversized top-level specs for queue, bot, bot cockpit, engagement admin control
  plane, search rebuild, and engagement embedding matching.
- Split oversized plan files for bot engagement controls, community engagement, engagement operator
  controls, and search rebuild implementation.
- Split `bot/formatting.py` and `bot/ui.py` by discovery vs. engagement surfaces while preserving
  compatibility exports.
- Split `bot/main.py` into app, runtime, discovery handler, callback handler, engagement command,
  and engagement workflow modules while preserving `bot.main` compatibility exports.
- Split `backend/services/community_engagement.py` into settings, targets, topics, prompts, style
  rules, candidates, actions, and shared view modules.
- Split remaining oversized backend production files: engagement API routes, SQLAlchemy models, and
  engagement detection worker orchestration.

Remaining backlog:

5. Split oversized tests after the production modules have stable entrypoints.

## Acceptance Criteria

- Agent instructions include reading limits, wiki fragmentation limits, and code fragmentation
  limits.
- Local duplicate worktrees and temp directories are ignored by Git and Docker context.
- The architecture spec records the context fragmentation rule as a project design constraint.
- The wiki index links this plan.
