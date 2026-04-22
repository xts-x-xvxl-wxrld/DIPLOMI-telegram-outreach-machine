# Search Rebuild Slices 0-5

Detailed slices for contract resolution, schema, API, planner, adapter, and ranking.

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
