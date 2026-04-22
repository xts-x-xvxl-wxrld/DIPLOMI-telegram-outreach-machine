# Search Rebuild Implementation Overview

Goal, context, guiding decisions, verification expectations, and progress.

## Goal

Turn the clean-sheet search rebuild design into a safe, incremental implementation path.

This plan resolves the implementation order for the gaps recorded in
`wiki/spec/search-rebuild.md`. It does not replace the active seed-first MVP path; it describes how
to introduce first-class query-driven search beside the current seed-group workflow.
## Current Context

The app already has:

- manual seed CSV intake
- direct public Telegram handle intake
- seed resolution into `communities`
- seed-group candidate review
- account-pool separation for search vs. engagement accounts
- Telegram bot as the initial operator UI

The search rebuild should reuse those primitives where they fit, but should not overload
`seed_groups` as the only search intent object. Search runs become their own durable workflow.
## Guiding Decisions

- `search_runs` are the operator intent object for query-driven search.
- `search_candidates` are run-scoped and may temporarily hold unresolved raw identity fields.
- `communities` remains the canonical durable community table after Telegram resolution.
- Search reject/archive actions are run-scoped by default.
- Global community rejection remains an explicit separate action.
- Graph expansion may start only from manual seeds or operator-promoted search candidates.
- First implementation is bot-first because the web frontend remains deferred.
- `telegram_post_search` waits until post evidence storage, snippet limits, and Telegram capability
  rules are fully specified.
- Ranking is deterministic, community-level, and explainable through stored score components.
- Search never creates person-level scores and never stores raw message history by default.
## Verification Expectations

Every implementation slice should include:

- focused tests for new service/API/worker/bot behavior
- wiki log entry
- spec updates if behavior changes
- no unrelated dirty files staged
- a focused Git commit
- push when remote is configured

Full-suite runs are recommended after schema, worker, and bot slices. Narrow tests are acceptable
for pure documentation or small API-client changes when full suite cost is high.
## Progress

### 2026-04-21 - Slice 0 Contract Resolution

Completed the implementation contract for the first query-driven search slices:

- locked search statuses, review actions, evidence types, caps, and ranking components in
  `wiki/spec/search-rebuild.md`
- added planned search tables, uniqueness rules, indexes, and retention constraints to
  `wiki/spec/database.md`
- added the first `/api/search-runs` and `/api/search-candidates` contracts to `wiki/spec/api.md`
- added `search.plan`, `search.retrieve`, `search.normalize`, `search.rank`, and deferred
  `search.expand` job contracts to `wiki/spec/queue.md`
- added first bot search commands and review behavior to `wiki/spec/bot.md`

Next slice: Slice 1 Core Search Schema.

### 2026-04-21 - Slice 1 Core Search Schema

Implemented the durable schema foundation for query-driven search:

- added search enums for adapters, statuses, evidence types, review actions, and review scopes
- added SQLAlchemy models for `search_runs`, `search_queries`, `search_candidates`,
  `search_candidate_evidence`, and `search_reviews`
- added Alembic migration `20260421_0011_search_schema.py`
- added Pydantic search request/response schemas for the upcoming API skeleton
- added focused schema tests for defaults, partial uniqueness, nullable unresolved candidates,
  foreign keys, PostgreSQL DDL compilation, and create-request validation

Next slice: Slice 2 API Skeleton.
