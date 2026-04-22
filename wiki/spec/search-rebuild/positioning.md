# Search Rebuild Positioning

Purpose, product goal, design principles, seeds relationship, jobs, caching, safety, MVP recommendation, and discovery relationship.

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
