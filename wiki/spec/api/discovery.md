# API Discovery And Expansion

Seed import, seed group, direct entity intake, discovery, and expansion endpoint contracts.

## Discovery and Expansion

The primary MVP discovery flow is:

```text
POST /api/seed-imports/csv
  -> POST /api/seed-groups/{seed_group_id}/resolve-jobs
  -> seed.resolve queues community.snapshot for resolved seed communities
  -> GET /api/seed-groups
  -> GET /api/seed-groups/{seed_group_id}/candidates
```

Seed expansion endpoints may remain available for later experiments, but they are not part of the
active bare seed-import path.
## Direct Telegram Entity Intake

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
## Discovery and Expansion Endpoints

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
snapshots for each unique resolved community so metadata and visible members are persisted.

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
