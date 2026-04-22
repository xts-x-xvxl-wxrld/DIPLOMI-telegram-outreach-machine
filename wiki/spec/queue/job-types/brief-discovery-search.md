# Queue Brief Discovery And Search Jobs

Detailed brief, discovery, and query-driven search job contracts.

### `brief.process`

Optional/future job triggered by the API after an audience brief is created.

Payload:

```json
{
  "brief_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "auto_start_discovery": true
}
```

Reads:

- `audience_briefs.raw_input`

Writes:

- `audience_briefs.keywords`
- `audience_briefs.related_phrases`
- `audience_briefs.language_hints`
- `audience_briefs.geography_hints`
- `audience_briefs.exclusion_terms`
- `audience_briefs.community_types`

May enqueue:

- `discovery.run`, if `auto_start_discovery = true` in a future brief-driven workflow

Rules:

- OpenAI calls are allowed in this job.
- The API must not call OpenAI directly.
- Discovery must not start automatically if structured output validation fails.
- The output is search guidance, not a relevance score.
- Briefs are not the active MVP discovery input; seed groups are primary.
### `discovery.run`

Optional/future job triggered after `brief.process` completes or when the operator manually starts
adapter-based discovery.

Payload:

```json
{
  "brief_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "limit": 50,
  "auto_expand": false
}
```

Writes:

- `communities` rows with `status = 'candidate'`
- `source = 'web_search'`, `source = 'telegram_search'`, `source = 'manual'`, or `source = 'expansion'`
- `brief_id`
- `match_reason`

May enqueue:

- `expansion.run` for promising seed communities, if enabled by API request or config.

MVP default:

- `discovery.run` is not on the primary MVP path.
- `auto_expand = false`.
### `search.plan`

Triggered after the API creates a query-driven search run.

Payload:

```json
{
  "search_run_id": "uuid",
  "requested_by": "telegram_user_id_or_operator"
}
```

Reads:

- `search_runs`

Writes:

- `search_runs.status`
- `search_runs.planner_source`
- `search_runs.planner_metadata`
- `search_queries`

May enqueue:

- `search.retrieve` for each valid pending query after planner writes commit

Rules:
- First planner source is `deterministic_v1`.
- The planner rejects empty normalized queries and marks the run `failed` with `last_error`.
- Planning is idempotent for one run by using `(search_run_id, adapter, normalized_query_key)`.
- OpenAI-assisted query expansion is deferred; this job does not call OpenAI in the first
  implementation.
- The job must not call Telethon or retrieval adapters directly.
### `search.retrieve`

Triggered by `search.plan` for each valid search query.

Payload:

```json
{
  "search_run_id": "uuid",
  "search_query_id": "uuid",
  "adapter": "telegram_entity_search",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="search_retrieve")`
- The account manager must lease only a `search` pool account for Telegram-backed search retrieval.

Reads:

- `search_runs`
- `search_queries`
- existing `communities`
- existing `search_candidates` for the same run

Writes:

- `search_queries.status`
- `communities` for resolved public channels/groups
- `search_candidates`
- `search_candidate_evidence`
- `search_runs.status`

May enqueue:

- `search.rank` when all queries for the run are completed, failed, or skipped

Rules:
- First active adapter is `telegram_entity_search`.
- Retrieval adapters emit raw public community hits plus compact evidence; they do not assign final
  relevance.
- Duplicate hits merge by `community_id`, then normalized username, then canonical public URL.
- Existing operator decisions on `communities.status` must be preserved.
- Query-level partial failures mark only that query failed when other queries can still complete.
- No raw message collection, no full message-history storage, and no person-level scores.
### `search.normalize`

Reserved job type for a later split between raw adapter output and candidate persistence.

The first implementation lets `search.retrieve` normalize hits directly into candidates and
evidence, because raw adapter-output storage is intentionally deferred.
### `search.rank`

Triggered after retrieval finishes or when the operator requests a rerank.

Payload:

```json
{
  "search_run_id": "uuid",
  "requested_by": "telegram_user_id_or_operator",
  "reason": "retrieval_complete|manual_rerank"
}
```

Reads:

- `search_runs`
- `search_candidates`
- `search_candidate_evidence`
- `search_reviews`

Writes:

- `search_candidates.score`
- `search_candidates.score_components`
- `search_candidates.ranking_version`
- `search_runs.status`
- `search_runs.ranking_version`
- `search_runs.ranking_metadata`

Rules:
- Ranking version starts as `search_rank_v1`.
- Ranking is deterministic, replayable, and community-level.
- Reranking does not call Telegram, OpenAI, web-search providers, or retrieval adapters.
- Reranking does not create, update, or delete evidence rows.
- If at least one query completed, a ranking failure may mark the run `failed`; otherwise the run
  should already carry query-level failures.
### `search.expand`

Deferred second-wave graph expansion job for query-driven search.

Payload:

```json
{
  "search_run_id": "uuid",
  "root_candidate_ids": ["uuid"],
  "depth": 1,
  "requested_by": "telegram_user_id_or_operator"
}
```

Rules:
- Expansion can start only from resolved manual seeds or operator-promoted, resolved search
  candidates.
- Unresolved candidates, arbitrary high-scoring candidates, archived candidates, run-scoped
  rejected candidates, and globally rejected communities are not valid roots.
- Search expansion is read-only discovery. It must not join communities, send messages, or create
  engagement targets.
