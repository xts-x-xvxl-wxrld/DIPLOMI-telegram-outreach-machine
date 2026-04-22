# API Briefs And Search

Optional brief and query-driven search endpoint contracts.

## Audience Briefs

Audience brief endpoints are optional/future in the seed-first MVP. They may remain available for
experiments, but the primary operator flow starts with CSV seed import.

### `POST /api/briefs`

Creates an audience brief from operator text.

The API stores the raw brief and enqueues `brief.process`. If `auto_start_discovery = true`, the
brief processing job starts discovery after it writes valid structured search fields.

Request:

```json
{
  "raw_input": "Hungarian SaaS founders and marketing communities",
  "auto_start_discovery": true
}
```

Response `201`:

```json
{
  "brief": {
    "id": "uuid",
    "raw_input": "Hungarian SaaS founders and marketing communities",
    "keywords": [],
    "related_phrases": [],
    "language_hints": [],
    "geography_hints": [],
    "exclusion_terms": [],
    "community_types": [],
    "created_at": "iso_datetime"
  },
  "job": {
    "id": "rq_job_id",
    "type": "brief.process",
    "status": "queued"
  }
}
```

If `auto_start_discovery = false`, the `brief.process` job still runs, but it does not enqueue
discovery after processing.

### `GET /api/briefs/{brief_id}`

Returns a brief and high-level discovery counts.

Response:

```json
{
  "brief": {},
  "counts": {
    "candidate": 12,
    "approved": 3,
    "rejected": 4,
    "monitoring": 3
  }
}
```
## Query-Driven Search

Query-driven search is a first-class workflow beside seed-first discovery. Search endpoints live
under `/api/search-runs` and `/api/search-candidates`; they do not extend brief endpoints.

API handlers validate requests, persist state, and enqueue search jobs. They must not call Telethon,
OpenAI, web-search providers, or retrieval adapters directly.

### `POST /api/search-runs`

Creates a search run from plain-language operator text and queues `search.plan`.

Request:

```json
{
  "query": "Hungarian SaaS founders",
  "requested_by": "telegram_user_id_or_operator",
  "language_hints": ["hu", "en"],
  "locale_hints": ["HU"],
  "enabled_adapters": ["telegram_entity_search"],
  "per_run_candidate_cap": 100,
  "per_adapter_caps": {
    "telegram_entity_search": {
      "per_query": 25
    }
  }
}
```

Rules:
- `query` is required after trimming and must not be empty.
- `enabled_adapters` defaults to `["telegram_entity_search"]`.
- The first implementation rejects unsupported adapters instead of silently accepting them.
- `per_run_candidate_cap` defaults to 100 and must be bounded by application validation.
- Creation sets `status = 'draft'`; the queued planner moves it to `planning`.

Response `201`:

```json
{
  "search_run": {
    "id": "uuid",
    "raw_query": "Hungarian SaaS founders",
    "normalized_title": "Hungarian SaaS founders",
    "status": "draft",
    "enabled_adapters": ["telegram_entity_search"],
    "language_hints": ["hu", "en"],
    "locale_hints": ["HU"],
    "per_run_candidate_cap": 100,
    "created_at": "iso_datetime"
  },
  "job": {
    "id": "rq_job_id",
    "type": "search.plan",
    "status": "queued"
  }
}
```

### `GET /api/search-runs`

Lists recent search runs.

Query parameters:
- `status`
- `requested_by`
- `limit` - default `20`, max `100`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "raw_query": "Hungarian SaaS founders",
      "normalized_title": "Hungarian SaaS founders",
      "status": "completed",
      "query_count": 3,
      "candidate_count": 24,
      "promoted_count": 2,
      "rejected_count": 5,
      "last_error": null,
      "created_at": "iso_datetime",
      "completed_at": "iso_datetime"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

### `GET /api/search-runs/{search_run_id}`

Returns one search run with aggregate counts.

Response:

```json
{
  "search_run": {
    "id": "uuid",
    "raw_query": "Hungarian SaaS founders",
    "normalized_title": "Hungarian SaaS founders",
    "status": "retrieving",
    "enabled_adapters": ["telegram_entity_search"],
    "language_hints": ["hu"],
    "locale_hints": ["HU"],
    "planner_source": "deterministic_v1",
    "ranking_version": null,
    "last_error": null,
    "started_at": "iso_datetime",
    "completed_at": null,
    "created_at": "iso_datetime"
  },
  "counts": {
    "queries": 3,
    "queries_completed": 1,
    "candidates": 8,
    "promoted": 0,
    "rejected": 0,
    "archived": 0
  }
}
```

### `GET /api/search-runs/{search_run_id}/queries`

Lists planner-created queries for a run.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "adapter": "telegram_entity_search",
      "query_text": "hungarian saas founders",
      "language_hint": "en",
      "locale_hint": "HU",
      "status": "completed",
      "planner_source": "deterministic_v1",
      "error_message": null,
      "created_at": "iso_datetime"
    }
  ],
  "total": 1
}
```

### `GET /api/search-runs/{search_run_id}/candidates`

Lists ranked candidates for one run.

Query parameters:
- `status` - optional; default includes `candidate` and `promoted`
- `limit` - default `10`, max `50`
- `offset`
- `include_archived` - default `false`
- `include_rejected` - default `false`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "search_run_id": "uuid",
      "status": "candidate",
      "community_id": "uuid-or-null",
      "title": "Example Community",
      "username": "example",
      "telegram_url": "https://t.me/example",
      "description": "Short public description",
      "member_count": 1234,
      "score": 72.5,
      "ranking_version": "search_rank_v1",
      "score_components": {
        "title_username_match": 40,
        "description_match": 25,
        "cross_query_confirmation": 7.5
      },
      "evidence_summary": {
        "total": 3,
        "types": ["entity_title_match", "description_match"],
        "snippets": ["Title matched saas founders"]
      },
      "first_seen_at": "iso_datetime",
      "last_seen_at": "iso_datetime"
    }
  ],
  "limit": 10,
  "offset": 0,
  "total": 1
}
```

Rules:
- Candidate lists must not expose raw message history, sender identity, phone numbers, or
  person-level scores.
- Evidence snippets are compact and capped.
- Sorting uses stored ranking fields and deterministic tie-breakers from the search spec.

### `POST /api/search-runs/{search_run_id}/rerank-jobs`

Queues `search.rank` to recompute scores from stored candidates, evidence, and review history.

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "search.rank",
    "status": "queued"
  }
}
```

Rerank does not call retrieval adapters and must not create or delete evidence rows.

### `POST /api/search-candidates/{candidate_id}/review`

Records a run-scoped review action for one search candidate.

Request:

```json
{
  "action": "promote",
  "requested_by": "telegram_user_id_or_operator",
  "notes": "Useful founder community"
}
```

Initial supported actions:
- `promote`
- `reject`
- `archive`

Later supported actions:
- `global_reject`
- `convert_to_seed`

Response:

```json
{
  "candidate": {
    "id": "uuid",
    "search_run_id": "uuid",
    "status": "promoted",
    "community_id": "uuid-or-null",
    "reviewed_at": "iso_datetime",
    "last_reviewed_by": "telegram_user_id_or_operator"
  },
  "review": {
    "id": "uuid",
    "action": "promote",
    "scope": "run",
    "created_at": "iso_datetime"
  }
}
```

Review rules:
- `promote`, `reject`, and `archive` update only the run-scoped search candidate.
- These actions do not mutate `communities.status`.
- `global_reject` is a separate explicit action and is not part of the first API skeleton.
- The endpoint must validate that the candidate exists and belongs to a search run.

### `POST /api/search-candidates/{candidate_id}/convert-to-seed`

Converts a reviewed search candidate into a seed-group row.

Request:

```json
{
  "seed_group_name": "Search: Hungarian SaaS founders",
  "requested_by": "telegram_user_id_or_operator"
}
```

Rules:
- `seed_group_name` is optional for the bot; when absent, the API uses the search run title.
- The candidate must have a resolved `community_id` or public username/canonical URL.
- The endpoint creates or reuses the named seed group.
- Duplicate conversion reuses the existing `seed_channels` row for the seed group and public username.
- Conversion writes `manual_seed` evidence and `convert_to_seed` review metadata linking the search candidate to the seed row.
- Candidate status becomes `converted_to_seed`.
