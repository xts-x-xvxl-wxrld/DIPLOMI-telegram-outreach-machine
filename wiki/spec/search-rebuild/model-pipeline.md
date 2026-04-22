# Search Rebuild Model And Pipeline

Search model, retrieval surfaces, planning, pipeline, normalization, evidence, ranking, and operator workflow contracts.

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
