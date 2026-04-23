# Search Rebuild Implementation Contract

Durable object, status, adapter, evidence, normalization, ranking, API, queue, gate, and operator surface contracts.

## Implementation Contract

This section locks the first implementation contract for query-driven search. Deferred surfaces are
explicitly marked and do not block the core schema, API skeleton, deterministic planner, Telegram
entity search adapter, ranking, or bot review slices.

### Durable Objects

The first implementation uses five tables:

- `search_runs` - one operator query-driven search intent.
- `search_queries` - deterministic planner outputs for one run and one adapter.
- `search_candidates` - run-scoped candidate rows. `community_id` is nullable so unresolved raw
  public hits can be preserved until Telegram resolution succeeds.
- `search_candidate_evidence` - compact append-style evidence rows for why a candidate matched.
- `search_reviews` - operator review audit rows.

`communities` remains the canonical durable community identity after a candidate resolves through
Telegram. Search candidates may hold `normalized_username` and `canonical_url` before resolution.

Exact columns, indexes, and uniqueness rules live in `wiki/spec/database.md`.

### Statuses

Search run statuses:

- `draft` - created but not yet planned.
- `planning` - planner is creating `search_queries`.
- `retrieving` - one or more adapter queries are running.
- `ranking` - scores are being computed from stored candidates and evidence.
- `completed` - retrieval and ranking finished with usable output.
- `failed` - the run cannot continue. `last_error` must be populated.
- `cancelled` - operator or system stopped the run before completion.

Search query statuses:

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

Search candidate statuses:

- `candidate` - visible for review.
- `promoted` - run-scoped positive review.
- `rejected` - run-scoped rejection unless paired with a `global_reject` review.
- `archived` - run-scoped hide/defer action.
- `converted_to_seed` - candidate has been converted into a seed row.

Review actions:

- `promote` - sets candidate status to `promoted`; does not mutate `communities.status`.
- `reject` - sets candidate status to `rejected` for this run only.
- `archive` - sets candidate status to `archived` for this run only.
- `global_reject` - explicit separate action that may set the resolved community to
  `communities.status = 'rejected'` and applies a future-run ranking penalty.
- `convert_to_seed` - creates or reuses a seed row and sets candidate status to
  `converted_to_seed`.

The API skeleton starts with `promote`, `reject`, and `archive`. `global_reject` and
`convert_to_seed` are specified here for schema and audit compatibility but are enabled in later
slices.

### Planner Contract

`search.plan` replaces brief-driven planning for query-driven search. It lives beside the optional
`brief.process` path and does not require `audience_briefs`.

The first planner is `deterministic_v1`:

- trim and normalize the operator query
- reject empty or whitespace-only queries
- casefold duplicate generated query texts
- emit the full normalized term query plus contiguous 2-term or 3-term windows, capped at 5 total queries
- preserve API-supplied `language_hints` and `locale_hints`
- create one or more `search_queries` with `adapter = 'telegram_entity_search'`
- create `skipped` `search_queries` with deferred metadata for requested dormant adapters
  `telegram_post_search` and `web_search_tme`
- store `include_terms`, `exclusion_terms`, and `planner_metadata`

OpenAI-assisted query expansion and audience-brief reuse are deferred.

### Retrieval Adapter Contract

All adapters receive:

- `search_run_id`
- `search_query_id`
- `adapter`
- `query_text`
- caps from `search_runs.per_adapter_caps`
- `requested_by`

All adapters emit raw public community hits with:

- optional Telegram `tg_id`
- optional public `username`
- optional canonical public Telegram URL
- title
- description
- member count when available
- compact evidence rows
- adapter metadata, excluding secrets and full raw message history

Adapters never make final relevance decisions. They may resolve public channel/group identities into
`communities`; inaccessible and non-community hits remain query-level outcomes or unresolved
candidate evidence depending on what was safely known.

First active adapter:

- `telegram_entity_search` - uses only search-pool Telegram accounts and writes title, username,
  and description evidence.

Deferred adapters:

- `telegram_post_search` - dormant contract exists. It defines `search_posts`, caps snippets at
  240 characters, stores matched terms plus source post ID/URL in evidence metadata, filters sender
  identity, and retains only candidate evidence by default.
- `web_search_tme` - dormant contract exists. It defines provider/per-query caps, result-cache
  policy, public Telegram URL normalization, and requires Telegram resolution before a web hit can
  become a durable community.
- `seed_graph_expand` - blocked until the graph expansion gate slice.

### Evidence Contract

First active evidence types:

- `entity_title_match`
- `entity_username_match`
- `description_match`
- `handle_resolution`
- `manual_seed`
- `linked_discussion`
- `forward_source`
- `telegram_link`
- `mention`

Reserved/deferred evidence types:

- `post_text_match`
- `web_result`

Evidence value rules:

- store compact proof text only
- truncate `evidence_value` to 500 characters before persistence
- store adapter-specific structured details in `evidence_metadata`
- do not store sender identity, phone numbers, full raw message history, or person-level scores
- treat evidence rows as append-style audit facts; corrections should write new evidence or update
  candidate score fields, not overwrite the original proof row

### Candidate Normalization

Candidate identity is merged within a run in this order:

1. `community_id`, when Telegram resolution succeeds
2. normalized public username
3. canonical public Telegram URL

Resolution may create or update `communities` metadata, but it must preserve existing operator
decisions on `communities.status`. A rejected, monitoring, approved, or dropped community must not
be reset to `candidate` by search retrieval.

Run-scoped search review state lives on `search_candidates` and `search_reviews`; it must not be
inferred from global community status except for explicit `global_reject` penalties.

### Ranking Contract

Ranking version `search_rank_v1` persists a numeric `score` and JSON `score_components` on each
candidate. Scores are community-level review sorting signals only.

Component names and first weights:

```text
+ title_username_match:      40
+ description_match:        25
+ cross_query_confirmation: 15
+ cross_adapter_confirmation: 10
+ activity_hint:            10
- prior_run_rejection_penalty: -25
- spam_penalty:              -30
```

Component rules:

- `title_username_match` uses `entity_title_match` and `entity_username_match` evidence.
- `description_match` uses `description_match` evidence.
- `cross_query_confirmation` applies when distinct search queries found the same candidate.
- `cross_adapter_confirmation` is usually zero until multiple adapters are active.
- `activity_hint` uses public member count or safe adapter-level activity hints when available.
- `prior_run_rejection_penalty` applies to future runs after prior run-scoped rejections.
- `spam_penalty` applies to deterministic low-quality patterns, never to people.

Tie-breakers, in order:

1. score descending
2. status order: `promoted`, `candidate`, `archived`, `rejected`, `converted_to_seed`
3. evidence count descending
4. title ascending, nulls last
5. candidate creation time ascending

`search.rank` must be replayable from stored candidates, evidence, and review history without
running Telegram retrieval again.

### Caps and Retention

First defaults:

- per-run candidate cap: 100
- `telegram_entity_search` per-query hit cap: 25
- maximum generated queries per run in `deterministic_v1`: 5
- evidence value cap: 500 characters
- candidate evidence metadata cap: 8 KB per row

Raw adapter output is not stored in the first implementation except as compact candidate fields,
evidence rows, and capped metadata. RQ result metadata follows the queue retention policy. Search
run/candidate/evidence/review rows are durable until an explicit pruning policy is added.

### API and Queue Boundaries

Search endpoints live under `/api/search-runs` and `/api/search-candidates`; they do not extend the
legacy brief endpoints.

Search jobs live beside seed-first jobs:

- `search.plan`
- `search.retrieve`
- `search.normalize` (reserved until retrieval/normalization are split)
- `search.rank`
- `search.expand` (deferred until the graph expansion gate)

The API must not call Telethon or OpenAI directly.

### Graph Expansion Gate

Second-wave expansion may start only from:

- resolved manual seed communities
- operator-promoted, resolved search candidates

It must not start from arbitrary high-scoring candidates, unresolved raw hits, archived candidates,
run-scoped rejected candidates, or globally rejected communities.

`search.expand` is the query-driven expansion job. It leases an expansion account, inspects only
eligible roots through the graph adapter, writes expanded results back into the same
`search_candidates` and `search_candidate_evidence` tables with `adapter = 'seed_graph_expand'`,
and enqueues `search.rank` after persistence. Search-candidate roots are linked through
`evidence_metadata.source_search_candidate_id`; manual seed roots use the durable
`source_seed_group_id` and `source_seed_channel_id` evidence columns.

### First Operator Surface

The first implementation is Telegram-bot-first:

- `/search <plain language query>`
- `/searches`
- `/search_run <search_run_id>`
- `/search_candidates <search_run_id>`
- `/promote_search <candidate_id>`
- `/reject_search <candidate_id>`
- `/archive_search <candidate_id>`

The web frontend is deferred until the bot workflow exposes real review needs.
