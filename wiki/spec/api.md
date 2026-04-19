# API Spec

## Purpose

The backend API is the only service the Telegram bot calls.

It validates operator requests, reads/writes Postgres state, enqueues RQ jobs, and returns status/results to the bot.

The active MVP is seed-first. The API should make named `seed_groups` the primary discovery and
review context. Audience brief endpoints may remain as optional/future endpoints, but they should
not be required for candidate discovery.

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

## Discovery and Expansion

The primary MVP discovery flow is:

```text
POST /api/seed-imports/csv
  -> POST /api/seed-groups/{seed_group_id}/resolve-jobs
  -> seed.resolve queues collection.run for resolved seed communities
  -> GET /api/seed-groups
  -> GET /api/seed-groups/{seed_group_id}/candidates
```

Seed expansion endpoints may remain available for later experiments, but they are not part of the
active bare seed-import path.

### `POST /api/telegram-entities`

Accepts one public Telegram username or link from the bot, records an intake row, and queues
`telegram_entity.resolve`.

Request:

```json
{
  "handle": "@example",
  "requested_by": "telegram_bot"
}
```

Response `202`:

```json
{
  "intake": {
    "id": "uuid",
    "raw_value": "@example",
    "normalized_key": "username:example",
    "username": "example",
    "telegram_url": "https://t.me/example",
    "status": "pending",
    "entity_type": null,
    "community_id": null,
    "user_id": null
  },
  "job": {
    "id": "rq_job_id",
    "type": "telegram_entity.resolve",
    "status": "queued"
  }
}
```

The worker classifies the target as `channel`, `group`, `user`, or `bot`. Channels/groups are saved
to `communities`; users/bots are saved to `users`.

### `GET /api/telegram-entities/{intake_id}`

Returns the latest intake state, including the resolved `entity_type`, `community_id`, or `user_id`
when available.

### `POST /api/briefs/{brief_id}/discovery-jobs`

Optional/future endpoint that starts discovery for an existing brief.

The brief should already have structured fields from `brief.process`. If those fields are missing,
the discovery job fails with a clear error instead of running a weak raw-text-only search.

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

Optional/future endpoint that starts generic expansion for selected communities.

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

### `POST /api/seed-imports/csv`

Imports operator-curated Telegram seed links from CSV text supplied by the bot after a `.csv`
document upload.

CSV required columns:

- `group_name`
- `channel`

Optional columns:

- `title`
- `notes`

Accepted `channel` values are public Telegram usernames or links such as `@example`,
`https://t.me/example`, or `t.me/s/example`. Private invite links are rejected.

Seed field contract:

- `raw_value` preserves the trimmed CSV value.
- `normalized_key` is `username:<casefolded_username>`.
- `username` is parsed from the public username or link.
- `telegram_url` is normalized to `https://t.me/<username>`.
- `title` and `notes` are operator metadata.
- `community_id` stays null until `seed.resolve` links the row to a real community.

Seed row statuses:

- `pending`
- `resolved`
- `invalid`
- `inaccessible`
- `not_community`
- `failed`

Request:

```json
{
  "csv_text": "group_name,channel,title,notes\nHungarian SaaS,@example,Example,Anchor seed\n",
  "file_name": "seeds.csv",
  "requested_by": "telegram_bot"
}
```

Response `201`:

```json
{
  "imported": 1,
  "updated": 0,
  "errors": [],
  "groups": [
    {
      "id": "uuid",
      "name": "Hungarian SaaS",
      "imported": 1,
      "updated": 0
    }
  ]
}
```

Valid rows are committed even if other rows are skipped with row-level errors.

### `GET /api/seed-groups`

Lists manual seed groups.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Hungarian SaaS",
      "description": null,
      "created_by": "telegram_bot",
      "created_at": "iso_datetime",
      "seed_count": 12,
      "resolved_count": 3,
      "unresolved_count": 8,
      "failed_count": 1
    }
  ],
  "total": 1
}
```

### `GET /api/seed-groups/{seed_group_id}`

Returns one seed group with the same aggregate counts used by the seed-group list.

Response:

```json
{
  "group": {
    "id": "uuid",
    "name": "Hungarian SaaS",
    "description": null,
    "created_by": "telegram_bot",
    "created_at": "iso_datetime",
    "seed_count": 12,
    "resolved_count": 3,
    "unresolved_count": 8,
    "failed_count": 1
  }
}
```

### `GET /api/seed-groups/{seed_group_id}/channels`

Lists imported seed channels for one group.

### `POST /api/seed-groups/{seed_group_id}/resolve-jobs`

Starts resolution for imported seed rows in one seed group.

The resolver maps public Telegram usernames to `communities` rows and updates each seed row with
`status` and `community_id`. After the worker resolves seed communities, it queues initial
collection for each unique resolved community so metadata and visible members are persisted.

Request:

```json
{
  "limit": 100,
  "retry_failed": false
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "seed.resolve",
    "status": "queued"
  }
}
```

If no rows are eligible for resolution, returns `400` with `no_seed_channels_to_resolve`.

### `POST /api/seed-groups/{seed_group_id}/expansion-jobs`

Starts batch-scoped expansion for resolved seed channels in a group. If no seed channels have been
resolved to `communities` yet, the API returns `400` with `no_resolved_seed_communities`.

This endpoint preserves seed-group context and queues seed batch expansion. It must not flatten the
batch into a generic arbitrary-community expansion request where the seed group is lost.

Request:

```json
{
  "brief_id": "uuid-or-null",
  "depth": 1
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "seed.expand",
    "status": "queued"
  }
}
```

### `GET /api/seed-groups/{seed_group_id}/candidates`

Lists candidate communities associated with a seed group.

This endpoint should include both:

- manually resolved seed communities via `seed_channels.community_id`
- graph-discovered communities via `community_discovery_edges.target_community_id`

Query parameters:

- `status` - default `candidate`
- `limit`
- `offset`
- `include_rejected` - default `false`

Response:

```json
{
  "items": [
    {
      "community": {
        "id": "uuid",
        "username": "example_channel",
        "title": "Example Channel",
        "member_count": 1234,
        "source": "expansion",
        "match_reason": "Expanded from seed group 'Hungarian SaaS' via forward source from Seed Channel",
        "status": "candidate"
      },
      "seed_group_id": "uuid",
      "source_seed_count": 2,
      "evidence_count": 4,
      "evidence_types": ["forward_source", "telegram_link"],
      "candidate_score": 73
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

`candidate_score` is an operator sorting signal only. It must be deterministic, community-level,
and derived from graph evidence. It is not a person-level score and is not an outreach priority.

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

## Engagement

Engagement endpoints are optional/future. They must remain operator-controlled and separate from
collection and analysis.

### `GET /api/engagement/targets`

Lists manual engagement targets. Targets are the explicit engagement allowlist and are separate from
seed groups, direct handle intakes, and community review.

Query parameters:

- `status`
- `limit`
- `offset`

### `POST /api/engagement/targets`

Creates or returns an engagement target from an existing `community_id`, public Telegram username,
or public Telegram link.

Request:

```json
{
  "target_ref": "@example",
  "notes": "Manual engagement candidate",
  "added_by": "telegram_user_id_or_operator"
}
```

Rules:

- Existing `community_id` targets are created as `resolved`.
- Public username/link targets are created as `pending` and must be resolved by an engagement job.
- Duplicate normalized targets return the existing row instead of creating seed rows.
- Private invite-link resolution remains out of scope for MVP.

### `PATCH /api/engagement/targets/{target_id}`

Updates target status, notes, and engagement permissions.

Request:

```json
{
  "status": "approved",
  "allow_join": true,
  "allow_detect": true,
  "allow_post": false,
  "updated_by": "telegram_user_id_or_operator"
}
```

Rules:

- A target must resolve to a community before it can be approved.
- Rejected and archived targets force `allow_join`, `allow_detect`, and `allow_post` to false.
- Approving a target records `approved_by` and `approved_at`.

### `POST /api/engagement/targets/{target_id}/resolve-jobs`

Queues `engagement_target.resolve`. This is an engagement job, not a seed job.

Request:

```json
{
  "requested_by": "telegram_user_id_or_operator|null"
}
```

### `POST /api/engagement/targets/{target_id}/join-jobs`

Queues `community.join` for the target's resolved community. The worker still enforces target
approval and `allow_join`.

### `POST /api/engagement/targets/{target_id}/detect-jobs`

Queues manual `engagement.detect` for the target's resolved community. The worker still enforces
target approval and `allow_detect`.

### `GET /api/communities/{community_id}/engagement-settings`

Returns engagement settings for one community. If no settings exist, engagement is disabled.

### `PUT /api/communities/{community_id}/engagement-settings`

Creates or updates per-community engagement settings.

Request:

```json
{
  "mode": "suggest",
  "allow_join": true,
  "allow_post": false,
  "reply_only": true,
  "require_approval": true,
  "max_posts_per_day": 1,
  "min_minutes_between_posts": 240
}
```

MVP rules:

- `require_approval` must remain true.
- `reply_only` must remain true.
- Settings are disabled unless explicitly created or enabled.

### `POST /api/communities/{community_id}/join-jobs`

Queues `community.join` after verifying the community exists. The API does not call Telethon
directly.

Request:

```json
{
  "telegram_account_id": "uuid-or-null",
  "requested_by": "telegram_user_id_or_operator|null"
}
```

Response `202`:

```json
{
  "job": {
    "id": "rq_job_id",
    "type": "community.join",
    "status": "queued"
  }
}
```

### `GET /api/engagement/topics`

Lists configured engagement topics.

### `POST /api/engagement/topics`

Creates an engagement topic.

### `PATCH /api/engagement/topics/{topic_id}`

Updates an engagement topic.

### `POST /api/communities/{community_id}/engagement-detect-jobs`

Queues `engagement.detect`.

### `GET /api/engagement/candidates`

Lists candidate replies for operator review.

Query parameters:

- `status` - default `needs_review`
- `community_id`
- `topic_id`
- `limit`
- `offset`

### `POST /api/engagement/candidates/{candidate_id}/approve`

Approves a candidate reply. The API records the reviewer and review timestamp. Sending still happens
through `engagement.send`.

### `POST /api/engagement/candidates/{candidate_id}/reject`

Rejects a candidate reply.

### `POST /api/engagement/candidates/{candidate_id}/send-jobs`

Queues `engagement.send` for an approved candidate.

### `GET /api/engagement/actions`

Lists outbound action audit rows.

Query parameters:

- `community_id`
- `candidate_id`
- `status`
- `action_type`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "candidate_id": "uuid-or-null",
      "community_id": "uuid",
      "telegram_account_id": "uuid",
      "action_type": "reply",
      "status": "sent",
      "outbound_text": "exact approved public reply",
      "reply_to_tg_message_id": 123,
      "sent_tg_message_id": 456,
      "scheduled_at": "iso_datetime|null",
      "sent_at": "iso_datetime|null",
      "error_message": null,
      "created_at": "iso_datetime"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Rules:

- API handlers must not call Telethon directly.
- API responses must not expose phone numbers.
- API responses must not expose person-level scores.
- Engagement workers fail closed unless an approved engagement target grants the matching
  join/detect/post permission.
- Audit rows should remain available for operator review.

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
