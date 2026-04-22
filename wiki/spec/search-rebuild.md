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
- `backend/workers/search_retrieve.py` - `search.retrieve` worker orchestration, search-pool account leasing, account release, and rank enqueue handoff.
- `backend/workers/telegram_entity_search.py` - Telethon-backed Telegram entity search adapter.
- `backend/queue/client.py` - `search.plan` and `search.rank` enqueue helpers.
- `tests/test_search_schema.py` - schema contract tests.
- `tests/test_search_api.py` - API skeleton contract tests.
- `tests/test_search_planner.py` - deterministic planner and idempotent worker coverage.
- `tests/test_search_retrieve_worker.py` - fakeable Telegram entity search retrieval, duplicate, inaccessible, non-community, flood wait, and partial-failure coverage.
- Future `backend/workers/search_*` modules - remaining ranking and expansion job roots.

## Shards

- [Model and Pipeline](search-rebuild/model-pipeline.md)
- [Implementation](search-rebuild/implementation.md)
- [Positioning](search-rebuild/positioning.md)
