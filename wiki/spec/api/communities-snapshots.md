# API Communities Snapshots And Analysis

Community review, snapshot, members, and analysis endpoint contracts.

## Communities

### `GET /api/communities`

Lists communities.

Query parameters:

- `brief_id`
- `seed_group_id`
- `status`
- `limit`
- `offset`

When `seed_group_id` is provided, the endpoint should behave like the seed-group candidates view:
return communities linked through resolved seed rows or expansion provenance. A dedicated
`/seed-groups/{seed_group_id}/candidates` endpoint is preferred for richer evidence summaries.

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
      "source": "expansion",
      "match_reason": "Expanded from seed group 'Hungarian SaaS' via telegram link from Example Seed",
      "brief_id": null,
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
    "type": "community.snapshot",
    "status": "queued"
  }
}
```

Approving a community enqueues an initial `community.snapshot`.

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
## Snapshots and Analysis

### `POST /api/communities/{community_id}/snapshot-jobs`

Manually starts a discovery community snapshot.

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
    "type": "community.snapshot",
    "status": "queued"
  }
}
```

### `GET /api/communities/{community_id}/snapshot-runs`

Lists recent discovery snapshot runs. The response still uses `collection_runs` storage fields
because that table is the durable run/artifact boundary.

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

### `GET /api/communities/{community_id}/members`

Lists visible users collected for one community. This is a read-only operator view over
`community_members` joined to `users`.

Query parameters:

- `limit` - default `20`, max `1000`
- `offset` - default `0`
- `username_present` - optional boolean filter
- `has_public_username` - optional alias for `username_present`
- `activity_status` - optional `inactive`, `passive`, or `active`

Response:

```json
{
  "items": [
    {
      "tg_user_id": 123456,
      "username": "public_user",
      "first_name": "Public",
      "membership_status": "member",
      "activity_status": "inactive",
      "first_seen_at": "iso_datetime",
      "last_updated_at": "iso_datetime",
      "last_active_at": null
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Rules:

- Do not return phone numbers.
- Do not return internal user IDs.
- Do not return event counts as a person-level ranking signal.
- Do not return person-level scores.

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
