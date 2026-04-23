# Search Rebuild Spec

Top-level routing contract for clean-sheet query-driven Telegram search. Details live in `wiki/spec/search-rebuild/`.

## Responsibility

- Plan and run multi-surface Telegram community searches.
- Normalize evidence into reviewable community candidates.
- Keep seed-first discovery compatible with query-driven search outputs.

## Code Map

- `alembic/versions/20260421_0011_search_schema.py` - search schema.
- `backend/api/routes/search.py` - Slice 2 API skeleton for search runs, queries, candidates, rerank jobs, and reviews.
- `backend/services/search.py` - search run persistence, list/detail views, candidate list shaping, and review audit helpers.
- `backend/workers/search_plan.py` - deterministic `search.plan` worker that normalizes operator queries, writes `search_queries`, and enqueues retrieval.
- `backend/services/search_retrieval.py` - `search.retrieve` state transitions, candidate/community merge rules, evidence persistence, and query-level failure handling.
- `backend/services/search_deferred_surfaces.py` - dormant post-search and web-search surface contracts, snippet/privacy guards, and `t.me` URL normalization.
- `backend/workers/search_retrieve.py` - `search.retrieve` worker orchestration, search-pool account leasing, account release, and rank enqueue handoff.
- `backend/workers/telegram_entity_search.py` - Telethon-backed Telegram entity search adapter.
- `backend/services/search_ranking.py` - replayable `search_rank_v1` scoring, component explanations, prior rejection/spam penalties, and deterministic ordering metadata.
- `backend/workers/search_rank.py` - `search.rank` worker orchestration and commit/rollback boundary.
- `backend/queue/client.py` - `search.plan` and `search.rank` enqueue helpers.
- `backend/services/search_seed_conversion.py` - search-candidate to seed-group conversion, duplicate seed reuse, manual-seed evidence, and conversion review audit.
- `backend/services/search_expansion.py`, `backend/workers/search_expand.py` - gated second-wave graph expansion from promoted search candidates or resolved manual seeds, with source evidence provenance and ranking handoff.
- `bot/api_client_search.py`, `bot/search_handlers.py`, `bot/formatting_search.py`, `bot/ui_search.py` - Telegram bot search client methods, commands, candidate cards, review controls, paging, and seed conversion action.
- `tests/test_search_schema.py` - schema contract tests.
- `tests/test_search_api.py` - API skeleton contract tests.
- `tests/test_search_planner.py` - deterministic planner and idempotent worker coverage.
- `tests/test_search_deferred_surfaces.py` - deferred post-search and web-search privacy, snippet, retention, and URL-normalization contract tests.
- `tests/test_search_retrieve_worker.py` - fakeable Telegram entity search retrieval, duplicate, inaccessible, non-community, flood wait, and partial-failure coverage.
- `tests/test_search_ranking.py` - deterministic ranking, score components, penalties, ordering, and worker coverage.
- `tests/test_search_seed_conversion.py`, `tests/test_bot_search_handlers.py`, `tests/test_bot_search_api_client.py`, `tests/test_bot_search_ui.py` - seed conversion and bot search surface coverage.
- `tests/test_search_expansion.py`, `tests/test_search_expand_queue.py`, `tests/test_search_expand_worker.py` - search graph expansion gate, queue payload, dispatch, account-release, and evidence provenance coverage.
- Future `backend/workers/search_*` modules - remaining expansion job roots.

## Shards

- [Model and Pipeline](search-rebuild/model-pipeline.md)
- [Implementation](search-rebuild/implementation.md)
- [Positioning](search-rebuild/positioning.md)
