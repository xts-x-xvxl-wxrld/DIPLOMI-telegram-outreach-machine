# API Foundation

Technology, auth, response, health, and privacy contracts.

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

Bot requests that need operator-specific capability checks may include:

```http
X-Telegram-User-Id: <numeric Telegram user id>
```

When backend-owned engagement admin capabilities are configured through `ENGAGEMENT_ADMIN_USER_IDS`,
protected engagement-admin mutation routes use this header to authorize prompt, style, topic,
target, and advanced community-setting changes. If backend capabilities are unconfigured, those
routes preserve the transitional rollout behavior and the Telegram bot may fall back to its local
`TELEGRAM_ADMIN_USER_IDS` allowlist.

### `GET /api/operator/capabilities`

Returns the backend capability view for the current bot request and Telegram operator ID.

Response:

```json
{
  "operator_user_id": 123456,
  "backend_capabilities_available": true,
  "engagement_admin": true,
  "source": "backend_admin_user_ids"
}
```

If `ENGAGEMENT_ADMIN_USER_IDS` is not configured, `backend_capabilities_available` is `false` and
`engagement_admin` is `null`, which tells the bot to use its transitional fallback.
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
- `403` forbidden
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
## Security and Privacy Rules

- Bot talks only to the API.
- API never exposes raw message history by default.
- API never exposes phone numbers collected from Telegram users; phone numbers are not collected.
- API never returns person-level scores.
- Account phone numbers are operational secrets and must be masked in debug responses.
- Raw message storage remains opt-in per community through `store_messages`.
