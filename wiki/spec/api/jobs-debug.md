# API Jobs And Debug

Job status and account debug endpoint contracts.

## Jobs and Debug

### `GET /api/jobs/{job_id}`

Returns RQ job status and metadata.

Response:

```json
{
  "id": "rq_job_id",
  "type": "community.snapshot",
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
