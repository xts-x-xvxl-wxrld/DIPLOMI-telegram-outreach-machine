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
