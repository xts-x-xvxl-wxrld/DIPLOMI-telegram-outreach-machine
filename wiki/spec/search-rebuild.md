# Search Rebuild Spec

## Purpose

This spec defines a clean-sheet rebuild target for Telegram community search.

It is intentionally broader than the current seed-first MVP discovery slice. The goal is to design
a search system that can accept an operator query, search across multiple public discovery
surfaces, explain why each community matched, and let the operator turn strong results into durable
research inputs.

This spec is not constrained by the current implementation shape. It is a future-facing design
target for a stronger search product.

## Product Goal

The operator should be able to describe a target audience or topic in plain language and receive a
ranked, explainable list of public Telegram communities that are likely to be relevant.

The system should:

- search beyond manually imported seeds
- combine multiple retrieval methods instead of relying on one weak query surface
- show evidence for every result
- support iterative operator review and refinement
- preserve safety boundaries around public-community discovery

## Design Principles

- Search is a retrieval system, not a single query endpoint.
- Every result must carry explainable evidence.
- Seeds remain valuable, but they are one discovery input among several.
- Query understanding may use structured extraction, but relevance decisions stay community-level and
  evidence-based.
- Ranking is deterministic and inspectable.
- Search should optimize for recall first, then precision through evidence fusion and operator review.

## Search Model

Search should become a first-class concept rather than being represented only by `seed_groups` or
optional briefs.

Recommended durable entities:

- `search_runs` - one operator search intent, such as `Hungarian SaaS founders`
- `search_queries` - generated subqueries, variants, or language forms associated with a run
- `search_candidates` - candidate communities discovered for a run
- `search_candidate_evidence` - evidence rows explaining each candidate hit
- `search_reviews` - operator actions such as promote, reject, archive, or convert to seed

`seed_groups` should remain useful, but as:

- a manual import path
- a high-signal source of trusted communities
- a graph expansion root
- an operator-curated output from a search run

They should not be the only search intent object in the long-term design.

## Retrieval Surfaces

The rebuilt search system should support multiple search surfaces in parallel.

### 1. Direct Handle Resolution

If the operator submits `@username` or a public `t.me/...` link, resolve it immediately and attach
the result to the current search run or save it as a standalone intake.

### 2. Telegram Native Entity Search

Search public channels and groups by terms likely to appear in:

- title
- username
- description
- public discovery metadata

This is useful for obvious or strongly named communities, but should not be treated as the only
search surface.

### 3. Telegram Post or Message Search

Search public post or message content for query terms, then attribute matching posts back to their
source communities.

This is critical because many relevant communities have weak names but strong topical post content.

### 4. Graph Expansion

Expand from trusted seeds or promising early hits through:

- linked discussion groups
- forwarded-from communities
- public Telegram links
- `@username` mentions
- repeated co-occurrence across already-relevant communities

Graph expansion should be a controlled second-wave retrieval step, not uncontrolled crawling.

### 5. Optional Public Web Search

Search the public web for Telegram links, for example with `site:t.me` patterns, then resolve all
hits back through Telegram before creating candidate communities.

This is a recall booster, not the primary truth source.

## Query Planning

One operator query should fan out into multiple structured subqueries.

Example:

```text
"Hungarian SaaS founders"
```

Could produce:

- core terms: `hungarian`, `saas`, `founder`, `startup`
- Hungarian variants: `magyar`, `vallalkozo`, `cegalapito`, `startup`
- related phrases: `b2b saas`, `startup community`, `founder group`
- exclusions: `job board`, `crypto spam`, `giveaway`
- search modes: entity search, post search, graph expansion

The planner may use a model to generate structured search guidance, but it must not make final
relevance decisions or produce person-level scores.

## Search Pipeline

Recommended end-to-end flow:

```text
operator query
  -> search_run created
  -> query planner creates search_queries
  -> retrieval adapters execute in parallel with caps
  -> raw hits normalized to communities
  -> evidence rows stored per hit
  -> duplicate communities merged
  -> deterministic ranking computed
  -> operator reviews/promotes/rejects
  -> optional second-wave graph expansion from trusted hits
```

Each stage should be replayable and observable.

## Candidate Normalization

All retrieval surfaces should normalize into the same community candidate model.

Preferred identity order:

1. Telegram `tg_id` after resolution
2. normalized public username
3. canonical public Telegram URL

Before a candidate becomes durable, the system should resolve public identifiers through Telegram
when possible. All retrieval surfaces should converge on the same `communities` identity so that:

- duplicate hits merge cleanly
- ranking can combine evidence across adapters
- operator decisions persist across future runs

## Evidence Model

Every candidate must have one or more evidence rows.

Recommended evidence fields:

- `search_run_id`
- `community_id`
- `adapter`
- `query_text`
- `evidence_type`
- `evidence_value`
- `source_community_id` nullable
- `source_seed_group_id` nullable
- `source_seed_channel_id` nullable
- `captured_at`

Examples of evidence types:

- `entity_title_match`
- `entity_username_match`
- `description_match`
- `post_text_match`
- `linked_discussion`
- `forward_source`
- `telegram_link`
- `mention`
- `web_result`
- `manual_seed`

The operator-facing product should explain results through evidence rather than opaque scores.

## Ranking

Ranking should be deterministic, explainable, and community-level.

It should combine signals such as:

- title and username match strength
- description match strength
- post or message match strength
- number of distinct search queries that found the same community
- number of distinct retrieval adapters that confirmed the same community
- graph support from trusted seeds or promoted communities
- public member count or activity hints when available
- operator rejection history
- spam or low-quality penalties

Recommended score shape:

```text
search_score =
  lexical_match
  + content_match
  + graph_support
  + cross_source_confirmation
  + activity_hint
  - spam_penalty
  - prior_rejection_penalty
```

The system should preserve individual score components so the UI can explain why a community ranked
high or low.

## Operator Workflow

Recommended operator flow:

1. Start a search run from plain language text.
2. Inspect ranked candidate communities with evidence summaries.
3. Mark communities as:
   - promoted
   - rejected
   - archive for later
   - convert to seed group
4. Launch graph expansion from promoted hits or trusted seeds.
5. Review second-wave results.
6. Move approved communities into monitoring or later research flows.

This makes search iterative rather than one-shot.

## Seeds in the Rebuilt Design

Seeds should remain important, but their role changes:

- seeds are one high-quality input source
- promoted search hits can become new seeds
- seed groups can anchor graph expansion
- seed evidence can increase ranking confidence

The rebuilt search system should therefore treat seeds as part of the search ecosystem, not as the
only implementation of search.

## Jobs and Adapters

Recommended async job families:

- `search.plan`
- `search.retrieve`
- `search.normalize`
- `search.rank`
- `search.expand`

Recommended adapter families:

- `telegram_entity_search`
- `telegram_post_search`
- `telegram_handle_resolve`
- `seed_graph_expand`
- `web_search_tme`

Each adapter should:

- declare its caps and rate limits
- emit structured evidence
- report partial failures cleanly
- avoid creating durable relevance judgments on its own

## Caching and Replay

Search should cache raw retrieval outputs and normalized evidence where safe so that:

- repeated queries are cheaper
- ranking changes can be replayed without full re-retrieval
- operators can inspect what happened during a search run

Replay is especially useful for ranking changes, spam-penalty tuning, and query-planner
improvements.

## Safety Rules

- Discovery finds communities, not people.
- No person-level scores.
- No private invite-link scraping.
- No hidden collection of private content.
- No raw message-history storage by default just because a search adapter matched a post.
- Query planning may extract search terms, but it must not decide final relevance without evidence.
- Telegram account-backed retrieval must use managed accounts with rate-limit and flood-wait safety.

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
- preserve API-supplied `language_hints` and `locale_hints`
- create one or more `search_queries` with `adapter = 'telegram_entity_search'`
- store `include_terms`, `exclusion_terms`, and `planner_metadata`

OpenAI-assisted expansion and audience-brief reuse are deferred.

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

- `telegram_post_search` - blocked until Telegram capability, source post identifiers, snippet
  limits, sender privacy, and retention are specified.
- `web_search_tme` - blocked until provider, query caps, result cache policy, and URL normalization
  are specified.
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

## MVP Recommendation

If implementation starts from this spec, the recommended first slice is:

1. Create first-class `search_runs` and `search_queries`.
2. Implement Telegram entity search.
3. Implement Telegram post or message search.
4. Normalize all hits into shared community candidates plus evidence rows.
5. Rank results using transparent evidence-based scoring.
6. Let operators promote strong hits into seeds.
7. Add graph expansion as a second-wave search step.

This gives the product a real query-driven search experience without requiring full autonomous
crawling in the first slice.

## Relationship to Current Discovery Spec

The current discovery spec remains the active MVP path for today's app. It is seed-first and keeps
graph expansion paused.

This search rebuild spec does not invalidate that slice. Instead, it defines a future state where:

- search becomes a first-class operator workflow
- seeds remain important but are no longer the only search entry point
- evidence-based ranking replaces thin query or title matching
- multiple retrieval surfaces combine into one explainable result set
