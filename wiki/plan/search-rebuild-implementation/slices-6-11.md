# Search Rebuild Slices 6-11

Detailed slices for bot search, seed conversion, rerank/replay, graph gate, deferred surfaces, and frontend later.

## Slice 6: Bot Search Surface

Status: implemented in `bot/search_handlers.py`, `bot/formatting_search.py`, `bot/ui_search.py`,
with API-client and callback wiring.

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

Status: implemented through `POST /api/search-candidates/{candidate_id}/convert-to-seed`,
`backend/services/search_seed_conversion.py`, and bot convert controls.

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

Status: implemented through replayable `search.rank`, rerank job metadata on
`search_runs.ranking_metadata.last_rerank_job`, and component-shape metadata.

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

Status: implemented through gated `search.expand` queue/API/worker plumbing,
`backend/services/search_expansion.py`, and tests for promoted/manual roots.

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
