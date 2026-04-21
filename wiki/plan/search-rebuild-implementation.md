# Search Rebuild Implementation Plan

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

## Slice 0: Contract Resolution

Purpose: make the spec implementation-ready before migrations or workers change.

Tasks:

1. Expand `wiki/spec/search-rebuild.md` with the concrete database contract.
2. Update `wiki/spec/database.md` with planned search tables and indexes.
3. Update `wiki/spec/api.md` with first search endpoints.
4. Update `wiki/spec/queue.md` with search job types, payloads, retry policy, and idempotency.
5. Update `wiki/spec/bot.md` with the first bot search commands and callbacks.

Decisions to lock:

- run statuses
- query statuses
- candidate statuses
- review action names and scope
- allowed evidence types
- ranking component names and weights
- per-run and per-adapter caps
- retention policy for raw adapter output and evidence snippets

Exit criteria:

- No open-contract section remains blocking the first database slice.
- Deferred areas are explicitly labeled as later slices, especially post search, web search, and
  second-wave graph expansion.

## Slice 1: Core Search Schema

Purpose: add durable search state without changing retrieval behavior yet.

Tables:

- `search_runs`
- `search_queries`
- `search_candidates`
- `search_candidate_evidence`
- `search_reviews`

Recommended first statuses:

- `search_runs.status`: `draft`, `planning`, `retrieving`, `ranking`, `completed`, `failed`,
  `cancelled`
- `search_queries.status`: `pending`, `running`, `completed`, `failed`, `skipped`
- `search_candidates.status`: `candidate`, `promoted`, `rejected`, `archived`,
  `converted_to_seed`
- `search_reviews.action`: `promote`, `reject`, `archive`, `convert_to_seed`,
  `global_reject`

Important schema rules:

- `search_candidates.community_id` is nullable until resolution succeeds.
- Candidate uniqueness is scoped to one run and should dedupe by `community_id` when present, then
  normalized username, then canonical public URL.
- Evidence rows must be append-only enough for replay and audit.
- Scores should preserve component detail and a `ranking_version`.
- Post/message evidence fields should exist only if the contract is finalized; otherwise keep that
  adapter out of the first migration.

Implementation targets:

- Alembic migration
- SQLAlchemy models
- Pydantic schemas
- focused schema tests

Exit criteria:

- Search tables migrate cleanly.
- Tests cover uniqueness, nullable unresolved candidates, allowed statuses, and foreign keys.

## Slice 2: API Skeleton

Purpose: let the bot and workers create and inspect search runs before real retrieval exists.

Endpoints:

- `POST /api/search-runs`
- `GET /api/search-runs`
- `GET /api/search-runs/{search_run_id}`
- `GET /api/search-runs/{search_run_id}/queries`
- `GET /api/search-runs/{search_run_id}/candidates`
- `POST /api/search-runs/{search_run_id}/rerank-jobs`
- `POST /api/search-candidates/{candidate_id}/review`

Initial behavior:

- Creating a run records the raw operator query and queues `search.plan`.
- Listing candidates returns empty results until retrieval slices exist.
- Review endpoint supports only run-scoped `promote`, `reject`, and `archive` until seed
  conversion is implemented.

Exit criteria:

- API contract tests cover create/list/detail/candidate-list/review validation.
- API never calls Telethon or OpenAI directly.

## Slice 3: Deterministic Query Planner

Purpose: create a working `search.plan` job without introducing model dependency first.

Behavior:

- Tokenize and normalize the operator query.
- Store one or more `search_queries` for `telegram_entity_search`.
- Preserve locale/language hints if supplied by the API payload.
- Store planner metadata with `planner_source = deterministic_v1`.
- Enqueue retrieval only after valid queries are committed.

Deferred:

- OpenAI-assisted query expansion.
- Reuse of `audience_briefs` or `brief.process`.

Exit criteria:

- `search.plan` is idempotent for the same run.
- Failed validation marks the run failed with a short error summary.
- Planner tests cover simple queries, duplicate terms, empty queries, and locale hints.

## Slice 4: Telegram Entity Search Adapter

Purpose: deliver the first real query-driven search surface.

Adapter contract:

- Input: `search_run_id`, `search_query_id`, query text, caps, requested operator.
- Account pool: search pool only.
- Output: raw public community hits with username, title, description, member count when available,
  and compact match evidence.
- No final relevance decisions.
- No raw message collection.

Worker behavior:

- Lease a managed search account.
- Execute Telegram entity search with per-query and per-run caps.
- Resolve public channels/groups into `communities` when possible.
- Create or merge run-scoped candidates.
- Write evidence rows such as `entity_title_match`, `entity_username_match`, and
  `description_match`.
- Mark partial failures at query level without failing the whole run when other queries succeeded.

Exit criteria:

- Fakeable adapter tests cover success, duplicate hits, inaccessible hits, non-community hits,
  flood waits, and partial failure.
- Existing community operator decisions are preserved.

## Slice 5: Candidate Normalization and Ranking

Purpose: make candidate results useful and explainable.

Ranking v1:

```text
+ title_username_match
+ description_match
+ cross_query_confirmation
+ cross_adapter_confirmation
+ activity_hint
- prior_run_rejection_penalty
- spam_penalty
```

Rules:

- Ranking is deterministic and community-level.
- Scores are persisted with component detail and `ranking_version = search_rank_v1`.
- Ties break by score, promoted/rejected state, evidence count, title, and candidate creation time.
- Prior run-scoped rejections reduce rank only for future runs, unless the operator chose
  `global_reject`.

Exit criteria:

- Ranking can be replayed without re-running retrieval.
- Candidate list API returns evidence summaries and component scores.
- Tests cover deterministic ordering and explanation fields.

## Slice 6: Bot Search Surface

Purpose: expose the first search workflow through the existing MVP operator UI.

Commands:

- `/search <plain language query>`
- `/searches`
- `/search_run <search_run_id>`
- `/search_candidates <search_run_id>`
- `/promote_search <candidate_id>`
- `/reject_search <candidate_id>`
- `/archive_search <candidate_id>`

Bot behavior:

- `/search` creates a run and reports queued planning job.
- Search-run detail shows status, query count, candidate count, and latest error if any.
- Candidate cards show title, username/link, member count, score summary, evidence summary, and
  run-scoped review controls.
- Bot copy describes communities, not outreach targets.

Exit criteria:

- Bot tests cover commands, callback routing, review actions, paging, and safe formatting.
- Candidate cards do not expose raw message history or person-level signals.

## Slice 7: Seed Conversion

Purpose: let strong search hits feed the existing seed-first ecosystem.

Contract:

- `convert_to_seed` requires a resolved `community_id` or public username/canonical URL.
- Conversion creates or appends to a named `seed_group`.
- The created `seed_channels` row should use the canonical public username URL when available.
- Conversion writes `manual_seed` evidence or review metadata linking the search candidate to the
  seed row.
- Candidate status becomes `converted_to_seed`.

API:

- `POST /api/search-candidates/{candidate_id}/convert-to-seed`

Bot:

- Add conversion action to promoted candidate detail.

Exit criteria:

- Duplicate conversion returns the existing seed row instead of creating duplicate seed channels.
- Seed resolution and candidate review continue to work through existing seed endpoints.

## Slice 8: Rerank and Replay

Purpose: support ranking changes without hitting Telegram again.

Behavior:

- `search.rank` recomputes scores from existing candidates and evidence.
- `rerank` does not create or delete evidence.
- Ranking metadata records version, timestamp, and component shape.
- API exposes last ranking version and rerank job status.

Exit criteria:

- Reranking a completed run is idempotent.
- Ranking-version changes can be tested against fixed evidence fixtures.

## Slice 9: Graph Expansion Gate

Purpose: add controlled second-wave discovery after first search is usable.

Allowed roots:

- resolved manual seed communities
- operator-promoted search candidates

Disallowed roots:

- arbitrary high-scoring candidates with no operator review
- unresolved raw hits
- globally rejected communities

Caps:

- per-run expansion root cap
- per-community inspected-neighbor cap
- per-adapter emitted-candidate cap
- account flood-wait backoff

Exit criteria:

- Expansion cannot start unless the root is manual or promoted.
- Evidence links each expanded candidate back to the source search candidate or seed.
- Expansion remains read-only discovery and does not join or post.

## Slice 10: Deferred Search Surfaces

Purpose: add recall boosters only after the core workflow is stable.

Deferred adapters:

- `telegram_post_search`
- `web_search_tme`
- model-assisted query expansion

Before `telegram_post_search`:

- Define Telegram capability and adapter method.
- Define snippet length, match-term storage, source post ID/URL handling, and retention.
- Confirm no full raw message-history storage by default.
- Add tests that snippets are capped and sender identity is not exposed.

Before `web_search_tme`:

- Define provider, query caps, result cache policy, and URL normalization.
- Require all web hits to resolve through Telegram before becoming durable communities.

## Slice 11: Frontend Later

Purpose: keep the first search rollout bot-first while reserving a richer review surface.

Frontend should wait until:

- bot search review exposes real operator pain points
- entity-search results have useful evidence summaries
- seed conversion is working
- ranking v1 has enough data for review

Future views:

- search run list/detail
- candidate evidence explorer
- ranking component view
- review history
- seed conversion flow
- rerank/replay controls

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
