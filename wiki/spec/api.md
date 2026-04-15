# API Spec

## Purpose

The backend API is the only service the Telegram bot calls.

It validates operator requests, reads/writes Postgres state, enqueues RQ jobs, and returns status/results to the bot.

## Technology

- FastAPI
- JSON REST API
- Async SQLAlchemy
- RQ client for enqueueing jobs

## Auth

MVP auth is a shared internal API token between bot and API.

Requests include:

```http
Authorization: Bearer <BOT_API_TOKEN>
```

Unauthorized requests return `401`.

The API is intended for internal Docker network access. It should not be publicly exposed without additional authentication.

## Response Conventions

IDs are UUID strings unless otherwise noted.

Error response:

```json
{
  "error": {
    "code": "not_found",
    "message": "Community not found"
  }
}
```

Common status codes:

- `200` success
- `201` created
- `202` accepted/enqueued
- `400` validation error
- `401` unauthorized
- `404` not found
- `409` conflict
- `500` unexpected server error

## Health

### `GET /health`

Returns API liveness.

Response:

```json
{
  "status": "ok"
}
```

### `GET /ready`

Checks API dependencies.

Response:

```json
{
  "status": "ok",
  "postgres": "ok",
  "redis": "ok"
}
```

## Audience Briefs

### `POST /api/briefs`

Creates an audience brief from operator text.

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
    "type": "discovery.run",
    "status": "queued"
  }
}
```

If `auto_start_discovery = false`, `job` is `null`.

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

## Discovery and Expansion

### `POST /api/briefs/{brief_id}/discovery-jobs`

Starts discovery for an existing brief.

Request:

```json
{
  "limit": 50,
  "auto_expand": true
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "discovery.run",
    "status": "queued"
  }
}
```

### `POST /api/briefs/{brief_id}/expansion-jobs`

Starts expansion for selected communities.

Request:

```json
{
  "community_ids": ["uuid"],
  "depth": 1
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "expansion.run",
    "status": "queued"
  }
}
```

## Communities

### `GET /api/communities`

Lists communities.

Query parameters:

- `brief_id`
- `status`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "tg_id": 123456,
      "username": "example_channel",
      "title": "Example Channel",
      "description": "Short description",
      "member_count": 1234,
      "language": "hu",
      "is_group": false,
      "is_broadcast": true,
      "source": "tgstat",
      "match_reason": "Matched SaaS and founder keywords",
      "brief_id": "uuid",
      "status": "candidate",
      "store_messages": false,
      "first_seen_at": "iso_datetime",
      "last_snapshot_at": null
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

### `GET /api/communities/{community_id}`

Returns one community with latest snapshot and latest analysis summary.

Response:

```json
{
  "community": {},
  "latest_snapshot": {},
  "latest_analysis": {}
}
```

### `POST /api/communities/{community_id}/review`

Approves or rejects a candidate community.

Request:

```json
{
  "decision": "approve",
  "store_messages": false
}
```

Allowed decisions:

- `approve` - sets `status = 'monitoring'`.
- `reject` - sets `status = 'rejected'`.

Response:

```json
{
  "community": {
    "id": "uuid",
    "status": "monitoring",
    "store_messages": false,
    "reviewed_at": "iso_datetime"
  },
  "job": {
    "id": "rq_job_id",
    "type": "collection.run",
    "status": "queued"
  }
}
```

Approving a community enqueues an initial `collection.run`.

### `PATCH /api/communities/{community_id}`

Updates operator-controlled community settings.

Request:

```json
{
  "status": "monitoring",
  "store_messages": false
}
```

Response:

```json
{
  "community": {}
}
```

## Collection and Analysis

### `POST /api/communities/{community_id}/collection-jobs`

Manually starts collection for a community.

Request:

```json
{
  "window_days": 90
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "collection.run",
    "status": "queued"
  }
}
```

### `GET /api/communities/{community_id}/collection-runs`

Lists recent collection runs.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "community_id": "uuid",
      "status": "completed",
      "analysis_status": "completed",
      "window_days": 90,
      "messages_seen": 120,
      "members_seen": 45,
      "started_at": "iso_datetime",
      "completed_at": "iso_datetime"
    }
  ]
}
```

### `POST /api/collection-runs/{collection_run_id}/analysis-jobs`

Manually starts or retries analysis for a collection run.

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "analysis.run",
    "status": "queued"
  }
}
```

### `GET /api/communities/{community_id}/analysis`

Lists analysis summaries for a community.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "community_id": "uuid",
      "brief_id": "uuid",
      "summary": "Community-level summary",
      "dominant_themes": ["theme"],
      "activity_level": "moderate",
      "is_broadcast": true,
      "relevance_score": 0.82,
      "relevance_notes": "Why this community is relevant",
      "centrality": "core",
      "analysis_window_days": 90,
      "analyzed_at": "iso_datetime",
      "model": "configured_model"
    }
  ]
}
```

## Jobs and Debug

### `GET /api/jobs/{job_id}`

Returns RQ job status and metadata.

Response:

```json
{
  "id": "rq_job_id",
  "type": "collection.run",
  "status": "queued|started|finished|failed|deferred|scheduled",
  "meta": {},
  "error": null,
  "created_at": "iso_datetime",
  "started_at": "iso_datetime|null",
  "ended_at": "iso_datetime|null"
}
```

### `GET /api/debug/accounts`

Returns account pool health for the operator.

Response:

```json
{
  "counts": {
    "available": 4,
    "in_use": 1,
    "rate_limited": 2,
    "banned": 0
  },
  "items": [
    {
      "id": "uuid",
      "phone": "+123*****89",
      "status": "available",
      "flood_wait_until": null,
      "last_used_at": "iso_datetime",
      "last_error": null
    }
  ]
}
```

Phone numbers must be masked in API responses unless an explicit admin-only endpoint is added later.

## Security and Privacy Rules

- Bot talks only to the API.
- API never exposes raw message history by default.
- API never exposes phone numbers collected from Telegram users; phone numbers are not collected.
- API never returns person-level scores.
- Account phone numbers are operational secrets and must be masked in debug responses.
- Raw message storage remains opt-in per community through `store_messages`.
